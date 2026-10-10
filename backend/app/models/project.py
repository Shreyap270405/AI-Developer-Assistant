from datetime import datetime, timezone
from app.models.base import db

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_type = db.Column(db.String(50), default="zip", nullable=False)  # 'zip', 'github', 'manual'
    storage_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default="pending", nullable=False)  # 'pending', 'indexing', 'ready', 'error'
    error_message = db.Column(db.Text, nullable=True)
    file_count = db.Column(db.Integer, default=0, nullable=False)
    chunk_count = db.Column(db.Integer, default=0, nullable=False)
    github_repo_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    files = db.relationship("ProjectFile", backref="project", cascade="all, delete-orphan", lazy="dynamic")
    conversations = db.relationship("Conversation", backref="project", cascade="all, delete-orphan", lazy="dynamic")
    indexing_jobs = db.relationship("IndexingJob", backref="project", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "status": self.status,
            "error_message": self.error_message,
            "file_count": self.file_count,
            "chunk_count": self.chunk_count,
            "github_repo_url": self.github_repo_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
