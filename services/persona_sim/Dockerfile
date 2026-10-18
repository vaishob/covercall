# Build from the repo root: docker build -f services/persona_sim/Dockerfile .
# All data is synthetic. No secrets are baked into the image (Secret Manager only).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY services/persona_sim/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/persona_sim/__init__.py services/persona_sim/__init__.py
COPY datagen datagen
COPY policy policy
COPY services/__init__.py services/__init__.py
COPY services/common services/common
COPY services/persona_sim services/persona_sim
RUN useradd --create-home app
USER app
CMD ["sh", "-c", "uvicorn services.persona_sim.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
