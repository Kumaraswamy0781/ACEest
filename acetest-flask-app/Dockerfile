FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install -r requirements.txt \
    && useradd --create-home --uid 10001 app

COPY --chown=app:app . .
RUN mkdir -p /app/instance && chown app:app /app /app/instance
USER app

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--preload", "app:app"]
