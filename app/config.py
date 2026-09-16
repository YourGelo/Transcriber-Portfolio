import os

from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_BUCKET = os.getenv("S3_BUCKET", "audio")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
