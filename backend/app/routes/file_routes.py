import hashlib
import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify, g, current_app
from app.database import db
from app.models.file_metadata import ProjectFile
from app.services.project_repository import ProjectRepository
from app.services.ingestion_service import IngestionService, IngestionError
from app.utils.auth import jwt_required
from app.utils.security import is_safe_path, sanitize_relative_path
from app.utils.file_filters import detect_language
from app.utils.logger import logger

file_bp = Blueprint("files", __name__)

# Max upload size (50 MB default, overridable by config MAX_CONTENT_LENGTH)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


# ─── Upload ZIP ───────────────────────────────────────────────────────────────

@file_bp.route("/<int:project_id>/upload", methods=["POST"])
@jwt_required(optional=False)
def upload_codebase(project_id):
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Expected multipart field 'file'"}), 400

    uploaded_file = request.files["file"]
    filename = (uploaded_file.filename or "").strip()
    if not filename or not filename.lower().endswith(".zip"):
        return jsonify({"error": "Uploaded file must be a .zip archive"}), 400

    # Enforce upload size limit (Content-Length header check — not authoritative
    # but gives a fast rejection; streaming limit is enforced by Flask/nginx)
    content_length = request.content_length
    if content_length and content_length > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"Archive exceeds the maximum upload size of {MAX_UPLOAD_BYTES // 1_048_576} MB"}), 413

    proj_dir = Path(project.storage_path)
    source_dir = proj_dir / "source"
    temp_zip = proj_dir / "temp_upload.zip"

    indexing_job = ProjectRepository.create_indexing_job(project.id)

    try:
        project.status = "indexing"
        project.source_type = "zip"
        project.error_message = None
        db.session.commit()

        # Save the upload into a sandboxed temporary path
        temp_zip.parent.mkdir(parents=True, exist_ok=True)
        uploaded_file.save(str(temp_zip))

        # --- Security: validate archive before extraction ---
        IngestionService.validate_zip(temp_zip)

        # Clear previous source tree
        if source_dir.exists():
            shutil.rmtree(source_dir, ignore_errors=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        # Extract (safe, filtered)
        IngestionService.extract_zip(temp_zip, source_dir)
        temp_zip.unlink(missing_ok=True)

        # Parse and sync metadata to MySQL
        file_count, db_files = IngestionService.sync_project_files_to_db(project)

        # Parse chunks and build vector index for RAG search
        from app.services.chunking_service import ChunkingService
        from app.services.vector_service import VectorService
        chunks = ChunkingService.chunk_project(source_dir)
        chunk_count = len(chunks)
        if chunks:
            VectorService.build_and_save_index(project.id, chunks)

        project.status = "ready"
        project.file_count = file_count
        project.chunk_count = chunk_count
        db.session.commit()

        ProjectRepository.update_indexing_job(
            indexing_job.id,
            status="completed",
            progress=100,
            processed=file_count,
        )

        logger.info(f"Project {project_id}: ingested {file_count} files and {chunk_count} chunks.")
        return jsonify({
            "message": "Project uploaded, processed, and indexed successfully",
            "file_count": file_count,
            "chunk_count": chunk_count,
            "status": "ready",
        }), 200

    except IngestionError as exc:
        temp_zip.unlink(missing_ok=True)
        project.status = "error"
        project.error_message = str(exc)
        db.session.commit()
        ProjectRepository.update_indexing_job(
            indexing_job.id, status="failed", error_message=str(exc)
        )
        logger.warning(f"Project {project_id}: upload validation failed: {exc}")
        return jsonify({"error": str(exc)}), 422

    except Exception as exc:
        temp_zip.unlink(missing_ok=True)
        project.status = "error"
        project.error_message = "Internal error during upload."
        db.session.commit()
        ProjectRepository.update_indexing_job(
            indexing_job.id, status="failed", error_message="Internal error"
        )
        logger.error(f"Project {project_id} upload error: {exc}")
        return jsonify({"error": "Failed to process archive. Please try again."}), 500


# ─── List project files ───────────────────────────────────────────────────────

@file_bp.route("/<int:project_id>/files", methods=["GET"])
@jwt_required(optional=False)
def list_project_files(project_id):
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project"}), 403

    files = (
        ProjectFile.query.filter_by(project_id=project.id)
        .order_by(ProjectFile.file_path)
        .all()
    )
    return jsonify({
        "project_id": project_id,
        "file_count": len(files),
        "files": [f.to_dict() for f in files],
    }), 200


# ─── File tree ────────────────────────────────────────────────────────────────

@file_bp.route("/<int:project_id>/tree", methods=["GET"])
@jwt_required(optional=False)
def get_file_tree(project_id):
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project"}), 403

    source_dir = Path(project.storage_path) / "source"
    tree = IngestionService.build_file_tree(source_dir)
    return jsonify({"tree": tree, "project_id": project.id}), 200


# ─── File content ─────────────────────────────────────────────────────────────

@file_bp.route("/<int:project_id>/content", methods=["GET"])
@jwt_required(optional=False)
def get_file_content(project_id):
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project"}), 403

    rel_path = request.args.get("path", "").strip()
    if not rel_path:
        return jsonify({"error": "Query parameter 'path' is required"}), 400

    clean_path = sanitize_relative_path(rel_path)
    source_dir = Path(project.storage_path) / "source"
    target_file = source_dir / clean_path

    if not is_safe_path(source_dir, target_file) or not target_file.is_file():
        return jsonify({"error": "File not found or access denied"}), 404

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        return jsonify({
            "path": clean_path,
            "content": content,
            "language": detect_language(clean_path),
            "line_count": len(content.splitlines()),
        }), 200
    except Exception as exc:
        logger.error(f"Error reading file {clean_path}: {exc}")
        return jsonify({"error": "Failed to read file"}), 500


# ─── Save file ────────────────────────────────────────────────────────────────

@file_bp.route("/<int:project_id>/save", methods=["POST"])
@jwt_required(optional=False)
def save_file_content(project_id):
    user_id = g.user_id
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "You do not have access to this project"}), 403

    data = request.get_json() or {}
    rel_path = data.get("path", "").strip()
    content = data.get("content", "")

    if not rel_path:
        return jsonify({"error": "Parameter 'path' is required"}), 400

    clean_path = sanitize_relative_path(rel_path)
    source_dir = Path(project.storage_path) / "source"
    target_file = source_dir / clean_path

    if not is_safe_path(source_dir, target_file):
        return jsonify({"error": "Invalid file path"}), 403

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")

        content_bytes = content.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        lines = len(content.splitlines())

        pf = ProjectFile.query.filter_by(
            project_id=project.id, file_path=clean_path
        ).first()
        if pf:
            pf.line_count = lines
            pf.file_size = len(content_bytes)
            pf.content_hash = content_hash
            pf.file_type = detect_language(clean_path)
        else:
            pf = ProjectFile(
                project_id=project.id,
                file_path=clean_path,
                file_type=detect_language(clean_path),
                file_size=len(content_bytes),
                content_hash=content_hash,
                line_count=lines,
            )
            db.session.add(pf)
        db.session.commit()

        return jsonify({
            "message": "File saved successfully",
            "path": clean_path,
            "line_count": lines,
        }), 200

    except Exception as exc:
        logger.error(f"Error saving file {clean_path}: {exc}")
        return jsonify({"error": "Failed to save file"}), 500
