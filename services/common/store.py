"""Document store interface with two implementations behind it (§4.1, decision 0010).

- ``FirestoreStore``: Google Cloud Firestore (Native). Used on Cloud Run. **Not exercised locally**:
  the Firestore emulator needs the ``firebase``/``gcloud`` CLI, which this build may not run.
- ``MemoryStore``: an in-memory fake with the same transaction semantics that the code relies on
  (every read before the first write, as Firestore requires; ``create`` fails if the document
  exists; a transaction either applies all writes or none). Used by tests and ``evals/runners/local_cascade.py``.

Paths are slash-separated document paths such as ``gaps/g1/events/000001``.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class AlreadyExists(Exception):
    """``create`` on a document that already exists."""


class ReadAfterWrite(RuntimeError):
    """A transaction read after it wrote. Firestore forbids this (``ReadAfterWriteError``): every
    read in a transaction must come before its first write. MemoryStore enforces the same rule."""


class Txn(Protocol):
    def get(self, path: str) -> dict[str, Any] | None: ...
    def set(self, path: str, data: dict[str, Any]) -> None: ...
    def create(self, path: str, data: dict[str, Any]) -> None: ...
    def update(self, path: str, data: dict[str, Any]) -> None: ...
    def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]: ...


class Store(Protocol):
    def get(self, path: str) -> dict[str, Any] | None: ...
    def set(self, path: str, data: dict[str, Any]) -> None: ...
    def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]: ...
    def delete(self, path: str) -> None: ...
    def transaction(self, fn: Callable[[Txn], T]) -> T: ...


class _MemoryTxn:
    def __init__(self, store: MemoryStore):
        self._store = store
        self._writes: dict[str, dict[str, Any] | None] = {}
        self._creates: set[str] = set()
        self._wrote = False

    def _check_read(self, what: str) -> None:
        if self._wrote:
            raise ReadAfterWrite(f"read of {what} after a write in the same transaction")

    def _peek(self, path: str) -> dict[str, Any] | None:
        if path in self._writes:
            return copy.deepcopy(self._writes[path])
        return self._store.get(path)

    def get(self, path: str) -> dict[str, Any] | None:
        self._check_read(path)
        return self._peek(path)

    def set(self, path: str, data: dict[str, Any]) -> None:
        self._wrote = True
        self._writes[path] = copy.deepcopy(data)

    def create(self, path: str, data: dict[str, Any]) -> None:
        if self._peek(path) is not None:  # Firestore fails the commit; same outcome
            raise AlreadyExists(path)
        self._wrote = True
        self._creates.add(path)
        self._writes[path] = copy.deepcopy(data)

    def update(self, path: str, data: dict[str, Any]) -> None:
        current = self._peek(path)
        if current is None:
            raise KeyError(path)
        current.update(copy.deepcopy(data))
        self._wrote = True
        self._writes[path] = current

    def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]:
        self._check_read(collection)
        prefix = collection.rstrip("/") + "/"
        merged: dict[str, dict[str, Any]] = dict(self._store.list(collection))
        for path, data in self._writes.items():
            if path.startswith(prefix) and path.count("/") == prefix.count("/"):
                if data is None:
                    merged.pop(path[len(prefix):], None)
                else:
                    merged[path[len(prefix):]] = copy.deepcopy(data)
        return sorted(merged.items())


class MemoryStore:
    """In-memory fake. Transactions are serialised with a lock, so they never interleave."""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, path: str) -> dict[str, Any] | None:
        with self._lock:
            doc = self._docs.get(path)
            return copy.deepcopy(doc) if doc is not None else None

    def set(self, path: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._docs[path] = copy.deepcopy(data)

    def delete(self, path: str) -> None:
        with self._lock:
            self._docs.pop(path, None)

    def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]:
        prefix = collection.rstrip("/") + "/"
        depth = prefix.count("/")
        with self._lock:
            return sorted(
                (p[len(prefix):], copy.deepcopy(d)) for p, d in self._docs.items()
                if p.startswith(prefix) and p.count("/") == depth
            )

    def transaction(self, fn: Callable[[Txn], T]) -> T:
        with self._lock:
            txn = _MemoryTxn(self)
            result = fn(txn)
            for path in txn._creates:
                if path in self._docs:
                    raise AlreadyExists(path)
            for path, data in txn._writes.items():
                if data is None:
                    self._docs.pop(path, None)
                else:
                    self._docs[path] = data
            return result

    def require(self, path: str) -> dict[str, Any]:
        doc = self.get(path)
        if doc is None:
            raise KeyError(path)
        return doc

    # Test helper: break the store on purpose (tamper tests).
    def raw(self) -> dict[str, dict[str, Any]]:
        return self._docs


# Firestore database IDs must be 4-63 characters, so the "sim" database is named covercall-sim
# (docs/decisions/0022-sim-database-id.md). Keep in step with SIM_DB_ID in infra/env.sh.
SIM_DATABASE = "covercall-sim"


class FirestoreStore:  # pragma: no cover - needs a Firestore project or emulator
    """Firestore (Native mode) implementation. One instance per database ((default) or SIM_DATABASE)."""

    def __init__(self, database: str = "(default)", project: str | None = None):
        from google.cloud import firestore

        self._fs = firestore
        self._client = firestore.Client(project=project, database=database)

    def _ref(self, path: str) -> Any:
        return self._client.document(path)

    def get(self, path: str) -> dict[str, Any] | None:
        snap = self._ref(path).get()
        return snap.to_dict() if snap.exists else None

    def set(self, path: str, data: dict[str, Any]) -> None:
        self._ref(path).set(data)

    def delete(self, path: str) -> None:
        self._ref(path).delete()

    def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]:
        return sorted((d.id, d.to_dict() or {}) for d in self._client.collection(collection).stream())

    def transaction(self, fn: Callable[[Txn], T]) -> T:
        client, fs, ref = self._client, self._fs, self._ref

        class _FsTxn:
            def __init__(self, tx: Any):
                self.tx = tx

            def get(self, path: str) -> dict[str, Any] | None:
                snap = ref(path).get(transaction=self.tx)
                return snap.to_dict() if snap.exists else None

            def set(self, path: str, data: dict[str, Any]) -> None:
                self.tx.set(ref(path), data)

            def create(self, path: str, data: dict[str, Any]) -> None:
                self.tx.create(ref(path), data)

            def update(self, path: str, data: dict[str, Any]) -> None:
                self.tx.update(ref(path), data)

            def list(self, collection: str) -> list[tuple[str, dict[str, Any]]]:
                docs = client.collection(collection).get(transaction=self.tx)
                return sorted((d.id, d.to_dict() or {}) for d in docs)

        @fs.transactional
        def run(tx: Any) -> T:
            return fn(_FsTxn(tx))

        return run(client.transaction())
