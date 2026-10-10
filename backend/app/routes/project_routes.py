import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models.project import Project
from app.services.project_repository import ProjectRepository
from app.utils.auth import jwt_required
from app.config import Config
from app.utils.logger import logger

project_bp = Blueprint("projects", __name__)


@project_bp.route("", methods=["GET"])
@jwt_required(optional=False)
def list_projects():
    user_id = getattr(g, "user_id", None)
    projects = ProjectRepository.list_projects_for_user(user_id)
    return jsonify({"projects": [p.to_dict() for p in projects]}), 200


@project_bp.route("", methods=["POST"])
@jwt_required(optional=False)
def create_project():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    source_type = data.get("source_type", "zip").strip()
    user_id = getattr(g, "user_id", None)

    if not name:
        return jsonify({"error": "Project name is required"}), 400

    new_project = Project(
        name=name,
        description=description,
        user_id=user_id,
        source_type=source_type,
        storage_path="",
        status="pending"
    )

    try:
        db.session.add(new_project)
        db.session.flush()  # populate new_project.id

        from flask import current_app
        storage_base = Path(current_app.config.get("STORAGE_DIR") or Config.STORAGE_DIR)
        proj_dir = storage_base / f"proj_{new_project.id}"
        (proj_dir / "source").mkdir(parents=True, exist_ok=True)
        (proj_dir / "faiss_index").mkdir(parents=True, exist_ok=True)

        new_project.storage_path = str(proj_dir.as_posix())
        db.session.commit()

        logger.info(f"Project '{name}' (ID: {new_project.id}) created for user {user_id}.")
        return jsonify({"message": "Project created successfully", "project": new_project.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating project: {e}")
        return jsonify({"error": f"Failed to create project: {str(e)}"}), 500


@project_bp.route("/<int:project_id>", methods=["PATCH", "PUT"])
@jwt_required(optional=False)
def update_project(project_id):
    user_id = getattr(g, "user_id", None)
    data = request.get_json() or {}
    name = data.get("name")
    description = data.get("description")

    if name is not None and not name.strip():
        return jsonify({"error": "Project name cannot be empty"}), 400

    project, err = ProjectRepository.update_project(
        project_id, 
        user_id, 
        name=name.strip() if name else None, 
        description=description.strip() if description else None
    )
    
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project"}), 403

    return jsonify({"message": "Project updated successfully", "project": project.to_dict()}), 200


@project_bp.route("/<int:project_id>", methods=["GET"])
@jwt_required(optional=False)
def get_project(project_id):
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project"}), 403

    return jsonify({"project": project.to_dict()}), 200


@project_bp.route("/<int:project_id>/jobs", methods=["GET"])
@jwt_required(optional=False)
def get_project_jobs(project_id):
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project"}), 403

    from app.models.indexing_job import IndexingJob
    jobs = project.indexing_jobs.order_by(IndexingJob.created_at.desc()).all()
    return jsonify({"jobs": [j.to_dict() for j in jobs]}), 200


@project_bp.route("/<int:project_id>/index", methods=["POST"])
@jwt_required(optional=False)
def index_project(project_id):
    """
    Manually triggers full code parsing, chunking, and FAISS indexing for the project.
    Atomically updates the vector database without retaining stale or deleted files.
    """
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project"}), 403

    source_dir = Path(project.storage_path) / "source"
    if not source_dir.exists() or not any(source_dir.iterdir()):
        return jsonify({"error": "No source files found to index. Upload or import code first.", "error_code": "no_source_files"}), 400

    indexing_job = ProjectRepository.create_indexing_job(project.id)
    try:
        from app.services.ingestion_service import IngestionService
        from app.services.chunking_service import ChunkingService
        from app.services.vector_service import VectorService

        project.status = "indexing"
        project.error_message = None
        db.session.commit()

        file_count, _ = IngestionService.sync_project_files_to_db(project)
        chunks = ChunkingService.chunk_project(source_dir)
        chunk_count = len(chunks)

        if chunks:
            saved = VectorService.build_and_save_index(project.id, chunks)
            if not saved:
                raise RuntimeError("Failed to build and save FAISS index.")

        project.status = "ready"
        project.file_count = file_count
        project.chunk_count = chunk_count
        project.error_message = None
        db.session.commit()

        ProjectRepository.update_indexing_job(
            indexing_job.id,
            status="completed",
            progress=100,
            processed=file_count,
        )

        logger.info(f"Project {project_id} manually reindexed: {file_count} files, {chunk_count} chunks.")
        return jsonify({
            "message": "Project reindexed successfully.",
            "file_count": file_count,
            "chunk_count": chunk_count,
            "status": "ready"
        }), 200
    except Exception as exc:
        project.status = "error"
        project.error_message = f"Indexing failed: {str(exc)}"
        db.session.commit()
        ProjectRepository.update_indexing_job(
            indexing_job.id,
            status="failed",
            error_message=str(exc)
        )
        logger.error(f"Manual reindex failed for project {project_id}: {exc}")
        return jsonify({"error": f"Indexing failed: {str(exc)}"}), 500


@project_bp.route("/<int:project_id>", methods=["DELETE"])
@jwt_required(optional=False)
def delete_project(project_id):
    user_id = getattr(g, "user_id", None)
    project, err = ProjectRepository.get_project_secure(project_id, user_id)
    if err == "not_found":
        return jsonify({"error": "Project not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "Forbidden: You do not have access to this project"}), 403

    try:
        proj_dir = Path(project.storage_path)
        if proj_dir.exists() and proj_dir.is_dir():
            shutil.rmtree(proj_dir, ignore_errors=True)

        db.session.delete(project)
        db.session.commit()
        logger.info(f"Project ID {project_id} deleted.")
        return jsonify({"message": "Project deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({"error": f"Failed to delete project: {str(e)}"}), 500
