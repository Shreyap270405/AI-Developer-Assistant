import pytest
from pathlib import Path
from app.services.chunking_service import CodeChunk
from app.services.vector_service import VectorService

def test_build_and_search_index(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.Config.STORAGE_DIR", tmp_path)

    chunks = [
        CodeChunk(
            chunk_id="auth_1",
            file_path="src/auth.py",
            start_line=1,
            end_line=20,
            language="python",
            content="def authenticate_user(email, password):\n    # JWT verification\n    return token",
            metadata={"file_path": "src/auth.py", "start_line": 1, "end_line": 20}
        ),
        CodeChunk(
            chunk_id="db_1",
            file_path="src/database.py",
            start_line=1,
            end_line=15,
            language="python",
            content="def connect_mysql():\n    # MySQL 8.0 pool connection\n    return pool",
            metadata={"file_path": "src/database.py", "start_line": 1, "end_line": 15}
        )
    ]

    project_id = 9999
    success = VectorService.build_and_save_index(project_id, chunks)
    assert success is True

    # Search for authentication
    results = VectorService.similarity_search(project_id, "how does authentication work?", top_k=2)
    assert len(results) > 0
    top_result = results[0]
    assert "src/auth.py" in top_result["metadata"]["file_path"]
