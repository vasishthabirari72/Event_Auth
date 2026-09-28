import os

from alembic import context
from event_auth.adapters.database import models  # noqa: F401
from event_auth.adapters.database.session import Base, make_engine


def run() -> None:
    url = os.environ["DATABASE_URL"]
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run()
