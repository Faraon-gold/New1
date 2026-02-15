#!/usr/bin/env python3
"""Initialize the backend database with baseline data and safe DB retries."""

from __future__ import annotations

import os
import time
from typing import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.auth import hash_password
from backend.app.models import Base, Group, Subject, User

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
MAX_DB_RETRIES = int(os.getenv("DB_INIT_MAX_RETRIES", "30"))
DB_RETRY_DELAY_SECONDS = float(os.getenv("DB_INIT_RETRY_DELAY", "2"))


def wait_for_database(engine_factory: Callable[[], object]) -> object:
    """Wait until the database is ready to accept SQL queries."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_DB_RETRIES + 1):
        engine = engine_factory()
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            if attempt > 1:
                print(f"Database became available on attempt {attempt}/{MAX_DB_RETRIES}.")
            return engine
        except OperationalError as exc:
            last_error = exc
            print(
                f"Database is not ready yet (attempt {attempt}/{MAX_DB_RETRIES}): {exc}. "
                f"Retrying in {DB_RETRY_DELAY_SECONDS} sec..."
            )
            time.sleep(DB_RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Database is not ready after {MAX_DB_RETRIES} attempts."
    ) from last_error


def ensure_admin_user(db: Session) -> None:
    if db.query(User).filter(User.login == "admin").first():
        print("Admin user already exists.")
        return

    admin = User(
        full_name="Админ Администратов",
        login="admin",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    db.add(admin)
    db.commit()
    print("Admin user created successfully.")


def ensure_seed_data(db: Session) -> None:
    if db.query(Group).count() == 0:
        db.add_all([Group(name="ИС-201"), Group(name="ИС-202")])
        db.commit()
        print("Sample groups created.")

    if db.query(Subject).count() == 0:
        db.add_all([
            Subject(name="Математический анализ"),
            Subject(name="Программирование"),
        ])
        db.commit()
        print("Sample subjects created.")


def init_backend_database() -> None:
    engine = wait_for_database(lambda: create_engine(DATABASE_URL, pool_pre_ping=True))
    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    try:
        ensure_admin_user(db)
        ensure_seed_data(db)
    except Exception as exc:  # runtime safety for startup initialization
        db.rollback()
        raise RuntimeError(f"Error initializing database: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    init_backend_database()
    print("Database initialization completed.")
