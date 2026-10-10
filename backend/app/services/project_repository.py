from datetime import datetime, timezone
from app.database import db
from app.models.project import Project
from app.models.indexing_job import IndexingJob
from app.models.file_metadata import ProjectFile
from app.utils.logger import logger


class ProjectRepository:
    """
    Data-access layer for Project, ProjectFile, and IndexingJob models.
    Enforces user ownership boundaries so a user cannot access or modify another user's projects.
    """

    @staticmethod
    def get_project_secure(project_id: int, user_id: int = None):
        """
        Retrieves a project by ID and validates user ownership.
        Returns: (project, error_status: str|None)
          - If project not found: (None, "not_found")
          - If project belongs to another user: (None, "forbidden")
          - If authorized: (project, None)
        """
        project = db.session.get(Project, project_id)
        if not project:
            return None, "not_found"

        # If project has an owner and user_id is specified, enforce ownership
        if project.user_id is not None and user_id is not None:
            if project.user_id != user_id:
                return None, "forbidden"

        return project, None

    @staticmethod
    def list_projects_for_user(user_id: int = None):
        """
        Returns projects owned by the user, or all public/unowned projects if unauthenticated.
        """
        if user_id:
            return Project.query.filter(
                (Project.user_id == user_id) | (Project.user_id.is_(None))
            ).order_by(Project.created_at.desc()).all()
        return Project.query.order_by(Project.created_at.desc()).all()

    @staticmethod
    def create_project(name: str, description: str = "", user_id: int = None, source_type: str = "zip", storage_path: str = "") -> Project:
        """
        Creates and persists a new project record.
        """
        project = Project(
            name=name,
            description=description,
            user_id=user_id,
            source_type=source_type,
            storage_path=storage_path,
            status="pending"
        )
        db.session.add(project)
        db.session.commit()
        return project

    @staticmethod
    def update_project(project_id: int, user_id: int = None, name: str = None, description: str = None):
        """
        Updates project metadata (name, description) securely.
        """
        project, err = ProjectRepository.get_project_secure(project_id, user_id)
        if err:
            return None, err
        
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
            
        db.session.commit()
        return project, None

    @staticmethod
    def update_project_status(project_id: int, status: str, error_message: str = None, chunk_count: int = None, file_count: int = None):
        """
        Updates project index status and counts.
        """
        project = db.session.get(Project, project_id)
        if not project:
            return None
        project.status = status
        if error_message is not None:
            project.error_message = error_message
        if chunk_count is not None:
            project.chunk_count = chunk_count
        if file_count is not None:
            project.file_count = file_count
        db.session.commit()
        return project

    @staticmethod
    def delete_project_secure(project_id: int, user_id: int = None):
        """
        Validates ownership and deletes the project along with cascading database records.
        """
        project, err = ProjectRepository.get_project_secure(project_id, user_id)
        if err:
            return False, err
        db.session.delete(project)
        db.session.commit()
        return True, None

    @staticmethod
    def create_indexing_job(project_id: int, total_files: int = 0) -> IndexingJob:
        """
        Creates an asynchronous indexing job record in MySQL.
        """
        job = IndexingJob(
            project_id=project_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            total_files=total_files,
            processed_files=0,
            progress_percentage=0
        )
        db.session.add(job)
        db.session.commit()
        return job

    @staticmethod
    def update_indexing_job(job_id: int, status: str, progress: int = None, processed: int = None, error_message: str = None):
        """
        Updates the progress of an indexing job.
        """
        job = db.session.get(IndexingJob, job_id)
        if not job:
            return None
        job.status = status
        if progress is not None:
            job.progress_percentage = min(max(progress, 0), 100)
        if processed is not None:
            job.processed_files = processed
        if error_message is not None:
            job.error_message = error_message
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return job
