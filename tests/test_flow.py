from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import audio, main, worker
from app.db import Base, Job


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    s3 = Mock()
    monkeypatch.setattr(main.storage, "client", lambda: s3)
    queue = Mock()
    monkeypatch.setattr(main.process_audio, "delay", queue)
    with TestClient(main.app) as client:
        yield client, sessions, s3, queue
    engine.dispose()


def test_upload_process_result(setup, monkeypatch):
    client, sessions, s3, queue = setup
    response = client.post("/transcriptions", files={"file": ("test.wav", b"audio")})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    queue.assert_called_once_with(job_id)
    assert client.get(f"/transcriptions/{job_id}").json()["status"] == "queued"
    result = {"language": "en", "segments": [{"start": 0, "end": 1, "text": "hello"}]}
    monkeypatch.setattr(worker, "transcribe_audio", lambda path: result)
    worker.process_audio.run(job_id)
    body = client.get(f"/transcriptions/{job_id}").json()
    assert body["status"] == "completed"
    assert body["result"] == result
    worker.process_audio.run(job_id)
    assert s3.download_file.call_count == 1


@pytest.mark.parametrize("filename,data,status", [("a.exe", b"x", 415), ("a.wav", b"", 400)])
def test_invalid_upload(setup, filename, data, status):
    client, _, s3, queue = setup
    assert client.post("/transcriptions", files={"file": (filename, data)}).status_code == status
    s3.put_object.assert_not_called()
    queue.assert_not_called()


def test_size_limit(setup, monkeypatch):
    monkeypatch.setattr(main.config, "MAX_UPLOAD_BYTES", 3)
    assert setup[0].post("/transcriptions", files={"file": ("a.wav", b"1234")}).status_code == 413


def test_queue_failure(setup):
    client, sessions, _, queue = setup
    queue.side_effect = RuntimeError("sensitive provider details")
    response = client.post("/transcriptions", files={"file": ("a.wav", b"x")})
    assert response.status_code == 503
    assert "sensitive" not in response.text
    with sessions() as db:
        assert db.query(Job).one().status == "failed"


def test_processing_failure(setup, monkeypatch):
    client, _, _, _ = setup
    job_id = client.post("/transcriptions", files={"file": ("a.wav", b"bad audio")}).json()[
        "job_id"
    ]
    monkeypatch.setattr(worker, "transcribe_audio", Mock(side_effect=ValueError("private path")))
    worker.process_audio.run(job_id)
    response = client.get(f"/transcriptions/{job_id}")
    assert response.json()["status"] == "failed"
    assert "private path" not in response.text


def test_unknown_job(setup):
    assert setup[0].get("/transcriptions/missing").status_code == 404


def test_audio_segments(monkeypatch):
    model = Mock()
    model.transcribe.return_value = (
        iter([SimpleNamespace(start=0, end=1.5, text=" hello ")]),
        SimpleNamespace(language="en"),
    )
    monkeypatch.setattr(audio, "get_model", lambda: model)
    assert audio.transcribe_audio("input.wav") == {
        "language": "en",
        "segments": [{"start": 0.0, "end": 1.5, "text": "hello"}],
    }
