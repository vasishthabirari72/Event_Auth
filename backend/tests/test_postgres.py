import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from event_auth.adapters.database.session import make_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url


@pytest.mark.postgres
def test_postgresql_connection():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    assert make_url(url).database == "event_auth_test", "Refusing non-test database"
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "event_auth_test"
            expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected
    finally:
        engine.dispose()
