import platform
from app.config import Config
from app.database import db

class HealthService:
    @staticmethod
    def get_system_health():
        # Storage accessibility
        storage_accessible = False
        try:
            Config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            test_file = Config.STORAGE_DIR / ".health_test"
            test_file.write_text("ok")
            test_file.unlink(missing_ok=True)
            storage_accessible = True
        except Exception:
            storage_accessible = False

        # Database readiness check
        db_connected = False
        db_dialect = "unknown"
        db_error = None
        try:
            from sqlalchemy import text
            db_dialect = db.engine.dialect.name
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_connected = True
        except Exception as e:
            db_error = str(e)

        driver_label = "MySQL 8.0 (Active)" if db_dialect == "mysql" else f"SQLite dev fallback ({db_dialect})"

        return {
            "status": "healthy" if db_connected else "degraded",
            "service": "AI Developer Assistant Backend",
            "api_version": "v1",
            "environment": Config.FLASK_ENV,
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "storage_ready": storage_accessible,
            "database": {
                "connected": db_connected,
                "dialect": db_dialect,
                "driver": driver_label,
                "message": "Connected" if db_connected else f"Unreachable: {db_error}"
            },
            "ai_services": {
                "gemini_api_configured": bool(Config.GEMINI_API_KEY),
                "model": Config.GEMINI_MODEL,
                "status": "ready" if Config.GEMINI_API_KEY else "pending_api_key"
            }
        }
