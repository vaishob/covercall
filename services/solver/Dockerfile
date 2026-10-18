# Build from the repo root: docker build -f services/solver/Dockerfile .
# All data is synthetic. No secrets are baked into the image (Secret Manager only).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY services/solver/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/solver/__init__.py services/solver/__init__.py
COPY policy policy
COPY services/__init__.py services/__init__.py
COPY services/solver services/solver
RUN useradd --create-home app
USER app
CMD ["sh", "-c", "uvicorn services.solver.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
