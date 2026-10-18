# Decision 0004: Design doc file name

- **Date:** 2026-10-18
- **PDF section:** §0, §13.1

## Context
The design doc was committed on `main` as `docs/CoverCall-Design-Doc.pdf.pdf` (double
extension). The handoff prompt refers to it as `docs/CoverCall-Design-Doc.pdf`.

## Decision
Rename it to `docs/CoverCall-Design-Doc.pdf` with `git mv` on `claude/slices-1-2`. The commit on
`main` is untouched (branch rules forbid changing `main`).

## Alternatives
Leave the double extension. Rejected: every reference in the docs uses the single extension.
