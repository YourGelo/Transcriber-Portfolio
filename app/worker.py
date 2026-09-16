import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from celery import Celery

from app import config, storage
from app.audio import transcribe_audio
from app.db import Job, SessionLocal

celery = Celery("transcriber", broker=config.REDIS_URL)
celery.conf.update(
    task_serializer="json", accept_content=["json"], broker_connection_retry_on_startup=True
)
logger = logging.getLogger(__name__)


@celery.task(ignore_result=True)
def process_audio(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "processing"
        db.commit()
        try:
            with TemporaryDirectory() as directory:
                path = str(Path(directory) / "input.audio")
                storage.client().download_file(config.S3_BUCKET, job.input_key, path)
                job.result = transcribe_audio(path)
            job.status = "completed"
        except Exception as exc:
            # Do not expose paths, credentials or provider response bodies.
            logger.error("Job %s failed (%s)", job_id, type(exc).__name__)
            job.status = "failed"
            job.error = "Audio processing failed"
        db.commit()
