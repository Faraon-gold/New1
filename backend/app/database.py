import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _add_column_if_missing(inspector, table_name: str, column_name: str, ddl: str) -> bool:
    if table_name not in inspector.get_table_names():
        return False

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return False

    with engine.begin() as connection:
        connection.execute(text(ddl))
    return True


def ensure_compatible_schema() -> None:
    """Lightweight runtime migration for environments without Alembic."""
    try:
        inspector = inspect(engine)
        dialect = engine.dialect.name

        user_monitor_ddl = (
            "ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT FALSE"
            if dialect == "postgresql"
            else "ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT 0"
        )
        subject_teacher_ddl = "ALTER TABLE subjects ADD COLUMN teacher_id INTEGER"

        _add_column_if_missing(inspector, "users", "is_monitor", user_monitor_ddl)
        _add_column_if_missing(inspector, "subjects", "teacher_id", subject_teacher_ddl)
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
