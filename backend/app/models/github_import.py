from datetime import datetime, timezone
from app.models.base import db


class GitHubImport(db.Model):
    __tablename__ = "github_imports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    repo_url = db.Column(db.String(500), nullable=False)
    owner = db.Column(db.String(255), nullable=False)
    repo_name = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(511), nullable=False)
    default_branch = db.Column(db.String(255), nullable=True)
    commit_sha = db.Column(db.String(40), nullable=True)
    import_status = db.Column(db.String(50), default="pending", nullable=False, index=True)
    error_message = db.Column(db.Text, nullable=True)
    error_code = db.Column(db.String(50), nullable=True)
    extracted_files = db.Column(db.Integer, default=0, nullable=False)
    indexed_chunks = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text, nullable=True)
    html_url = db.Column(db.String(500), nullable=True)
    stars = db.Column(db.Integer, default=0, nullable=False)
    is_private = db.Column(db.Boolean, default=False, nullable=False)
    language = db.Column(db.String(100), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "repo_url": self.repo_url,
            "owner": self.owner,
            "repo_name": self.repo_name,
            "full_name": self.full_name,
            "default_branch": self.default_branch,
            "commit_sha": self.commit_sha,
            "import_status": self.import_status,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "extracted_files": self.extracted_files,
            "indexed_chunks": self.indexed_chunks,
            "description": self.description,
            "html_url": self.html_url,
            "stars": self.stars,
            "is_private": self.is_private,
            "language": self.language,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
