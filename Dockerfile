FROM python:3.12-slim AS api
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY migrations migrations
COPY alembic.ini .
RUN useradd --create-home app
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM api AS worker
USER root
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt
RUN mkdir -p /home/app/.cache && chown app:app /home/app/.cache
USER app
CMD ["celery", "-A", "app.worker.celery", "worker", "--loglevel=info", "--concurrency=1", "--pool=solo"]
