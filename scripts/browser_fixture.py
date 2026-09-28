"""Ephemeral browser test server. Refuses non-test or nonempty databases."""

import os
from pathlib import Path

import uvicorn
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from event_auth.adapters.crypto import Vault, pin_hash
from event_auth.adapters.database.models import Staff
from event_auth.adapters.database.session import Base, make_engine
from event_auth.api.app import create_app
from event_auth.config.settings import load_config
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    if make_url(url).database != "event_auth_test":
        raise ValueError("Refusing non-test database")
    engine = make_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        if any(
            db.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        ):
            raise ValueError("Browser test requires empty isolated test database")
    os.environ["EVENT_AUTH_COOKIE_SECURE"] = "false"
    os.environ["EVENT_AUTH_ORIGINS"] = "http://127.0.0.1:8765"
    try:
        with factory.begin() as db:
            db.add(Staff(username="test_browser", role="admin", pin_hash=pin_hash("123456")))
        app = create_app(
            sessions=factory,
            signer=Ed25519PrivateKey.generate(),
            vault=Vault(Fernet.generate_key()),
            config=load_config(Path("assets/config/customer_config.json")),
        )
        uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)
    finally:
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(delete(table))
        engine.dispose()


if __name__ == "__main__":
    main()
