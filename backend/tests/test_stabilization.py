import io
import json
import shutil
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import create_app
from app.database import db
from app.models.user import User
from app.models.project import Project
from app.models.conversation import Conversation
from app.services.chunking_service import ChunkingService
from app.services.rag_service import RAGService
from app.services.vector_service import VectorService
from app.utils.security import create_access_token


@pytest.fixture
def app(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "STORAGE_DIR": storage_dir,
        "JWT_SECRET_KEY": "stabilization-test-secret",
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
def test_users(app):
    with app.app_context():
        u1 = User(email="user1@example.com", password_hash="hash1", full_name="User One")
        u2 = User(email="user2@example.com", password_hash="hash2", full_name="User Two")
        db.session.add_all([u1, u2])
        db.session.commit()
        return {"u1_id": u1.id, "u2_id": u2.id}


def _create_sample_project(app, user_id, name="Sample Project"):
    with app.app_context():
        proj = Project(
            name=name,
            user_id=user_id,
            source_type="zip",
            storage_path="",
            status="pending"
        )
        db.session.add(proj)
        db.session.flush()

        storage_base = Path(app.config["STORAGE_DIR"])
        proj_dir = storage_base / f"proj_{proj.id}"
        source_dir = proj_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "faiss_index").mkdir(parents=True, exist_ok=True)

        # Create a sample python file in source
        sample_file = source_dir / "app.py"
        sample_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        proj.storage_path = str(proj_dir.as_posix())
        db.session.commit()
        return proj.id


class TestStabilizationAndSecurity:

    def test_dual_mode_auth_bearer_header(self, client, test_users):
        u1_id = test_users["u1_id"]
        token = create_access_token(u1_id, "user1@example.com")

        # Call /auth/me with Authorization: Bearer <token>
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "user1@example.com"

    def test_manual_reindex_endpoint_success(self, app, client, test_users):
        u1_id = test_users["u1_id"]
        token = create_access_token(u1_id, "user1@example.com")
        proj_id = _create_sample_project(app, u1_id)

        resp = client.post(
            f"/api/v1/projects/{proj_id}/index",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Project reindexed successfully."
        assert data["file_count"] >= 1
        assert data["chunk_count"] >= 1
        assert data["status"] == "ready"

        # Check FAISS index exists on disk
        with app.app_context():
            index_path = VectorService.get_index_path(proj_id)
            assert (index_path / "index.faiss").exists()

    def test_manual_reindex_unauthorized_user(self, app, client, test_users):
        u1_id = test_users["u1_id"]
        u2_id = test_users["u2_id"]
        proj_id = _create_sample_project(app, u1_id)
        u2_token = create_access_token(u2_id, "user2@example.com")

        resp = client.post(
            f"/api/v1/projects/{proj_id}/index",
            headers={"Authorization": f"Bearer {u2_token}"}
        )
        assert resp.status_code == 403
        assert "Forbidden" in resp.get_json()["error"]

    def test_missing_index_is_rebuilt_from_disk(self, app, client, test_users):
        u1_id = test_users["u1_id"]
        token = create_access_token(u1_id, "user1@example.com")

        with app.app_context():
            proj = Project(
                name="Auto Rebuild Project",
                user_id=u1_id,
                source_type="zip",
                storage_path="",
                status="ready"
            )
            db.session.add(proj)
            db.session.flush()

            storage_base = Path(app.config["STORAGE_DIR"])
            proj_dir = storage_base / f"proj_{proj.id}"
            source_dir = proj_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (proj_dir / "faiss_index").mkdir(parents=True, exist_ok=True)
            (source_dir / "main.py").write_text("def greet(name):\n    return f'hello {name}'\n", encoding="utf-8")
            proj.storage_path = str(proj_dir.as_posix())
            db.session.commit()
            proj_id = proj.id

        index_dir = VectorService.get_index_path(proj_id)
        if index_dir.exists():
            import shutil
            shutil.rmtree(index_dir, ignore_errors=True)

        resp = client.post(
            f"/api/v1/rag/{proj_id}/query",
            json={"question": "What does greet do?"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "Not Indexed" not in data["answer"]
        assert (index_dir / "index.faiss").exists()

    def test_notebook_and_csv_are_chunked_with_code_and_preview(self, app):
        with app.app_context():
            source_dir = Path(app.config["STORAGE_DIR"]) / "notebook_project"
            source_dir.mkdir(parents=True, exist_ok=True)
            notebook = {
                "cells": [
                    {"cell_type": "code", "source": ["def recommend_movie(title):\n", "    return title.upper()\n"]},
                    {"cell_type": "markdown", "source": ["# Notes\n", "This is a notebook.\n"]},
                    {"cell_type": "code", "source": ["print(recommend_movie('matrix'))\n"]},
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            (source_dir / "MovieRatingFinal.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
            (source_dir / "sample_IMDB_movies.csv").write_text(
                "movie_id,title,score\n1,Inception,8.8\n2,Matrix,8.7\n",
                encoding="utf-8",
            )

            chunks = ChunkingService.chunk_project(source_dir)
            notebook_chunks = [c for c in chunks if c.file_path.endswith(".ipynb")]
            csv_chunks = [c for c in chunks if c.file_path.endswith(".csv")]

            assert notebook_chunks
            assert any("recommend_movie" in c.content for c in notebook_chunks)
            assert any("Code cell" in c.content for c in notebook_chunks)
            assert csv_chunks
            assert any("Dataset preview" in c.content for c in csv_chunks)
            assert "movie_id" in csv_chunks[0].content

    def test_rag_query_success_uses_shared_db_session(self, app, test_users):
        u1_id = test_users["u1_id"]
        proj_id = _create_sample_project(app, u1_id)

        mock_index = MagicMock()
        mock_index.similarity_search_with_relevance_scores.return_value = [
            (
                MagicMock(
                    page_content="def greet(name):\n    return f'hello {name}'\n",
                    metadata={"file_path": "main.py", "start_line": 1, "end_line": 2},
                ),
                0.12,
            )
        ]

        with app.app_context():
            with patch.object(VectorService, "load_index", side_effect=[mock_index, mock_index]), \
                 patch("app.services.rag_service.GeminiService.is_configured", return_value=True), \
                 patch("app.services.rag_service.GeminiService.generate_rag_answer", return_value="This function greets the caller."):
                result = RAGService.ask_question(
                    project_id=proj_id,
                    question="What does greet do?",
                    user_id=u1_id,
                    top_k=1,
                )

        assert result["status"] == "success"
        assert "greet" in result["answer"].lower()
        assert result["citations"][0]["file_path"] == "main.py"

    def test_rag_query_missing_index_returns_not_indexed(self, app, test_users):
        u1_id = test_users["u1_id"]
        proj_id = _create_sample_project(app, u1_id)

        with app.app_context():
            with patch.object(VectorService, "load_index", return_value=None), \
                 patch.object(VectorService, "ensure_project_index", return_value=False):
                result = RAGService.ask_question(
                    project_id=proj_id,
                    question="What does greet do?",
                    user_id=u1_id,
                )

        assert result["answer"].startswith("⚠️ **Project Codebase Not Indexed**")
        assert result["status"] == "not_indexed"

    def test_cross_user_conversation_isolation(self, app, client, test_users):
        u1_id = test_users["u1_id"]
        u2_id = test_users["u2_id"]
        proj_id = _create_sample_project(app, u1_id)

        # Create conversation owned by u1
        with app.app_context():
            conv = Conversation(project_id=proj_id, user_id=u1_id, title="User1 Discussion")
            db.session.add(conv)
            db.session.commit()
            conv_id = conv.id

        # u2 attempts to fetch u1's conversation
        u2_token = create_access_token(u2_id, "user2@example.com")
        resp = client.get(
            f"/api/v1/rag/{proj_id}/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {u2_token}"}
        )
        assert resp.status_code in (403, 404)

    def test_atomic_index_swap_cleanup(self, app, test_users):
        u1_id = test_users["u1_id"]
        proj_id = _create_sample_project(app, u1_id)

        with app.app_context():
            source_dir = Path(app.config["STORAGE_DIR"]) / f"proj_{proj_id}" / "source"
            chunks = ChunkingService.chunk_project(source_dir)
            assert len(chunks) > 0

            # First build
            success1 = VectorService.build_and_save_index(proj_id, chunks)
            assert success1 is True

            index_dir = VectorService.get_index_path(proj_id)
            assert index_dir.exists()
            assert (index_dir / "index.faiss").exists()

            # Second build (re-index atomic swap)
            success2 = VectorService.build_and_save_index(proj_id, chunks)
            assert success2 is True
            assert (index_dir / "index.faiss").exists()

            # Verify no orphaned temp dirs
            parent = index_dir.parent
            assert not (parent / f"faiss_index_tmp_{proj_id}").exists()
            assert not (parent / f"faiss_index_bak_{proj_id}").exists()

    def test_zip_upload_indexes_codebase_automatically(self, app, client, test_users):
        u1_id = test_users["u1_id"]
        token = create_access_token(u1_id, "user1@example.com")
        proj_id = _create_sample_project(app, u1_id)

        # Build in-memory zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("main.py", "def compute(x):\n    return x * 2\n")
            zf.writestr("utils.py", "def log_msg(msg):\n    print(msg)\n")
        zip_buffer.seek(0)

        data = {"file": (zip_buffer, "project.zip")}
        resp = client.post(
            f"/api/v1/files/{proj_id}/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 200
        res = resp.get_json()
        assert res["file_count"] == 2
        assert res["chunk_count"] >= 2
        assert res["status"] == "ready"

        # Verify FAISS index exists
        with app.app_context():
            index_path = VectorService.get_index_path(proj_id)
            assert (index_path / "index.faiss").exists()
