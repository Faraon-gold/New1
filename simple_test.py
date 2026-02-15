#!/usr/bin/env python3
"""
Simple test script to verify admin login credentials work properly
by directly querying the SQLite database
"""
import sqlite3
import hashlib
from backend.app.auth import verify_password, hash_password

def test_admin_user_in_db():
    """Directly check the SQLite database for the admin user"""
    print("Checking SQLite database for admin user...")
    
    try:
        conn = sqlite3.connect('./attendance.db')
        cursor = conn.cursor()
        
        # Query the users table for admin
        cursor.execute("SELECT id, full_name, login, password_hash, role FROM users WHERE login = ?", ("admin",))
        result = cursor.fetchone()
        
        if result:
            user_id, full_name, login, password_hash, role = result
            print(f"Admin user found:")
            print(f"  ID: {user_id}")
            print(f"  Full Name: {full_name}")
            print(f"  Login: {login}")
            print(f"  Role: {role}")
            print(f"  Password hash: {password_hash[:50]}...")  # Show first 50 chars
            
            # Test the password verification
            is_correct = verify_password("admin123", password_hash)
            print(f"Password verification for 'admin123': {is_correct}")
            
            # Test wrong password
            is_wrong = verify_password("wrongpassword", password_hash)
            print(f"Password verification for 'wrongpassword': {is_wrong}")
            
            conn.close()
            return is_correct
        else:
            print("Admin user not found in database!")
            conn.close()
            return False
            
    except Exception as e:
        print(f"Error accessing database: {e}")
        return False

def test_password_functions():
    """Test the password hashing and verification functions"""
    print("\nTesting password functions...")
    
    password = "admin123"
    print(f"Original password: {password}")
    
    # Hash the password
    hashed = hash_password(password)
    print(f"Hashed password: {hashed[:50]}...")  # Show first 50 chars
    
    # Verify the password
    is_valid = verify_password(password, hashed)
    print(f"Verification result: {is_valid}")
    
    return is_valid

if __name__ == "__main__":
    print("Running simple login tests...\n")
    
    # Test password functions
    func_test = test_password_functions()
    
    # Test admin user in database
    db_test = test_admin_user_in_db()
    
    print(f"\nFunction test: {'PASSED' if func_test else 'FAILED'}")
    print(f"Database test: {'PASSED' if db_test else 'FAILED'}")
    
    if func_test and db_test:
        print("\nSUCCESS: Admin login should work correctly!")
    else:
        print("\nFAILURE: There are issues with login functionality.")