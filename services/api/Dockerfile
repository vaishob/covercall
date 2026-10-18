# Build from the repo root: docker build -f services/api/Dockerfile .
# All data is synthetic. No secrets are baked into the image (Secret Manager only).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY services/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/api/__init__.py services/api/__init__.py
COPY policy policy
COPY config config
COPY baseline baseline
COPY datagen datagen
COPY services/__init__.py services/__init__.py
COPY services/common services/common
COPY services/api services/api
COPY services/agent services/agent
COPY services/guard services/guard
RUN useradd --create-home app
USER app
CMD ["sh", "-c", "uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
