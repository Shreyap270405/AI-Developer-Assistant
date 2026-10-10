from flask import Blueprint, jsonify
from app.services.health_service import HealthService

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def check_health():
    """
    Standard health check endpoint reporting service, database, and AI status.
    """
    health_data = HealthService.get_system_health()
    return jsonify(health_data), 200
