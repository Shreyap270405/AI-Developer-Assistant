"""
Test suite for ZIP upload, file ingestion, security safeguards,
listing, retrieval, and authorization enforcement.

All tests run against an in-memory SQLite database and a tmp_path
storage directory — no real MySQL or secrets required.
"""
import io
import os
import zipfile
import pytest

from app import create_app
from app.database import db as _db
from app.services.ingestion_service import IngestionService, IngestionError, MAX_ARCHIVE_ENTRIES


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "STORAGE_DIR": tmp_path / "storage",
    })
    with app.test_client() as client:
        with app.app_context():
            _db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, email, password="password123", name="Test User"):
    """Helper: register + login, returning the authenticated client (cookies set)."""
    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": name})
    client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return client


def _create_project(client, name="Test Project"):
    res = client.post("/api/v1/projects", json={"name": name, "description": "test"})
    assert res.status_code == 201, res.get_json()
    return res.get_json()["project"]


def _make_zip(files: dict) -> bytes:
    """
    Build an in-memory ZIP archive.
    files = {"relative/path.py": b"content", ...}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _upload(client, project_id, zip_bytes, filename="project.zip"):
    return client.post(
        f"/api/v1/files/{project_id}/upload",
        data={"file": (io.BytesIO(zip_bytes), filename)},
        content_type="multipart/form-data",
    )


# ─── Authentication ────────────────────────────────────────────────────────────

class TestAuthentication:
    def test_upload_requires_auth(self, client):
        res = _upload(client, 99, _make_zip({"main.py": b"x = 1"}))
        assert res.status_code == 401

    def test_list_files_requires_auth(self, client):
        res = client.get("/api/v1/files/99/files")
        assert res.status_code == 401

    def test_tree_requires_auth(self, client):
        res = client.get("/api/v1/files/99/tree")
        assert res.status_code == 401

    def test_content_requires_auth(self, client):
        res = client.get("/api/v1/files/99/content?path=main.py")
        assert res.status_code == 401


# ─── Ownership enforcement ────────────────────────────────────────────────────

class TestOwnership:
    def test_user_cannot_upload_to_other_project(self, client):
        _register_and_login(client, "owner@x.com")
        proj = _create_project(client, "Owner Project")
        client.post("/api/v1/auth/logout")

        _register_and_login(client, "attacker@x.com")
        res = _upload(client, proj["id"], _make_zip({"evil.py": b"pass"}))
        assert res.status_code == 403

    def test_user_cannot_list_files_of_other_project(self, client):
        _register_and_login(client, "ownerb@x.com")
        proj = _create_project(client, "Project B")
        client.post("/api/v1/auth/logout")

        _register_and_login(client, "attackerb@x.com")
        res = client.get(f"/api/v1/files/{proj['id']}/files")
        assert res.status_code == 403

    def test_user_cannot_read_file_from_other_project(self, client):
        _register_and_login(client, "ownerc@x.com")
        proj = _create_project(client, "Project C")
        zip_bytes = _make_zip({"secret.py": b"API_KEY = 'abc'"})
        _upload(client, proj["id"], zip_bytes)
        client.post("/api/v1/auth/logout")

        _register_and_login(client, "attackerc@x.com")
        res = client.get(f"/api/v1/files/{proj['id']}/content?path=secret.py")
        assert res.status_code == 403


# ─── Valid upload ─────────────────────────────────────────────────────────────

class TestValidUpload:
    def test_basic_zip_upload_succeeds(self, client):
        _register_and_login(client, "dev@x.com")
        proj = _create_project(client, "Basic")
        zip_bytes = _make_zip({
            "main.py": b"def hello(): return 'hi'",
            "utils/helpers.js": b"const greet = () => 'hi';",
            "README.md": b"# My Project",
        })
        res = _upload(client, proj["id"], zip_bytes)
        assert res.status_code == 200
        data = res.get_json()
        assert data["file_count"] == 3
        assert data["status"] == "ready"

    def test_file_list_reflects_upload(self, client):
        _register_and_login(client, "dev2@x.com")
        proj = _create_project(client, "List Test")
        zip_bytes = _make_zip({
            "app.py": b"print('hello')",
            "lib/utils.py": b"pass",
        })
        _upload(client, proj["id"], zip_bytes)

        res = client.get(f"/api/v1/files/{proj['id']}/files")
        assert res.status_code == 200
        files = res.get_json()["files"]
        paths = [f["file_path"] for f in files]
        assert "app.py" in paths
        assert "lib/utils.py" in paths

    def test_file_tree_reflects_structure(self, client):
        _register_and_login(client, "dev3@x.com")
        proj = _create_project(client, "Tree Test")
        zip_bytes = _make_zip({
            "src/index.py": b"x=1",
            "src/utils/helpers.py": b"y=2",
        })
        _upload(client, proj["id"], zip_bytes)

        res = client.get(f"/api/v1/files/{proj['id']}/tree")
        assert res.status_code == 200
        tree = res.get_json()["tree"]
        assert len(tree) > 0  # not empty

    def test_file_content_retrieval(self, client):
        _register_and_login(client, "dev4@x.com")
        proj = _create_project(client, "Content Test")
        zip_bytes = _make_zip({"main.py": b"result = 42"})
        _upload(client, proj["id"], zip_bytes)

        res = client.get(f"/api/v1/files/{proj['id']}/content?path=main.py")
        assert res.status_code == 200
        data = res.get_json()
        assert "result = 42" in data["content"]
        assert data["language"] == "python"
        assert data["path"] == "main.py"

    def test_file_metadata_stored_correctly(self, client):
        _register_and_login(client, "dev5@x.com")
        proj = _create_project(client, "Meta Test")
        code = b"# hello world\nprint('test')\n"
        zip_bytes = _make_zip({"hello.py": code})
        _upload(client, proj["id"], zip_bytes)

        res = client.get(f"/api/v1/files/{proj['id']}/files")
        files = res.get_json()["files"]
        f = next(x for x in files if x["file_path"] == "hello.py")
        assert f["file_type"] == "python"
        assert f["file_size"] == len(code)
        assert f["line_count"] == 2
        assert len(f["content_hash"]) == 64  # SHA-256 hex

    def test_duplicate_upload_updates_records(self, client):
        """Uploading the same archive twice should not create duplicate DB rows."""
        _register_and_login(client, "dev6@x.com")
        proj = _create_project(client, "Dup Test")
        zip_bytes = _make_zip({"app.py": b"v = 1"})

        _upload(client, proj["id"], zip_bytes)
        _upload(client, proj["id"], zip_bytes)

        res = client.get(f"/api/v1/files/{proj['id']}/files")
        files = res.get_json()["files"]
        app_files = [f for f in files if f["file_path"] == "app.py"]
        assert len(app_files) == 1  # no duplicates


# ─── Security safeguards ──────────────────────────────────────────────────────

class TestSecuritySafeguards:
    def test_non_zip_file_rejected(self, client):
        _register_and_login(client, "sec1@x.com")
        proj = _create_project(client, "Sec Test 1")
        res = client.post(
            f"/api/v1/files/{proj['id']}/upload",
            data={"file": (io.BytesIO(b"#!/bin/bash\nrm -rf /"), "script.sh")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400

    def test_path_traversal_in_zip_rejected(self, client, app):
        """A zip containing ../../etc/passwd-style paths must not extract outside sandbox."""
        _register_and_login(client, "sec2@x.com")
        proj = _create_project(client, "Traversal Test")

        # Craft a traversal ZIP using zipfile directly (bypass validate_zip)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # This would be traversal if not sanitized
            zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
        zip_bytes = buf.getvalue()

        # validate_zip will catch the '..' component
        res = _upload(client, proj["id"], zip_bytes)
        assert res.status_code == 422
        assert "traversal" in res.get_json()["error"].lower()

    def test_absolute_path_in_zip_rejected(self, client):
        _register_and_login(client, "sec3@x.com")
        proj = _create_project(client, "Abs Path Test")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("/etc/cron.d/evil", "* * * * * root id")
        zip_bytes = buf.getvalue()

        res = _upload(client, proj["id"], zip_bytes)
        assert res.status_code == 422
        assert "absolute" in res.get_json()["error"].lower()

    def test_zip_bomb_entry_count_rejected(self):
        """validate_zip must reject archives exceeding MAX_ARCHIVE_ENTRIES."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for i in range(MAX_ARCHIVE_ENTRIES + 1):
                zf.writestr(f"file_{i}.txt", "x")
        buf.seek(0)

        import tempfile, pathlib
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = pathlib.Path(tmp.name)

        with pytest.raises(IngestionError, match="too many entries"):
            IngestionService.validate_zip(tmp_path)
        tmp_path.unlink(missing_ok=True)

    def test_excluded_directories_not_stored(self, client):
        """node_modules, .git, __pycache__ etc. must be excluded."""
        _register_and_login(client, "sec4@x.com")
        proj = _create_project(client, "Exclude Test")
        zip_bytes = _make_zip({
            "src/app.py": b"x = 1",
            "node_modules/lodash/index.js": b"module.exports = {}",
            ".git/config": b"[core]",
            "__pycache__/app.cpython-312.pyc": b"\x00\x00binary",
            "venv/lib/python3.11/os.py": b"# stdlib",
        })
        res = _upload(client, proj["id"], zip_bytes)
        assert res.status_code == 200

        files = client.get(f"/api/v1/files/{proj['id']}/files").get_json()["files"]
        paths = [f["file_path"] for f in files]
        assert "src/app.py" in paths
        assert not any("node_modules" in p for p in paths)
        assert not any(".git" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)
        assert not any("venv" in p for p in paths)

    def test_secret_files_excluded(self, client):
        """Files matching secret patterns (.env, credentials, etc.) must not be stored."""
        _register_and_login(client, "sec5@x.com")
        proj = _create_project(client, "Secrets Test")
        zip_bytes = _make_zip({
            "main.py": b"print('ok')",
            ".env": b"SECRET_KEY=abc123",
            ".env.production": b"DB_PASS=hunter2",
            "config/credentials.json": b'{"token": "secret"}',
        })
        _upload(client, proj["id"], zip_bytes)

        files = client.get(f"/api/v1/files/{proj['id']}/files").get_json()["files"]
        paths = [f["file_path"] for f in files]
        assert "main.py" in paths
        assert ".env" not in paths
        assert ".env.production" not in paths
        assert not any("credentials" in p.lower() for p in paths)

    def test_path_traversal_content_request_rejected(self, client):
        """GET /content?path=../../etc/passwd must be rejected."""
        _register_and_login(client, "sec6@x.com")
        proj = _create_project(client, "Content Traversal Test")
        zip_bytes = _make_zip({"legit.py": b"x=1"})
        _upload(client, proj["id"], zip_bytes)

        res = client.get(
            f"/api/v1/files/{proj['id']}/content?path=../../etc/passwd"
        )
        assert res.status_code == 404

    def test_missing_file_field_rejected(self, client):
        _register_and_login(client, "sec7@x.com")
        proj = _create_project(client, "No File Test")
        res = client.post(
            f"/api/v1/files/{proj['id']}/upload",
            data={},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400

    def test_invalid_zip_bytes_rejected(self, client):
        """Garbage bytes that are not a valid ZIP must be rejected."""
        _register_and_login(client, "sec8@x.com")
        proj = _create_project(client, "Garbage Zip Test")
        res = _upload(client, proj["id"], b"not a zip at all", "fake.zip")
        assert res.status_code == 422

    def test_binary_files_not_stored(self, client):
        """Binary files (containing null bytes) must be filtered out."""
        _register_and_login(client, "sec9@x.com")
        proj = _create_project(client, "Binary Test")
        zip_bytes = _make_zip({
            "app.py": b"print('hello')",
            "image.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00",
        })
        _upload(client, proj["id"], zip_bytes)

        files = client.get(f"/api/v1/files/{proj['id']}/files").get_json()["files"]
        paths = [f["file_path"] for f in files]
        assert "app.py" in paths
        assert "image.png" not in paths
