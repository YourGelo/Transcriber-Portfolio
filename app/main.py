from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile

from app import config, storage
from app.db import Job, SessionLocal
from app.worker import process_audio

app = FastAPI(title="Transcriber Portfolio")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcriptions", status_code=202)
def create_transcription(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".flac"}:
        raise HTTPException(415, "Unsupported audio extension")
    # Read at most limit + 1 bytes, including when Content-Length is absent.
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Empty audio file")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Audio exceeds 25 MiB")
    job_id = str(uuid4())
    key = f"jobs/{job_id}/input{suffix}"
    with SessionLocal() as db:
        job = Job(id=job_id, input_key=key, status="queued")
        try:
            storage.client().put_object(Bucket=config.S3_BUCKET, Key=key, Body=data)
            db.add(job)
            db.commit()
            process_audio.delay(job_id)
        except Exception:
            db.rollback()
            saved = db.get(Job, job_id)
            if saved is not None:
                saved.status = "failed"
                saved.error = "Could not queue audio"
                db.commit()
            raise HTTPException(503, "Storage or queue unavailable") from None
    return {"job_id": job_id, "status": "queued"}


@app.get("/transcriptions/{job_id}")
def get_transcription(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return {"job_id": job.id, "status": job.status, "result": job.result, "error": job.error}
