import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect


def test_migration_roundtrip(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    env = dict(os.environ, DATABASE_URL=url)
    for command in (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head")):
        subprocess.run([sys.executable, "-m", "alembic", *command], env=env, check=True)
    engine = create_engine(url)
    assert {column["name"] for column in inspect(engine).get_columns("jobs")} == {
        "id",
        "status",
        "input_key",
        "result",
        "error",
    }
    engine.dispose()
