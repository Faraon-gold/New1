#!/usr/bin/env python3
"""
Test script to verify admin login credentials work properly
"""
import os
# Set the DATABASE_URL before importing modules that depend on it
os.environ["DATABASE_URL"] = "sqlite:///./attendance.db"

from backend.app.auth import verify_password, hash_password
from backend.app.models import User, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use the same database URL as in init_db.py
DATABASE_URL = "sqlite:///./attendance.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_password_hashing():
    """Test the password hashing and verification functions"""
    print("Testing password hashing functionality...")
    
    # Test with the admin credentials
    plain_password = "admin123"
    print(f"Plain password: {plain_password}")
    
    # Hash the password using the function from auth.py
    hashed_password = hash_password(plain_password)
    print(f"Hashed password: {hashed_password}")
    
    # Verify the password
    is_valid = verify_password(plain_password, hashed_password)
    print(f"Verification result: {is_valid}")
    
    return is_valid

def test_admin_exists():
    """Test if admin user exists in the database with correct credentials"""
    print("\nTesting if admin user exists in database...")
    
    db = SessionLocal()
    
    try:
        # Find admin user
        admin_user = db.query(User).filter(User.login == "admin").first()
        
        if admin_user:
            print(f"Admin user found: {admin_user.full_name} (ID: {admin_user.id})")
            print(f"Role: {admin_user.role}")
            
            # Verify the password
            is_correct_password = verify_password("admin123", admin_user.password_hash)
            print(f"Password verification for 'admin123': {is_correct_password}")
            
            # Try wrong password
            is_wrong_password = verify_password("wrongpassword", admin_user.password_hash)
            print(f"Password verification for 'wrongpassword': {is_wrong_password}")
            
            return is_correct_password
        else:
            print("Admin user not found!")
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    print("Running login tests...\n")
    
    # Test basic password functionality
    basic_test_passed = test_password_hashing()
    
    # Test admin user exists and has correct password
    admin_test_passed = test_admin_exists()
    
    print(f"\nBasic password test: {'PASSED' if basic_test_passed else 'FAILED'}")
    print(f"Admin user test: {'PASSED' if admin_test_passed else 'FAILED'}")
    
    if basic_test_passed and admin_test_passed:
        print("\nAll tests PASSED! Login should work correctly.")
    else:
        print("\nSome tests FAILED! There might be issues with login.")