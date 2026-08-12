import pytest
from fastapi.testclient import TestClient
from main import app
from app.api.auth import sessions, storage
from app.services.storage import StorageService


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions before each test"""
    sessions.clear()
    yield
    sessions.clear()


@pytest.fixture
def test_storage():
    """Create test storage instance"""
    storage = StorageService()
    # Clear existing test data
    if storage.get_user("test@example.com"):
        import os
        user_path = storage._get_user_path("test@example.com")
        if user_path.exists():
            os.remove(user_path)
    if storage.get_user("existing@example.com"):
        import os
        user_path = storage._get_user_path("existing@example.com")
        if user_path.exists():
            os.remove(user_path)
    return storage


def test_sign_in_new_user(test_storage):
    """Test signing in a new user creates an account"""
    response = client.post(
        "/api/auth/sign-in",
        json={"name": "Test User", "email": "test@example.com"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"
    assert data["user"]["projects"] == []
    
    # Verify user was created in storage
    user = test_storage.get_user("test@example.com")
    assert user is not None
    assert user["name"] == "Test User"


def test_sign_in_existing_user(test_storage):
    """Test signing in existing user loads their data"""
    # Create user first
    test_storage.create_user("existing@example.com", "Existing User")
    
    response = client.post(
        "/api/auth/sign-in",
        json={"name": "Updated Name", "email": "existing@example.com"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "existing@example.com"
    # Name should be updated
    assert data["user"]["name"] == "Updated Name"


def test_sign_in_invalid_email():
    """Test signing in with invalid email format"""
    response = client.post(
        "/api/auth/sign-in",
        json={"name": "Test User", "email": "invalid-email"}
    )
    
    assert response.status_code == 400
    assert "Invalid email format" in response.json()["detail"]


def test_sign_in_missing_fields():
    """Test signing in with missing required fields"""
    # Missing name
    response = client.post(
        "/api/auth/sign-in",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 422  # FastAPI validation error
    
    # Missing email
    response = client.post(
        "/api/auth/sign-in",
        json={"name": "Test User"}
    )
    assert response.status_code == 422  # FastAPI validation error


def test_sign_out(test_storage):
    """Test signing out removes session"""
    # Sign in first
    sign_in_response = client.post(
        "/api/auth/sign-in",
        json={"name": "Test User", "email": "test@example.com"}
    )
    session_token = sign_in_response.cookies.get("session_token")
    
    # Sign out
    response = client.post(
        "/api/auth/sign-out",
        cookies={"session_token": session_token}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Signed out successfully"
    
    # Session should be removed
    assert session_token not in sessions


def test_sign_out_without_session():
    """Test signing out without session token"""
    response = client.post("/api/auth/sign-out")
    
    assert response.status_code == 401
    assert "No session token provided" in response.json()["detail"]


def test_get_current_user_email():
    """Test getting current user from session"""
    from app.api.auth import get_current_user_email
    
    # Test with no token
    assert get_current_user_email(None) is None
    
    # Test with invalid token
    assert get_current_user_email("invalid_token") is None
    
    # Test with valid token
    sessions["valid_token"] = "user@example.com"
    assert get_current_user_email("valid_token") == "user@example.com"