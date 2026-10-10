import pytest
from app import create_app
from app.database import db
from app.models.user import User
from app.utils.security import hash_password, check_password

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-secret"
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

def test_password_hashing():
    password = "supersecretpassword"
    hashed = hash_password(password)
    assert hashed != password
    assert check_password(password, hashed)
    assert not check_password("wrongpassword", hashed)

def test_register_success(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User"
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "User registered successfully"
    assert data["user"]["email"] == "test@example.com"
    # Ensure HttpOnly cookie is set
    cookies = response.headers.getlist('Set-Cookie')
    assert any("access_token=" in c and "HttpOnly" in c for c in cookies)

def test_register_duplicate_email(client):
    # First user
    client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123"
    })
    
    # Second user with same email
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "differentpassword"
    })
    assert response.status_code == 409
    assert response.get_json()["error"] == "An account with this email already exists"

def test_register_validation(client):
    # Missing email
    response = client.post("/api/v1/auth/register", json={
        "password": "password123"
    })
    assert response.status_code == 400
    
    # Short password
    response = client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "password": "short"
    })
    assert response.status_code == 400

def test_login_success(client):
    # Setup user
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "password123"
    })
    
    response = client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["email"] == "login@example.com"
    # Ensure HttpOnly cookie is set
    cookies = response.headers.getlist('Set-Cookie')
    assert any("access_token=" in c and "HttpOnly" in c for c in cookies)

def test_login_invalid_credentials(client):
    # Setup user
    client.post("/api/v1/auth/register", json={
        "email": "invalid@example.com",
        "password": "password123"
    })
    
    response = client.post("/api/v1/auth/login", json={
        "email": "invalid@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    
    # Unknown email
    response = client.post("/api/v1/auth/login", json={
        "email": "doesnotexist@example.com",
        "password": "password123"
    })
    assert response.status_code == 401

def test_logout(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    cookies = response.headers.getlist('Set-Cookie')
    assert any("access_token=" in c and "Expires=" in c for c in cookies) # Deleting cookie
