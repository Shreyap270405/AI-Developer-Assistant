import os
from flask import Flask, jsonify, redirect
from flask_cors import CORS
import pymysql
from app.config import Config
from app.database import db
from app.utils.logger import logger

def create_app(test_config=None):
    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)
    else:
        app.config.from_object(Config)

    # Enable CORS for React frontend (explicit origins required when supports_credentials=True)
    allowed_origins = [
        Config.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    if os.getenv("ALLOWED_ORIGINS"):
        allowed_origins.extend([o.strip() for o in os.getenv("ALLOWED_ORIGINS").split(",") if o.strip()])
    allowed_origins = list(dict.fromkeys(allowed_origins))

    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        expose_headers=["Content-Disposition"]
    )

    # Ensure storage directory exists
    try:
        Config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create storage directory: {e}")

    # Database configuration
    if not app.config.get("TESTING") and "SQLALCHEMY_DATABASE_URI" not in (test_config or {}):
        try:
            connection = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                charset="utf8mb4"
            )
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            connection.close()
            app.config["SQLALCHEMY_DATABASE_URI"] = Config.get_database_uri()
            logger.info(f"Connected to MySQL at {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
        except Exception as e:
            # Fallback to local SQLite during early development before MySQL credentials are supplied
            fallback_sqlite = f"sqlite:///{(Config.BASE_DIR / 'storage' / 'app_dev.db').as_posix()}"
            app.config["SQLALCHEMY_DATABASE_URI"] = fallback_sqlite
            logger.info(f"Database initialized with dev fallback ({fallback_sqlite}). MySQL status: {e}")

    from app.database import migrate
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from app.models.user import User  # noqa: F401
        from app.models.project import Project  # noqa: F401
        from app.models.file_metadata import ProjectFile  # noqa: F401
        from app.models.indexing_job import IndexingJob  # noqa: F401
        from app.models.conversation import Conversation, Message, MessageCitation  # noqa: F401
        from app.models.github_import import GitHubImport  # noqa: F401
        db.create_all()

    # Register API Blueprints under versioned /api/v1 prefix
    from app.routes.health_routes import health_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.project_routes import project_bp
    from app.routes.file_routes import file_bp
    from app.routes.rag_routes import rag_bp
    from app.routes.github_routes import github_bp
    from app.routes.ai_routes import ai_bp

    api_prefix = Config.API_PREFIX  # "/api/v1"

    app.register_blueprint(health_bp, url_prefix=api_prefix)
    app.register_blueprint(auth_bp, url_prefix=f"{api_prefix}/auth")
    app.register_blueprint(project_bp, url_prefix=f"{api_prefix}/projects")
    app.register_blueprint(file_bp, url_prefix=f"{api_prefix}/files")
    app.register_blueprint(rag_bp, url_prefix=f"{api_prefix}/rag")
    app.register_blueprint(github_bp, url_prefix=f"{api_prefix}/github")
    app.register_blueprint(ai_bp, url_prefix=f"{api_prefix}/ai")

    # Backward compatibility alias for /api/health
    @app.route("/api/health", methods=["GET"])
    def legacy_health():
        from app.services.health_service import HealthService
        return jsonify(HealthService.get_system_health())

    return app
