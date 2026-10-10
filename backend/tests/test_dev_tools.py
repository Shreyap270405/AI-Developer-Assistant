import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from app import create_app
from app.database import db
from app.models.project import Project
from app.models.file_metadata import ProjectFile
from app.services.chunking_service import CodeChunk
from app.services.vector_service import VectorService
from app.services.dev_tools_service import DevToolsService, redact_secrets
from app.utils.security import create_access_token


@pytest.fixture
def app_and_client(tmp_path):
    storage_dir = tmp_path / "storage"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "STORAGE_DIR": storage_dir
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield app, client


@pytest.fixture
def auth_header_user1():
    token = create_access_token(user_id=1, email="user1@example.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_header_user2():
    token = create_access_token(user_id=2, email="user2@example.com")
    return {"Authorization": f"Bearer {token}"}


def _seed_project(user_id=1, name="DevTools Test Project", setup_files=True):
    from flask import current_app
    storage_base = Path(current_app.config.get("STORAGE_DIR"))

    project = Project(
        name=name,
        description="A sample repository for testing README, tests, review, and search",
        user_id=user_id,
        source_type="zip",
        storage_path="pending",
        status="ready"
    )
    db.session.add(project)
    db.session.flush()

    proj_dir = storage_base / f"proj_{project.id}"
    source_dir = proj_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "faiss_index").mkdir(parents=True, exist_ok=True)
    project.storage_path = str(proj_dir.as_posix())

    if setup_files:
        # Create sample files
        (source_dir / "requirements.txt").write_text("flask==3.0.0\npytest==8.0.0\nSQLAlchemy==2.0.0\n")
        (source_dir / "package.json").write_text('{"name": "sample-app", "scripts": {"test": "jest"}}\n')
        (source_dir / "main.py").write_text(
            "import os\n\ndef add_user(username, email):\n    if not username:\n        raise ValueError('Empty username')\n    return {'user': username, 'email': email}\n"
        )
        (source_dir / "config.py").write_text(
            "DATABASE_URL = 'mysql://user:secret123@localhost/db'\nSECRET_KEY = 'super_secret_token_12345'\n"
        )
        
        pf1 = ProjectFile(project_id=project.id, file_path="main.py", file_type="python", file_size=150, line_count=6)
        pf2 = ProjectFile(project_id=project.id, file_path="requirements.txt", file_type="text", file_size=40, line_count=3)
        db.session.add(pf1)
        db.session.add(pf2)

    db.session.commit()
    return project


def _seed_index(project_id: int):
    chunks = [
        CodeChunk(
            chunk_id=f"{project_id}_1",
            file_path="main.py",
            start_line=1,
            end_line=6,
            language="python",
            content="def add_user(username, email):\n    if not username:\n        raise ValueError('Empty username')\n    return {'user': username, 'email': email}",
            metadata={"file_path": "main.py", "start_line": 1, "end_line": 6, "project_id": project_id}
        )
    ]
    VectorService.build_and_save_index(project_id, chunks)


# ─── Feature 1: README & Documentation Generator Tests ───────────────────────

class TestReadmeGenerator:

    def test_secret_redaction_utility(self):
        text = "SECRET_KEY = 'super_secret_pass_123' and api_key='AIzaSyAbc1234567890123456789012345678'"
        redacted = redact_secrets(text)
        assert "super_secret_pass_123" not in redacted
        assert "AIzaSyAbc" not in redacted
        assert "[REDACTED_SECRET]" in redacted

    def test_generate_docs_fallback_when_unconfigured(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        with patch("app.services.gemini_service.GeminiService.is_configured", return_value=False):
            res = client.post(f"/api/v1/rag/{pid}/generate-docs", json={}, headers=auth_header_user1)
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert "markdown" in data
            assert proj.name in data["markdown"]
            assert "Python" in data["detected_stack"]
            assert "package.json" in data["evidence_files"]
            assert "requirements.txt" in data["evidence_files"]

    def test_generate_docs_with_mocked_gemini(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        mock_response = {
            "title": "DevTools Test Project",
            "purpose": "A production-grade Python and Node workspace.",
            "detected_stack": ["Python", "Flask", "Jest"],
            "markdown": "# DevTools Test Project\n\n## Purpose\nA verified test application.\n\n## Setup\n`pip install -r requirements.txt`\n\n## Environment\n`DATABASE_URL=[placeholder]`",
            "unknown_items": ["[Unknown: Production deployment cloud provider]"],
            "warnings": ["Secrets were masked prior to analysis."]
        }

        with patch("app.services.gemini_service.GeminiService.is_configured", return_value=True):
            with patch("app.services.gemini_service.GeminiService._call_gemini", return_value={"summary": json.dumps(mock_response), "raw_data": mock_response}):
                res = client.post(f"/api/v1/rag/{pid}/generate-docs", json={"custom_instructions": "Focus on setup"}, headers=auth_header_user1)
                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert "DevTools Test Project" in data["markdown"]

    def test_save_docs_endpoint(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(
            f"/api/v1/rag/{pid}/save-docs",
            json={"filename": "README.md", "content": "# Generated Documentation\n\nVerified project overview."},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["file_path"] == "README.md"
        assert data["line_count"] == 3

        with app.app_context():
            saved_file = Path(proj.storage_path) / "source" / "README.md"
            assert saved_file.exists()
            assert "Generated Documentation" in saved_file.read_text()
            db_file = ProjectFile.query.filter_by(project_id=pid, file_path="README.md").first()
            assert db_file is not None

    def test_generate_docs_forbidden_other_user(self, app_and_client, auth_header_user2):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(f"/api/v1/rag/{pid}/generate-docs", json={}, headers=auth_header_user2)
        assert res.status_code == 403


# ─── Feature 2: Test-Case Generator Tests ────────────────────────────────────

class TestTestGenerator:

    def test_framework_detection_pytest(self, app_and_client):
        app, _ = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            framework = DevToolsService._detect_test_framework(proj.id, "python")
            assert framework == "pytest"

    def test_generate_tests_endpoint_success(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        mock_payload = {
            "framework": "pytest",
            "suggested_file_name": "test_main.py",
            "test_code": "import pytest\nfrom main import add_user\n\ndef test_add_user_happy_path():\n    assert add_user('alice', 'a@t.com')['user'] == 'alice'\n\ndef test_add_user_empty():\n    with pytest.raises(ValueError):\n        add_user('', 'a@t.com')\n",
            "test_cases": [
                {"name": "test_add_user_happy_path", "type": "happy_path", "description": "Returns dictionary for valid user"},
                {"name": "test_add_user_empty", "type": "edge_case", "description": "Raises ValueError when username is empty"}
            ],
            "assumptions_warnings": ["Tests are static suggestions and have not been executed."]
        }

        with patch("app.services.gemini_service.GeminiService.is_configured", return_value=True):
            with patch("app.services.gemini_service.GeminiService._call_gemini", return_value={"summary": json.dumps(mock_payload), "raw_data": mock_payload}):
                res = client.post(
                    f"/api/v1/rag/{pid}/generate-tests",
                    json={"file_path": "main.py", "function_name": "add_user"},
                    headers=auth_header_user1
                )
                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["framework"] == "pytest"
                assert "test_code" in data
                assert len(data["test_cases"]) > 0
                assert any("not been executed" in w.lower() for w in data["assumptions_warnings"])

    def test_generate_tests_missing_input_validation(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(f"/api/v1/rag/{pid}/generate-tests", json={}, headers=auth_header_user1)
        assert res.status_code == 400
        assert res.get_json()["error_code"] == "validation_error"


# ─── Feature 3: AI Code Review Tests ──────────────────────────────────────────

class TestCodeReview:

    def test_code_review_heuristic_fallback(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        code_with_smell = "def run_dynamic(cmd):\n    eval(cmd)\n"
        with patch("app.services.gemini_service.GeminiService.is_configured", return_value=False):
            res = client.post(
                f"/api/v1/rag/{pid}/review",
                json={"code": code_with_smell},
                headers=auth_header_user1
            )
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert len(data["findings"]) > 0
            crit = data["findings"][0]
            assert crit["severity"] == "critical"
            assert crit["category"] == "security"
            assert crit["is_verified"] is True
            assert crit["line_range"]["start_line"] == 2

    def test_code_review_mocked_gemini_structured(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        mock_review = {
            "summary": "Overall code is well structured with clear input validation.",
            "score": 90,
            "findings": [
                {
                    "id": "FINDING-1",
                    "severity": "suggestion",
                    "category": "maintainability",
                    "title": "Missing type annotations",
                    "file_path": "main.py",
                    "line_range": {"start_line": 3, "end_line": 3},
                    "is_verified": True,
                    "explanation": "Function add_user lacks type hints for username and email.",
                    "suggested_remediation": "def add_user(username: str, email: str) -> dict:"
                }
            ],
            "assumptions_warnings": ["Review is based on static analysis."]
        }

        with patch("app.services.gemini_service.GeminiService.is_configured", return_value=True):
            with patch("app.services.gemini_service.GeminiService._call_gemini", return_value={"summary": json.dumps(mock_review), "raw_data": mock_review}):
                res = client.post(
                    f"/api/v1/rag/{pid}/review",
                    json={"file_path": "main.py"},
                    headers=auth_header_user1
                )
                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["score"] == 90
                assert len(data["findings"]) == 1
                assert data["findings"][0]["is_verified"] is True
                assert data["findings"][0]["line_range"]["start_line"] == 3


# ─── Feature 4: Semantic Codebase Search Tests ───────────────────────────────

class TestSemanticSearch:

    def test_semantic_search_unindexed_project(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(
            f"/api/v1/rag/{pid}/search",
            json={"query": "where is user authentication?"},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "not_indexed"
        assert data["count"] == 0
        assert "not been indexed" in data["message"].lower()

    def test_semantic_search_with_indexed_data(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id
            _seed_index(pid)

        res = client.post(
            f"/api/v1/rag/{pid}/search",
            json={"query": "function that adds a user"},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "success"
        assert data["count"] > 0
        first = data["results"][0]
        assert first["file_path"] == "main.py"
        assert first["start_line"] == 1
        assert first["end_line"] == 6
        assert "add_user" in first["snippet"]
        assert "relevance_percentage" in first

    def test_semantic_search_empty_query(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(f"/api/v1/rag/{pid}/search", json={"query": "   "}, headers=auth_header_user1)
        assert res.status_code == 400
        assert res.get_json()["error_code"] == "validation_error"

    def test_semantic_search_project_isolation(self, app_and_client, auth_header_user2):
        app, client = app_and_client
        with app.app_context():
            proj = _seed_project(user_id=1)
            pid = proj.id

        res = client.post(
            f"/api/v1/rag/{pid}/search",
            json={"query": "where is user authentication?"},
            headers=auth_header_user2
        )
        assert res.status_code == 403
