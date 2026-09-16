import os

os.environ.update(
    DATABASE_URL="sqlite://",
    REDIS_URL="redis://localhost:6379/0",
    S3_ENDPOINT="http://localhost:9000",
    S3_ACCESS_KEY="test",
    S3_SECRET_KEY="test",
)
