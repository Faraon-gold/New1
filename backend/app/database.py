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
        email_ddl = "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
        personal_id_ddl = "ALTER TABLE users ADD COLUMN personal_id VARCHAR(64)"

        _add_column_if_missing(inspector, "users", "is_monitor", user_monitor_ddl)
        _add_column_if_missing(inspector, "subjects", "teacher_id", subject_teacher_ddl)
        _add_column_if_missing(inspector, "users", "email", email_ddl)
        added_pid = _add_column_if_missing(inspector, "users", "personal_id", personal_id_ddl)

        if "users" in inspector.get_table_names():
            with engine.begin() as connection:
                if dialect == "postgresql":
                    connection.execute(text("UPDATE users SET personal_id = 'U-' || id::text WHERE personal_id IS NULL OR personal_id = ''"))
                else:
                    connection.execute(text("UPDATE users SET personal_id = 'U-' || CAST(id AS TEXT) WHERE personal_id IS NULL OR personal_id = ''"))
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


ensure_compatible_schema()
