# Re-export the single shared SQLAlchemy instance from app.database.
# This ensures all models and routes share one db object regardless of import path.
from app.database import db

__all__ = ["db"]
