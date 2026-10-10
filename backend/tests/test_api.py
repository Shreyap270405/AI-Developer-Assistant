import pytest
from app import create_app
from app.database import db

@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "STORAGE_DIR": tmp_path / "storage"
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200

def login_user(client, email, password, full_name="User"):
    # Attempt to register first
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": full_name
    })
    # Login will set the cookie in the client
    return client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })

def test_project_lifecycle_and_ownership(client):
    # 1. Unauthenticated users cannot create projects
    res = client.post("/api/v1/projects", json={"name": "Fail"})
    assert res.status_code == 401

    # 2. Login User A
    login_user(client, "user_a@example.com", "password123")
    
    # 3. Create Project for User A
    res = client.post("/api/v1/projects", json={
        "name": "Project A",
        "description": "User A project"
    })
    assert res.status_code == 201
    proj_a_id = res.get_json()["project"]["id"]

    # 4. List Projects
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert len(res.get_json()["projects"]) == 1
    
    # 5. Rename Project A
    res = client.patch(f"/api/v1/projects/{proj_a_id}", json={
        "name": "Project A Renamed"
    })
    assert res.status_code == 200
    assert res.get_json()["project"]["name"] == "Project A Renamed"

    # 6. Logout User A
    client.post("/api/v1/auth/logout")

    # 7. Login User B
    login_user(client, "user_b@example.com", "password123")

    # 8. User B cannot see User A's project
    res = client.get("/api/v1/projects")
    assert len(res.get_json()["projects"]) == 0

    # 9. User B cannot get User A's project
    res = client.get(f"/api/v1/projects/{proj_a_id}")
    assert res.status_code == 403

    # 10. User B cannot rename User A's project
    res = client.patch(f"/api/v1/projects/{proj_a_id}", json={"name": "Hacked"})
    assert res.status_code == 403

    # 11. User B cannot delete User A's project
    res = client.delete(f"/api/v1/projects/{proj_a_id}")
    assert res.status_code == 403

    # 12. Logout User B, Login User A
    client.post("/api/v1/auth/logout")
    login_user(client, "user_a@example.com", "password123")

    # 13. User A deletes their project
    res = client.delete(f"/api/v1/projects/{proj_a_id}")
    assert res.status_code == 200

    # 14. Project A is gone
    res = client.get(f"/api/v1/projects/{proj_a_id}")
    assert res.status_code == 404
