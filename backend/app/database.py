from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text
from app.utils.logger import logger

# Initialize SQLAlchemy and Flask-Migrate extensions
db = SQLAlchemy()
migrate = Migrate()


def check_database_connection(app):
    """
    Tests database connectivity using a lightweight ping.
    Returns (status: bool, message: str, details: dict)
    """
    with app.app_context():
        dialect_name = "unknown"
        try:
            dialect_name = db.engine.dialect.name
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, f"Database ({dialect_name}) connection verified.", {
                "dialect": dialect_name,
                "connected": True
            }
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Database connection check failure ({dialect_name}): {err_msg}")
            return False, f"Database connection failed: {err_msg}", {
                "dialect": dialect_name,
                "connected": False,
                "error": err_msg
            }
