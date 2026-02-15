import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_compatible_schema() -> None:
    """Lightweight runtime migration for environments without Alembic."""
    try:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            return

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_monitor" in user_columns:
            return

        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text("ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT FALSE"))
            else:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT 0"))
    except Exception:
        # Ignore migration errors here; normal startup/table creation flow will continue.
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


ensure_compatible_schema()
