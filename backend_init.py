#!/usr/bin/env python3
"""Initialize the backend database with baseline data and safe DB retries."""

from __future__ import annotations

import os
import time
from typing import Callable

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.auth import hash_password
from backend.app.models import Base, Group, Subject, User

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
MAX_DB_RETRIES = int(os.getenv("DB_INIT_MAX_RETRIES", "30"))
DB_RETRY_DELAY_SECONDS = float(os.getenv("DB_INIT_RETRY_DELAY", "2"))


def wait_for_database(engine_factory: Callable[[], object]) -> object:
    last_error: Exception | None = None
    for attempt in range(1, MAX_DB_RETRIES + 1):
        engine = engine_factory()
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return engine
        except OperationalError as exc:
            last_error = exc
            print(f"Database is not ready yet (attempt {attempt}/{MAX_DB_RETRIES}): {exc}. Retrying...")
            time.sleep(DB_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Database is not ready after {MAX_DB_RETRIES} attempts.") from last_error


def ensure_schema_updates(engine) -> None:
    inspector = inspect(engine)
    dialect = engine.dialect.name

    if "group_subjects" not in inspector.get_table_names() and "groups" in inspector.get_table_names() and "subjects" in inspector.get_table_names():
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE group_subjects (group_id INTEGER NOT NULL, subject_id INTEGER NOT NULL, PRIMARY KEY (group_id, subject_id), FOREIGN KEY(group_id) REFERENCES groups (id), FOREIGN KEY(subject_id) REFERENCES subjects (id))"))

    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "is_monitor" not in user_columns:
                if dialect == "postgresql":
                    connection.execute(text("ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT FALSE"))
                else:
                    connection.execute(text("ALTER TABLE users ADD COLUMN is_monitor BOOLEAN NOT NULL DEFAULT 0"))
            if "email" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
            if "personal_id" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN personal_id VARCHAR(64)"))
            if "birth_date" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN birth_date DATE"))
            if "direction_code" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN direction_code VARCHAR(32)"))
            if "direction_name" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN direction_name VARCHAR(255)"))
            if "faculty" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN faculty VARCHAR(255)"))
            if "study_status" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN study_status VARCHAR(20) NOT NULL DEFAULT 'studying'"))

            if dialect == "postgresql":
                connection.execute(text("UPDATE users SET personal_id = 'U-' || id::text WHERE personal_id IS NULL OR personal_id = ''"))
            else:
                connection.execute(text("UPDATE users SET personal_id = 'U-' || CAST(id AS TEXT) WHERE personal_id IS NULL OR personal_id = ''"))

    if "subjects" in inspector.get_table_names():
        subject_columns = {column["name"] for column in inspector.get_columns("subjects")}
        if "teacher_id" not in subject_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE subjects ADD COLUMN teacher_id INTEGER"))


def ensure_default_group(db: Session) -> Group:
    group = db.query(Group).filter(Group.name == "0").first()
    if group:
        return group
    group = Group(name="0")
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def ensure_admin_user(db: Session) -> None:
    default_group = ensure_default_group(db)
    if db.query(User).filter(User.login == "admin").first():
        return

    admin = User(
        full_name="Админ Администратов",
        login="admin",
        password_hash=hash_password("admin123"),
        role="admin",
        group_id=default_group.id,
        personal_id="U-admin",
    )
    db.add(admin)
    db.commit()


def ensure_seed_data(db: Session) -> None:
    ensure_default_group(db)
    if db.query(Group).count() == 1:
        db.add_all([Group(name="201"), Group(name="202")])
        db.commit()

    if db.query(Subject).count() == 0:
        db.add_all([
            Subject(name="Математический анализ"),
            Subject(name="Программирование"),
        ])
        db.commit()


def init_backend_database() -> None:
    engine = wait_for_database(lambda: create_engine(DATABASE_URL, pool_pre_ping=True))
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates(engine)

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        ensure_admin_user(db)
        ensure_seed_data(db)
    except Exception as exc:
        db.rollback()
        raise RuntimeError(f"Error initializing database: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    init_backend_database()
    print("Database initialization completed.")
