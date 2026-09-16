from functools import lru_cache

from app.config import WHISPER_MODEL


@lru_cache(maxsize=1)
def get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe_audio(path: str) -> dict:
    # The model is loaded once per worker; segments are evaluated lazily.
    segments, info = get_model().transcribe(
        path, beam_size=5, temperature=0.0, condition_on_previous_text=False
    )
    return {
        "language": info.language,
        "segments": [
            {"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in segments
        ],
    }
