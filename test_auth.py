#!/usr/bin/env python3
"""
Test script to verify authentication functionality
"""
from main import verify_password, get_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import User, Base
import os

def test_authentication():
    # Check which database is being used
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./attendance.db')
    print(f'Using database: {DATABASE_URL}')

    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if not DATABASE_URL.startswith('postgres') else {})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Check if users exist
    db = SessionLocal()
    try:
        # Find admin user specifically
        admin_user = db.query(User).filter(User.login == 'admin').first()
        if admin_user:
            print(f'Admin user found: {admin_user.full_name}')
            print(f'Login: {admin_user.login}')
            
            # Test password verification
            correct_password = "admin123"
            is_valid = verify_password(correct_password, admin_user.password_hash)
            print(f"Password verification for '{correct_password}': {is_valid}")
            
            wrong_password = "wrongpassword"
            is_invalid = verify_password(wrong_password, admin_user.password_hash)
            print(f"Password verification for '{wrong_password}': {is_invalid}")
            
            if is_valid and not is_invalid:
                print("✓ Authentication test PASSED")
            else:
                print("✗ Authentication test FAILED")
        else:
            print('No admin user found')
    finally:
        db.close()

if __name__ == "__main__":
    test_authentication()