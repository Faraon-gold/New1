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
        birth_date_ddl = "ALTER TABLE users ADD COLUMN birth_date DATE"
        direction_code_ddl = "ALTER TABLE users ADD COLUMN direction_code VARCHAR(32)"
        direction_name_ddl = "ALTER TABLE users ADD COLUMN direction_name VARCHAR(255)"
        faculty_ddl = "ALTER TABLE users ADD COLUMN faculty VARCHAR(255)"
        study_status_ddl = "ALTER TABLE users ADD COLUMN study_status VARCHAR(20) NOT NULL DEFAULT 'studying'"
        stream_year_ddl = "ALTER TABLE users ADD COLUMN stream_year VARCHAR(16)"
        education_form_ddl = "ALTER TABLE users ADD COLUMN education_form VARCHAR(64)"

        _add_column_if_missing(inspector, "users", "is_monitor", user_monitor_ddl)
        _add_column_if_missing(inspector, "subjects", "teacher_id", subject_teacher_ddl)
        _add_column_if_missing(inspector, "users", "email", email_ddl)
        _add_column_if_missing(inspector, "users", "personal_id", personal_id_ddl)
        _add_column_if_missing(inspector, "users", "birth_date", birth_date_ddl)
        _add_column_if_missing(inspector, "users", "direction_code", direction_code_ddl)
        _add_column_if_missing(inspector, "users", "direction_name", direction_name_ddl)
        _add_column_if_missing(inspector, "users", "faculty", faculty_ddl)
        _add_column_if_missing(inspector, "users", "study_status", study_status_ddl)
        _add_column_if_missing(inspector, "users", "stream_year", stream_year_ddl)
        _add_column_if_missing(inspector, "users", "education_form", education_form_ddl)

        if "group_subjects" not in inspector.get_table_names() and "groups" in inspector.get_table_names() and "subjects" in inspector.get_table_names():
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE group_subjects (group_id INTEGER NOT NULL, subject_id INTEGER NOT NULL, PRIMARY KEY (group_id, subject_id), FOREIGN KEY(group_id) REFERENCES groups (id), FOREIGN KEY(subject_id) REFERENCES subjects (id))"))

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
