"""
test_github.py - Comprehensive test suite for the GitHub repository import feature.

Structure
---------
- TestGitHubURLParsing       : parse_repo_url unit tests (no network)
- TestSSRFAndValidation       : SSRF / hostname / bad-url rejection
- TestValidateEndpoint        : POST /github/<id>/validate (mocked GitHub API)
- TestImportEndpoint          : POST /github/<id>/import  (mocked GitHub API)
- TestStatusEndpoint          : GET  /github/<id>/status
- TestRefreshEndpoint         : POST /github/<id>/refresh
- TestOwnershipEnforcement    : cross-user access attempts
- TestRateLimitHandling       : rate-limit propagation
- TestOversizedRepo           : archive-too-large / too-many-files errors
- TestIncrementalImport       : SHA-based skip and force flag
- TestRAGIntegration          : imports feed into similarity_search

All GitHub HTTP calls are mocked via unittest.mock.patch - no live network required.
Tests marked with @pytest.mark.integration require GITHUB_API_TOKEN and live network.
"""
import io
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app import create_app
from app.database import db as _db
from app.models.project import Project
from app.models.github_import import GitHubImport
from app.services.github_service import GitHubService, GitHubImportError
from app.utils.security import create_access_token


# --- Fixtures -----------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    storage_dir = tmp_path / "storage"
    db_path = (tmp_path / "test.db").as_posix()
    _app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "STORAGE_DIR": storage_dir,
    })
    with _app.app_context():
        _db.create_all()
    return _app


@pytest.fixture
def client(app):
    return app.test_client()


def _token(user_id, email):
    return create_access_token(user_id=user_id, email=email)


def _auth(user_id=1, email="dev@test.com"):
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


def _create_project(client, name="GitHub Test", user_id=1, user_email="dev@test.com"):
    res = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "test"},
        headers=_auth(user_id, user_email),
    )
    assert res.status_code == 201, res.get_json()
    return res.get_json()["project"]


def _mock_validate():
    return {
        "valid": True, "owner": "owner", "repo": "repo",
        "full_name": "owner/repo", "description": "A test repo",
        "default_branch": "main", "commit_sha": "abc1234f",
        "stars": 10, "forks": 2, "language": "Python", "size_kb": 512,
        "is_private": False, "html_url": "https://github.com/owner/repo",
    }


def _mock_import():
    return {
        "owner": "owner", "repo": "repo", "branch": "main",
        "commit_sha": "abc1234f", "extracted_count": 3,
        "description": "A test repo", "html_url": "https://github.com/owner/repo",
        "stars": 10,
    }

# --- TestGitHubURLParsing ----------------------------------------------------

class TestGitHubURLParsing:
    """Unit tests for parse_repo_url - no HTTP calls made."""

    def test_full_https_url(self):
        owner, repo, ref = GitHubService.parse_repo_url("https://github.com/octocat/Hello-World")
        assert owner == "octocat"
        assert repo == "Hello-World"
        assert ref is None

    def test_url_with_git_suffix(self):
        owner, repo, _ = GitHubService.parse_repo_url("https://github.com/octocat/Hello-World.git")
        assert repo == "Hello-World"

    def test_url_with_tree_branch(self):
        owner, repo, ref = GitHubService.parse_repo_url(
            "https://github.com/octocat/Hello-World/tree/develop"
        )
        assert ref == "develop"

    def test_owner_slash_repo_shorthand(self):
        owner, repo, ref = GitHubService.parse_repo_url("octocat/Hello-World")
        assert owner == "octocat" and repo == "Hello-World" and ref is None

    def test_github_com_without_scheme(self):
        owner, repo, _ = GitHubService.parse_repo_url("github.com/octocat/Hello-World")
        assert owner == "octocat" and repo == "Hello-World"

    def test_empty_url_raises(self):
        with pytest.raises(GitHubImportError) as exc_info:
            GitHubService.parse_repo_url("")
        assert exc_info.value.error_code == "invalid_url"

    def test_whitespace_only_raises(self):
        with pytest.raises(GitHubImportError):
            GitHubService.parse_repo_url("   ")

    def test_missing_repo_raises(self):
        with pytest.raises(GitHubImportError) as exc_info:
            GitHubService.parse_repo_url("https://github.com/octocat")
        assert exc_info.value.error_code == "invalid_url_structure"

    def test_invalid_characters_in_owner(self):
        with pytest.raises(GitHubImportError) as exc_info:
            GitHubService.parse_repo_url("https://github.com/octo!cat/repo")
        assert exc_info.value.error_code == "invalid_repo_name"


# --- TestSSRFAndValidation ---------------------------------------------------

class TestSSRFAndValidation:
    """Ensure non-GitHub hosts and SSRF attempts are rejected before any HTTP call."""

    def _check_ssrf(self, url):
        with pytest.raises(GitHubImportError) as exc_info:
            GitHubService.parse_repo_url(url)
        assert exc_info.value.error_code == "unsupported_host"

    def test_internal_ip_rejected(self):
        self._check_ssrf("https://192.168.1.1/owner/repo")

    def test_localhost_rejected(self):
        self._check_ssrf("https://localhost/owner/repo")

    def test_gitea_instance_rejected(self):
        self._check_ssrf("https://gitea.example.com/owner/repo")

    def test_gitlab_rejected(self):
        self._check_ssrf("https://gitlab.com/owner/repo")

    def test_bitbucket_rejected(self):
        self._check_ssrf("https://bitbucket.org/owner/repo")

    def test_metadata_endpoint_rejected(self):
        self._check_ssrf("http://169.254.169.254/latest/meta-data")


# --- TestValidateEndpoint ----------------------------------------------------

class TestValidateEndpoint:

    def test_validate_returns_metadata_for_valid_repo(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()):
            res = client.post(
                f"/api/v1/github/{proj['id']}/validate",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["valid"] is True
        assert data["repository"]["full_name"] == "owner/repo"

    def test_validate_missing_repo_url(self, client, app):
        proj = _create_project(client)
        res = client.post(
            f"/api/v1/github/{proj['id']}/validate",
            json={},
            headers=_auth(),
        )
        assert res.status_code == 400
        assert res.get_json()["error_code"] == "validation_error"

    def test_validate_unsupported_host(self, client, app):
        proj = _create_project(client)
        res = client.post(
            f"/api/v1/github/{proj['id']}/validate",
            json={"repo_url": "https://gitlab.com/owner/repo"},
            headers=_auth(),
        )
        assert res.status_code == 400
        assert res.get_json()["error_code"] == "unsupported_host"

    def test_validate_404_from_github(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   side_effect=GitHubImportError("Not found", 404, "not_found")):
            res = client.post(
                f"/api/v1/github/{proj['id']}/validate",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
        assert res.status_code == 404
        assert res.get_json()["valid"] is False

    def test_validate_rate_limit_from_github(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   side_effect=GitHubImportError("Rate limited", 429, "rate_limit_exceeded")):
            res = client.post(
                f"/api/v1/github/{proj['id']}/validate",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
        assert res.status_code == 429

    def test_validate_requires_auth(self, client, app):
        proj = _create_project(client)
        res = client.post(
            f"/api/v1/github/{proj['id']}/validate",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert res.status_code == 401

    def test_validate_forbidden_other_user(self, client, app):
        proj = _create_project(client, user_id=1, user_email="u1@t.com")
        res = client.post(
            f"/api/v1/github/{proj['id']}/validate",
            json={"repo_url": "https://github.com/owner/repo"},
            headers=_auth(user_id=2, email="u2@t.com"),
        )
        assert res.status_code == 403


# --- TestImportEndpoint ------------------------------------------------------

class TestImportEndpoint:

    def _do_import(self, client, project_id, repo_url="https://github.com/owner/repo",
                   force=False, headers=None):
        if headers is None:
            headers = _auth()
        return client.post(
            f"/api/v1/github/{project_id}/import",
            json={"repo_url": repo_url, "force": force},
            headers=headers,
        )

    def test_successful_import_returns_200(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=_mock_import()), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(3, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock(), MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 200, res.get_json()
        data = res.get_json()
        assert data["import_status"] == "completed"
        assert data["file_count"] == 3
        assert data["chunk_count"] == 2

    def test_import_persists_db_record(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=_mock_import()), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(3, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            self._do_import(client, proj["id"])
        with app.app_context():
            rec = GitHubImport.query.filter_by(project_id=proj["id"]).first()
            assert rec is not None
            assert rec.import_status == "completed"
            assert rec.commit_sha == "abc1234f"

    def test_import_sets_project_ready(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=_mock_import()), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(1, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            self._do_import(client, proj["id"])
        with app.app_context():
            p = _db.session.get(Project, proj["id"])
            assert p.status == "ready"
            assert p.source_type == "github"

    def test_import_missing_repo_url(self, client, app):
        proj = _create_project(client)
        res = client.post(f"/api/v1/github/{proj['id']}/import", json={}, headers=_auth())
        assert res.status_code == 400

    def test_import_invalid_host(self, client, app):
        proj = _create_project(client)
        res = self._do_import(client, proj["id"], repo_url="https://gitlab.com/x/y")
        assert res.status_code == 400

    def test_import_nonexistent_project(self, client, app):
        res = self._do_import(client, 99999)
        assert res.status_code == 404

    def test_import_rate_limit_returns_429_and_status_rate_limited(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   side_effect=GitHubImportError("Rate limit", 429, "rate_limit_exceeded")):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 429
        assert res.get_json()["import_status"] == "rate_limited"

    def test_import_timeout_returns_504(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   side_effect=GitHubImportError("Timeout", 504, "timeout")):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 504

    def test_import_archive_too_large_returns_413(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   side_effect=GitHubImportError("Too large", 413, "archive_too_large")):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 413

    def test_import_too_many_files_returns_413(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   side_effect=GitHubImportError("Too many files", 400, "too_many_files")):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 413

    def test_import_indexing_failure_marks_error(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=_mock_import()), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(2, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   side_effect=RuntimeError("chunking exploded")):
            res = self._do_import(client, proj["id"])
        assert res.status_code == 500
        with app.app_context():
            rec = GitHubImport.query.filter_by(project_id=proj["id"]).first()
            assert rec.import_status == "failed"

    def test_import_requires_auth(self, client, app):
        proj = _create_project(client)
        res = client.post(
            f"/api/v1/github/{proj['id']}/import",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert res.status_code == 401

    def test_import_forbidden_other_user(self, client, app):
        proj = _create_project(client, user_id=1, user_email="u1@t.com")
        res = client.post(
            f"/api/v1/github/{proj['id']}/import",
            json={"repo_url": "https://github.com/owner/repo"},
            headers=_auth(user_id=2, email="u2@t.com"),
        )
        assert res.status_code == 403


# --- TestStatusEndpoint ------------------------------------------------------

class TestStatusEndpoint:

    def test_status_no_prior_import(self, client, app):
        proj = _create_project(client)
        res = client.get(f"/api/v1/github/{proj['id']}/status", headers=_auth())
        assert res.status_code == 200
        assert res.get_json()["has_github_import"] is False

    def test_status_after_import(self, client, app):
        proj = _create_project(client)
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=_mock_import()), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(1, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            client.post(
                f"/api/v1/github/{proj['id']}/import",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
        res = client.get(f"/api/v1/github/{proj['id']}/status", headers=_auth())
        assert res.status_code == 200
        data = res.get_json()
        assert data["has_github_import"] is True
        assert data["import"]["import_status"] == "completed"
        assert data["import"]["full_name"] == "owner/repo"

    def test_status_requires_auth(self, client, app):
        proj = _create_project(client)
        res = client.get(f"/api/v1/github/{proj['id']}/status")
        assert res.status_code == 401

    def test_status_forbidden_other_user(self, client, app):
        proj = _create_project(client, user_id=1, user_email="u1@t.com")
        res = client.get(
            f"/api/v1/github/{proj['id']}/status",
            headers=_auth(user_id=2, email="u2@t.com"),
        )
        assert res.status_code == 403


# --- TestRefreshEndpoint -----------------------------------------------------

class TestRefreshEndpoint:

    def test_refresh_no_linked_repo_returns_400(self, client, app):
        proj = _create_project(client)
        res = client.post(
            f"/api/v1/github/{proj['id']}/refresh",
            json={},
            headers=_auth(),
        )
        assert res.status_code == 400
        assert "no_github_import" in res.get_json()["error_code"]

    def test_refresh_uses_stored_url(self, client, app):
        proj = _create_project(client)
        mock_validate = _mock_validate()
        mock_imp = _mock_import()
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=mock_validate), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=mock_imp), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(1, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            client.post(
                f"/api/v1/github/{proj['id']}/import",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
            res = client.post(
                f"/api/v1/github/{proj['id']}/refresh",
                json={},
                headers=_auth(),
            )
        assert res.status_code == 200
        data = res.get_json()
        assert data["import_status"] == "completed"

    def test_refresh_requires_auth(self, client, app):
        proj = _create_project(client)
        res = client.post(f"/api/v1/github/{proj['id']}/refresh", json={})
        assert res.status_code == 401

    def test_refresh_forbidden_other_user(self, client, app):
        proj = _create_project(client, user_id=1, user_email="u1@t.com")
        res = client.post(
            f"/api/v1/github/{proj['id']}/refresh",
            json={},
            headers=_auth(user_id=2, email="u2@t.com"),
        )
        assert res.status_code == 403


# --- TestIncrementalImport ---------------------------------------------------

class TestIncrementalImport:
    """SHA-based skip and force-flag behavior."""

    def _run_import(self, client, project_id, sha="abc1234f", force=False):
        meta = {**_mock_validate(), "commit_sha": sha}
        imp = {**_mock_import(), "commit_sha": sha}
        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=meta), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   return_value=imp), \
             patch("app.routes.github_routes.IngestionService.sync_project_files_to_db",
                   return_value=(2, [])), \
             patch("app.routes.github_routes.ChunkingService.chunk_project",
                   return_value=[MagicMock()]), \
             patch("app.routes.github_routes.VectorService.build_and_save_index",
                   return_value=True):
            return client.post(
                f"/api/v1/github/{project_id}/import",
                json={"repo_url": "https://github.com/owner/repo", "force": force},
                headers=_auth(),
            )

    def test_same_sha_skips_reimport(self, client, app):
        proj = _create_project(client)
        res1 = self._run_import(client, proj["id"], sha="abc1234f")
        assert res1.status_code == 200
        assert res1.get_json().get("skipped") is not True
        res2 = self._run_import(client, proj["id"], sha="abc1234f")
        assert res2.status_code == 200
        assert res2.get_json()["skipped"] is True

    def test_different_sha_triggers_reimport(self, client, app):
        proj = _create_project(client)
        self._run_import(client, proj["id"], sha="abc1234f")
        res = self._run_import(client, proj["id"], sha="deadbeef")
        assert res.status_code == 200
        assert res.get_json().get("skipped") is not True
        assert res.get_json()["import_status"] == "completed"

    def test_force_flag_bypasses_sha_skip(self, client, app):
        proj = _create_project(client)
        self._run_import(client, proj["id"], sha="abc1234f")
        res = self._run_import(client, proj["id"], sha="abc1234f", force=True)
        assert res.status_code == 200
        assert res.get_json().get("skipped") is not True


# --- TestRAGIntegration ------------------------------------------------------

class TestRAGIntegration:
    """After a mocked GitHub import, the RAG search endpoint should respond."""

    def _write_source_files(self, source_dir):
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "main.py").write_text(
            "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n"
        )
        (source_dir / "utils.py").write_text(
            "def greet(name):\n    return f\"Hello, {name}!\"\n"
        )

    def test_rag_search_works_after_github_import(self, client, app):
        proj = _create_project(client)
        with app.app_context():
            p = _db.session.get(Project, proj["id"])
            source_dir = Path(p.storage_path) / "source"
            self._write_source_files(source_dir)

        def fake_import_repository(repo_url, target_dir, **kwargs):
            return {**_mock_import(), "extracted_count": 2}

        with patch("app.routes.github_routes.GitHubService.validate_repository",
                   return_value=_mock_validate()), \
             patch("app.routes.github_routes.GitHubService.import_repository",
                   side_effect=fake_import_repository):
            res = client.post(
                f"/api/v1/github/{proj['id']}/import",
                json={"repo_url": "https://github.com/owner/repo"},
                headers=_auth(),
            )
        assert res.status_code == 200, res.get_json()
        assert res.get_json()["chunk_count"] > 0

        search_res = client.post(
            f"/api/v1/rag/{proj['id']}/search",
            json={"query": "add function", "top_k": 2},
            headers=_auth(),
        )
        assert search_res.status_code == 200
        assert len(search_res.get_json().get("results", [])) > 0
