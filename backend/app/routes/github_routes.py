"""
GitHub Repository Import Routes  -  /api/v1/github/...

Endpoints
---------
POST  /<project_id>/validate   – Validate a GitHub URL + fetch repo metadata
POST  /<project_id>/import     – Download, extract, index a repository
GET   /<project_id>/status     – Poll current import status / last import record
POST  /<project_id>/refresh    – Re-import the same repository (incremental-safe)
"""
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, request, jsonify, g

from app.database import db
from app.models.github_import import GitHubImport
from app.services.github_service import GitHubService, GitHubImportError
from app.services.ingestion_service import IngestionService
from app.services.chunking_service import ChunkingService
from app.services.vector_service import VectorService
from app.services.project_repository import ProjectRepository
from app.utils.auth import jwt_required
from app.utils.logger import logger

github_bp = Blueprint("github", __name__)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_import(project_id: int, repo_url: str, owner: str,
                          repo_name: str, full_name: str) -> GitHubImport:
    """Upsert the GitHubImport row – one row per project."""
    rec = GitHubImport.query.filter_by(project_id=project_id).first()
    if rec is None:
        rec = GitHubImport(
            project_id=project_id,
            repo_url=repo_url,
            owner=owner,
            repo_name=repo_name,
            full_name=full_name,
        )
        db.session.add(rec)
    else:
        rec.repo_url = repo_url
        rec.owner = owner
        rec.repo_name = repo_name
        rec.full_name = full_name
    return rec


def _map_github_error_code(error_code: str) -> int:
    """Map GitHubImportError codes to HTTP status codes."""
    mapping = {
        "invalid_url": 400,
        "invalid_url_structure": 400,
        "invalid_repo_name": 400,
        "unsupported_host": 400,
        "not_found": 404,
        "unauthorized": 401,
        "rate_limit_exceeded": 429,
        "timeout": 504,
        "network_error": 502,
        "archive_too_large": 413,
        "too_many_files": 413,
        "uncompressed_size_exceeded": 413,
        "empty_archive": 422,
        "corrupt_archive": 502,
        "provider_error": 502,
    }
    return mapping.get(error_code, 500)


# ─── POST /<project_id>/validate ─────────────────────────────────────────────

@github_bp.route("/<int:project_id>/validate", methods=["POST"])
@jwt_required(optional=False)
def validate_github_repo(project_id: int):
    """
    Validates the given GitHub URL and returns repository metadata without
    downloading any source code. Safe to call as a pre-flight step.
    """
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    if not repo_url:
        return jsonify({"error": "repo_url is required", "error_code": "validation_error"}), 400

    try:
        meta = GitHubService.validate_repository(repo_url)
        return jsonify({"valid": True, "repository": meta}), 200
    except GitHubImportError as exc:
        http_code = _map_github_error_code(exc.error_code)
        return jsonify({
            "valid": False,
            "error": exc.message,
            "error_code": exc.error_code,
        }), http_code
    except Exception as exc:
        logger.error(f"Unexpected error during GitHub validation: {exc}")
        return jsonify({"valid": False, "error": "Validation failed due to an internal error.", "error_code": "internal_error"}), 500


# ─── POST /<project_id>/import ───────────────────────────────────────────────

@github_bp.route("/<int:project_id>/import", methods=["POST"])
@jwt_required(optional=False)
def import_github_repository(project_id: int):
    """
    Downloads, extracts, chunks, embeds, and FAISS-indexes a GitHub repository
    for the given project. Reuses all existing ingestion/indexing services.

    Supports incremental re-import: if the commit SHA matches the previously
    indexed commit, the operation is a no-op and returns the cached status.

    Request body (JSON):
        repo_url   (str, required)  – GitHub URL in any accepted format
        force      (bool, optional) – re-index even if SHA is unchanged
    """
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project", "error_code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()
    force = bool(data.get("force", False))

    if not repo_url:
        return jsonify({"error": "repo_url is required", "error_code": "validation_error"}), 400

    # ── Step 0: validate repo (also gets commit SHA) ──
    try:
        meta = GitHubService.validate_repository(repo_url)
    except GitHubImportError as exc:
        http_code = _map_github_error_code(exc.error_code)
        return jsonify({"error": exc.message, "error_code": exc.error_code}), http_code
    except Exception as exc:
        logger.error(f"Validation error for project {project_id}: {exc}")
        return jsonify({"error": "Failed to reach GitHub API.", "error_code": "internal_error"}), 500

    new_sha = meta.get("commit_sha", "")

    # ── Step 1: upsert import record & check for skip ──
    rec = _get_or_create_import(
        project_id=project_id,
        repo_url=repo_url,
        owner=meta["owner"],
        repo_name=meta["repo"],
        full_name=meta["full_name"],
    )
    db.session.flush()

    # Incremental-skip: same commit SHA, index already ready, and not forced
    if (
        not force
        and rec.commit_sha
        and rec.commit_sha == new_sha
        and rec.import_status == "completed"
        and project.status == "ready"
    ):
        logger.info(
            f"Project {project_id}: GitHub repo {meta['full_name']} already indexed "
            f"at commit {new_sha}. Skipping re-import."
        )
        db.session.commit()
        return jsonify({
            "message": "Repository already indexed at this commit. Use force=true to re-index.",
            "skipped": True,
            "import": rec.to_dict(),
        }), 200

    # ── Step 2: mark status = importing ──
    rec.import_status = "importing"
    rec.error_message = None
    rec.error_code = None
    rec.started_at = datetime.now(timezone.utc)
    rec.completed_at = None
    rec.default_branch = meta.get("default_branch")
    rec.description = meta.get("description", "")
    rec.html_url = meta.get("html_url", "")
    rec.stars = meta.get("stars", 0)
    rec.is_private = meta.get("is_private", False)
    rec.language = meta.get("language", "")

    project.status = "indexing"
    project.source_type = "github"
    project.github_repo_url = repo_url
    project.error_message = None
    db.session.commit()

    source_dir = Path(project.storage_path) / "source"

    # ── Step 3: download & extract via GitHub API ──
    try:
        import_result = GitHubService.import_repository(repo_url, source_dir)
    except GitHubImportError as exc:
        http_code = _map_github_error_code(exc.error_code)
        # Map rate-limit to dedicated status
        import_status = "rate_limited" if exc.error_code == "rate_limit_exceeded" else "failed"
        rec.import_status = import_status
        rec.error_message = exc.message
        rec.error_code = exc.error_code
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = exc.message
        db.session.commit()
        return jsonify({"error": exc.message, "error_code": exc.error_code, "import_status": import_status}), http_code
    except Exception as exc:
        logger.error(f"Unexpected download error for project {project_id}: {exc}")
        rec.import_status = "failed"
        rec.error_message = "Unexpected error during repository download."
        rec.error_code = "internal_error"
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = "Repository download failed."
        db.session.commit()
        return jsonify({"error": "Repository download failed.", "error_code": "internal_error"}), 500

    extracted_count = import_result.get("extracted_count", 0)
    rec.extracted_files = extracted_count
    rec.commit_sha = import_result.get("commit_sha") or new_sha

    # ── Step 4: sync to MySQL ──
    rec.import_status = "indexing"
    db.session.commit()

    try:
        file_count, _ = IngestionService.sync_project_files_to_db(project)
    except Exception as exc:
        logger.error(f"DB sync failed for project {project_id}: {exc}")
        rec.import_status = "failed"
        rec.error_message = "File metadata sync failed."
        rec.error_code = "db_sync_error"
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = "File sync failed after download."
        db.session.commit()
        return jsonify({"error": "File metadata sync failed.", "error_code": "db_sync_error"}), 500

    # ── Step 5: chunk + embed + FAISS index ──
    try:
        chunks = ChunkingService.chunk_project(source_dir)
        chunk_count = len(chunks)
        VectorService.build_and_save_index(project_id, chunks)
    except Exception as exc:
        logger.error(f"Indexing failed for project {project_id}: {exc}")
        rec.import_status = "failed"
        rec.error_message = "Vector indexing failed."
        rec.error_code = "indexing_error"
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = "Vector indexing failed after import."
        db.session.commit()
        return jsonify({"error": "Vector indexing failed.", "error_code": "indexing_error"}), 500

    # ── Step 6: mark completed ──
    rec.import_status = "completed"
    rec.indexed_chunks = chunk_count
    rec.completed_at = datetime.now(timezone.utc)
    project.status = "ready"
    project.file_count = file_count
    project.chunk_count = chunk_count
    project.error_message = None
    db.session.commit()

    logger.info(
        f"GitHub import completed: project={project_id} repo={meta['full_name']} "
        f"files={file_count} chunks={chunk_count} sha={rec.commit_sha}"
    )
    return jsonify({
        "message": "Repository imported and indexed successfully.",
        "repo": meta["full_name"],
        "file_count": file_count,
        "chunk_count": chunk_count,
        "commit_sha": rec.commit_sha,
        "import_status": "completed",
        "import": rec.to_dict(),
    }), 200


# ─── GET /<project_id>/status ─────────────────────────────────────────────────

@github_bp.route("/<int:project_id>/status", methods=["GET"])
@jwt_required(optional=False)
def get_import_status(project_id: int):
    """Returns current GitHub import status and metadata for the project."""
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project", "error_code": "forbidden"}), 403

    rec = GitHubImport.query.filter_by(project_id=project_id).first()
    if not rec:
        return jsonify({
            "has_github_import": False,
            "project_status": project.status,
        }), 200

    return jsonify({
        "has_github_import": True,
        "project_status": project.status,
        "import": rec.to_dict(),
    }), 200


# ─── POST /<project_id>/refresh ──────────────────────────────────────────────

@github_bp.route("/<int:project_id>/refresh", methods=["POST"])
@jwt_required(optional=False)
def refresh_github_repository(project_id: int):
    """
    Re-imports the previously linked GitHub repository.
    Automatically uses the stored repo_url; optionally accepts a new one.
    Deleted/changed files are cleaned up via sync_project_files_to_db.
    """
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found", "error_code": "project_not_found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project", "error_code": "forbidden"}), 403

    rec = GitHubImport.query.filter_by(project_id=project_id).first()
    data = request.get_json(silent=True) or {}
    repo_url = (data.get("repo_url") or "").strip()

    if not repo_url:
        if rec and rec.repo_url:
            repo_url = rec.repo_url
        elif project.github_repo_url:
            repo_url = project.github_repo_url
        else:
            return jsonify({
                "error": "No GitHub repository is linked to this project. "
                         "Provide repo_url to import one.",
                "error_code": "no_github_import",
            }), 400

    # Delegate to import endpoint logic — pass force=true to skip SHA check
    from flask import current_app
    with current_app.test_request_context(
        f"/api/v1/github/{project_id}/import",
        method="POST",
        json={"repo_url": repo_url, "force": True},
    ):
        # Can't easily call the view function directly without going through
        # the request context; just re-use the service layer directly.
        pass

    # Directly re-run the import pipeline (force=True)
    try:
        meta = GitHubService.validate_repository(repo_url)
    except GitHubImportError as exc:
        return jsonify({"error": exc.message, "error_code": exc.error_code}), _map_github_error_code(exc.error_code)

    rec = _get_or_create_import(
        project_id=project_id,
        repo_url=repo_url,
        owner=meta["owner"],
        repo_name=meta["repo"],
        full_name=meta["full_name"],
    )
    rec.import_status = "importing"
    rec.error_message = None
    rec.error_code = None
    rec.started_at = datetime.now(timezone.utc)
    rec.completed_at = None
    rec.default_branch = meta.get("default_branch")
    rec.description = meta.get("description", "")
    rec.html_url = meta.get("html_url", "")
    rec.stars = meta.get("stars", 0)
    rec.is_private = meta.get("is_private", False)
    rec.language = meta.get("language", "")
    project.status = "indexing"
    project.source_type = "github"
    project.github_repo_url = repo_url
    project.error_message = None
    db.session.commit()

    source_dir = Path(project.storage_path) / "source"

    try:
        import_result = GitHubService.import_repository(repo_url, source_dir)
    except GitHubImportError as exc:
        import_status = "rate_limited" if exc.error_code == "rate_limit_exceeded" else "failed"
        rec.import_status = import_status
        rec.error_message = exc.message
        rec.error_code = exc.error_code
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = exc.message
        db.session.commit()
        return jsonify({"error": exc.message, "error_code": exc.error_code}), _map_github_error_code(exc.error_code)
    except Exception as exc:
        logger.error(f"Refresh download error for project {project_id}: {exc}")
        rec.import_status = "failed"
        rec.error_message = "Download failed during refresh."
        rec.error_code = "internal_error"
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = "Refresh failed."
        db.session.commit()
        return jsonify({"error": "Refresh failed.", "error_code": "internal_error"}), 500

    rec.extracted_files = import_result.get("extracted_count", 0)
    rec.commit_sha = import_result.get("commit_sha") or meta.get("commit_sha", "")
    rec.import_status = "indexing"
    db.session.commit()

    try:
        file_count, _ = IngestionService.sync_project_files_to_db(project)
        chunks = ChunkingService.chunk_project(source_dir)
        VectorService.build_and_save_index(project_id, chunks)
    except Exception as exc:
        logger.error(f"Indexing error during refresh for project {project_id}: {exc}")
        rec.import_status = "failed"
        rec.error_message = "Indexing failed during refresh."
        rec.error_code = "indexing_error"
        rec.completed_at = datetime.now(timezone.utc)
        project.status = "error"
        project.error_message = "Re-indexing failed."
        db.session.commit()
        return jsonify({"error": "Re-indexing failed.", "error_code": "indexing_error"}), 500

    rec.import_status = "completed"
    rec.indexed_chunks = len(chunks)
    rec.completed_at = datetime.now(timezone.utc)
    project.status = "ready"
    project.file_count = file_count
    project.chunk_count = len(chunks)
    project.error_message = None
    db.session.commit()

    logger.info(
        f"GitHub refresh completed: project={project_id} repo={meta['full_name']} "
        f"files={file_count} chunks={len(chunks)} sha={rec.commit_sha}"
    )
    return jsonify({
        "message": "Repository refreshed and re-indexed successfully.",
        "repo": meta["full_name"],
        "file_count": file_count,
        "chunk_count": len(chunks),
        "commit_sha": rec.commit_sha,
        "import_status": "completed",
        "import": rec.to_dict(),
    }), 200
