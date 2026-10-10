import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from app import create_app
from app.database import db
from app.config import Config
from app.models.project import Project
from app.models.conversation import Conversation, Message, MessageCitation
from app.services.chunking_service import CodeChunk
from app.services.vector_service import VectorService
from app.services.rag_service import RAGService
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


def _seed_project(user_id=1, name="Test Backend Project"):
    from flask import current_app
    storage_base = Path(current_app.config.get("STORAGE_DIR") or Config.STORAGE_DIR)
    
    project = Project(
        name=name,
        description="A test project for RAG retrieval",
        user_id=user_id,
        source_type="zip",
        storage_path="pending",
        status="ready"
    )
    db.session.add(project)
    db.session.flush()

    proj_dir = storage_base / f"proj_{project.id}"
    (proj_dir / "source").mkdir(parents=True, exist_ok=True)
    (proj_dir / "faiss_index").mkdir(parents=True, exist_ok=True)
    project.storage_path = str(proj_dir.as_posix())
    db.session.commit()
    return project


def _seed_index(project_id: int):
    chunks = [
        CodeChunk(
            chunk_id=f"{project_id}_1",
            file_path="src/auth/service.py",
            start_line=10,
            end_line=25,
            language="python",
            content="def authenticate_user(email, password):\n    # Verify password hash\n    return generate_jwt_token(email)",
            metadata={"file_path": "src/auth/service.py", "start_line": 10, "end_line": 25, "project_id": project_id}
        ),
        CodeChunk(
            chunk_id=f"{project_id}_2",
            file_path="src/db/connection.py",
            start_line=1,
            end_line=15,
            language="python",
            content="def get_database_connection():\n    # Connect to MySQL pool\n    return pool.get_connection()",
            metadata={"file_path": "src/db/connection.py", "start_line": 1, "end_line": 15, "project_id": project_id}
        )
    ]
    VectorService.build_and_save_index(project_id, chunks)


class TestRAGRetrievalAndWorkflow:
    """Test suite for RAG retrieval pipeline, Gemini generation, and authorization."""

    def test_unauthenticated_query_fails(self, app_and_client):
        _, client = app_and_client
        res = client.post("/api/v1/rag/1/query", json={"question": "Where is auth?"})
        assert res.status_code == 401

    def test_unauthorized_user_cannot_query_project(self, app_and_client, auth_header_user2):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        res = client.post(
            f"/api/v1/rag/{project_id}/query",
            json={"question": "How does auth work?"},
            headers=auth_header_user2
        )
        assert res.status_code == 403

    def test_nonexistent_project_returns_404(self, app_and_client, auth_header_user1):
        _, client = app_and_client
        res = client.post(
            "/api/v1/rag/9999/query",
            json={"question": "How does auth work?"},
            headers=auth_header_user1
        )
        assert res.status_code == 404

    def test_empty_question_returns_400(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        res = client.post(
            f"/api/v1/rag/{project_id}/query",
            json={"question": "   "},
            headers=auth_header_user1
        )
        assert res.status_code == 400
        assert "Question is required" in res.get_json()["error"]

    def test_unindexed_project_returns_clear_guidance(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        res = client.post(
            f"/api/v1/rag/{project_id}/query",
            json={"question": "Explain the auth logic"},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "Not Indexed" in data["answer"]
        assert len(data["citations"]) == 0

    def test_successful_end_to_end_rag_mocked_gemini(self, app_and_client, auth_header_user1):
        app, client = app_and_client

        mock_gemini_response = MagicMock()
        mock_gemini_response.text = (
            "Authentication is handled in `src/auth/service.py` [src/auth/service.py:10-25] "
            "using `authenticate_user` which validates passwords and issues JWTs."
        )

        from app.services.vector_service import LocalDeterministicEmbeddings
        with patch.object(Config, "GEMINI_API_KEY", "AIzaFakeKey123"):
            with patch("app.services.vector_service.VectorService.get_embeddings", return_value=LocalDeterministicEmbeddings()):
                with app.app_context():
                    project = _seed_project(user_id=1)
                    project_id = project.id
                    _seed_index(project_id)

                with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                    mock_client = MagicMock()
                    mock_client.models.generate_content.return_value = mock_gemini_response
                    mock_get_client.return_value = mock_client

                    res = client.post(
                        f"/api/v1/rag/{project_id}/query",
                        json={"question": "How does user authentication work?"},
                        headers=auth_header_user1
                    )

                    assert res.status_code == 200
                    data = res.get_json()
                    assert "Authentication is handled" in data["answer"]
                    assert data["retrieved_chunks_count"] > 0
                    assert len(data["citations"]) > 0

                    citation = data["citations"][0]
                    assert "file_path" in citation
                    assert "start_line" in citation
                    assert "end_line" in citation
                    assert "snippet" in citation
                    assert citation["file_path"] in ["src/auth/service.py", "src/db/connection.py"]

                    # Verify conversation persistence
                    with app.app_context():
                        conv = db.session.get(Conversation, data["conversation_id"])
                        assert conv is not None
                        assert conv.user_id == 1
                        assert conv.project_id == project_id
                        messages = list(conv.messages)
                        assert len(messages) == 2
                        assert messages[0].role == "user"
                        assert messages[1].role == "assistant"
                        assert len(messages[1].citations) > 0

    def test_rag_gemini_error_graceful_fallback(self, app_and_client, auth_header_user1):
        app, client = app_and_client

        from app.services.vector_service import LocalDeterministicEmbeddings
        with patch.object(Config, "GEMINI_API_KEY", "AIzaFakeKey123"):
            with patch("app.services.vector_service.VectorService.get_embeddings", return_value=LocalDeterministicEmbeddings()):
                with app.app_context():
                    project = _seed_project(user_id=1)
                    project_id = project.id
                    _seed_index(project_id)

                with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                    mock_client = MagicMock()
                    mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Rate limit reached")
                    mock_get_client.return_value = mock_client

                    res = client.post(
                        f"/api/v1/rag/{project_id}/query",
                        json={"question": "How does user authentication work?"},
                        headers=auth_header_user1
                    )

                    assert res.status_code == 200
                    data = res.get_json()
                    assert "Gemini AI Service Notice" in data["answer"] or "Rate limit" in data["answer"]
                    assert len(data["citations"]) > 0


    def test_vector_search_endpoint(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id
            _seed_index(project_id)

        res = client.post(
            f"/api/v1/rag/{project_id}/search",
            json={"query": "authenticate user password"},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["count"] > 0
        assert "results" in data


class TestConversationManagement:
    """Test suite for conversation CRUD, isolation, renaming, and deletion."""

    def test_create_and_list_conversations(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        # Create explicit conversation
        res = client.post(
            f"/api/v1/rag/{project_id}/conversations",
            json={"title": "Auth Architecture Discussion"},
            headers=auth_header_user1
        )
        assert res.status_code == 201
        conv_id = res.get_json()["conversation"]["id"]

        # List conversations
        res = client.get(f"/api/v1/rag/{project_id}/conversations", headers=auth_header_user1)
        assert res.status_code == 200
        conversations = res.get_json()["conversations"]
        assert len(conversations) == 1
        assert conversations[0]["title"] == "Auth Architecture Discussion"

    def test_conversation_isolation_between_users(self, app_and_client, auth_header_user1, auth_header_user2):
        app, client = app_and_client
        with app.app_context():
            p1 = _seed_project(user_id=1, name="Project 1")
            p2 = _seed_project(user_id=2, name="Project 2")
            p1_id = p1.id
            p2_id = p2.id

        # User 1 creates conversation in Project 1
        res = client.post(
            f"/api/v1/rag/{p1_id}/conversations",
            json={"title": "Secret User 1 Chat"},
            headers=auth_header_user1
        )
        assert res.status_code == 201
        c1_id = res.get_json()["conversation"]["id"]

        # User 2 tries to access User 1's conversation -> 403 Forbidden
        res = client.get(f"/api/v1/rag/{p1_id}/conversations/{c1_id}", headers=auth_header_user2)
        assert res.status_code == 403

    def test_rename_conversation(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        res = client.post(
            f"/api/v1/rag/{project_id}/conversations",
            json={"title": "Initial Title"},
            headers=auth_header_user1
        )
        conv_id = res.get_json()["conversation"]["id"]

        # Rename
        res = client.patch(
            f"/api/v1/rag/{project_id}/conversations/{conv_id}",
            json={"title": "Updated Refactored Title"},
            headers=auth_header_user1
        )
        assert res.status_code == 200
        assert res.get_json()["conversation"]["title"] == "Updated Refactored Title"

    def test_delete_conversation(self, app_and_client, auth_header_user1):
        app, client = app_and_client
        with app.app_context():
            project = _seed_project(user_id=1)
            project_id = project.id

        res = client.post(
            f"/api/v1/rag/{project_id}/conversations",
            json={"title": "To Be Deleted"},
            headers=auth_header_user1
        )
        conv_id = res.get_json()["conversation"]["id"]

        # Delete
        res = client.delete(f"/api/v1/rag/{project_id}/conversations/{conv_id}", headers=auth_header_user1)
        assert res.status_code == 200

        # Verify not found afterwards
        res = client.get(f"/api/v1/rag/{project_id}/conversations/{conv_id}", headers=auth_header_user1)
        assert res.status_code == 404
