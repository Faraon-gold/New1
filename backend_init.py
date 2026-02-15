#!/usr/bin/env python3
"""
Initialize the backend database with sample data including admin user
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set the DATABASE_URL environment variable before importing database modules
os.environ.setdefault("DATABASE_URL", "sqlite:///./attendance.db")

# Add the backend app directory to the path so we can import from it
sys.path.append('/workspace/backend/app')

# Import from the backend app modules
from backend.app.models import User, Group, Subject, Base
from backend.app.database import DATABASE_URL as DB_URL
from backend.app.auth import hash_password


def init_backend_database():
    """Initialize the database with sample data"""
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.login == "admin").first()
        if not admin_user:
            # Create admin user
            admin = User(
                full_name="Админ Администратов",
                login="admin",
                password_hash=hash_password("admin123"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("Admin user created successfully!")
        else:
            print("Admin user already exists!")
        
        # Check if other essential data exists
        if not db.query(Group).count():
            # Create some sample groups
            group1 = Group(name="ИС-201")
            group2 = Group(name="ИС-202")
            db.add(group1)
            db.add(group2)
            db.commit()
            print("Sample groups created!")
        
        if not db.query(Subject).count():
            # Create some sample subjects
            subject1 = Subject(name="Математический анализ")
            subject2 = Subject(name="Программирование")
            db.add(subject1)
            db.add(subject2)
            db.commit()
            print("Sample subjects created!")
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_backend_database()
    print("Database initialization completed!")