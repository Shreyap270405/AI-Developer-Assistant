from datetime import datetime, timezone
from app.models.base import db

class ProjectFile(db.Model):
    __tablename__ = "project_files"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = db.Column(db.String(500), nullable=False)  # normalized relative path e.g. "src/index.js"
    file_type = db.Column(db.String(50), nullable=True)   # "javascript", "python", etc.
    content_hash = db.Column(db.String(64), nullable=True, index=True)  # SHA-256 content checksum
    file_size = db.Column(db.Integer, default=0, nullable=False)
    line_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    indexed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("project_id", "file_path", name="uq_project_file_path"),
        db.Index("ix_project_file_lookup", "project_id", "file_path"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "content_hash": self.content_hash,
            "file_size": self.file_size,
            "line_count": self.line_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
        }
