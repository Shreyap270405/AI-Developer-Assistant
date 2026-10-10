from flask import Blueprint, request, jsonify, g
from app.services.gemini_service import (
    GeminiService,
    AIServiceError,
    AIConfigurationError,
    AIRateLimitError,
    AITimeoutError,
    AIProviderError,
    AIValidationError,
)
from app.utils.auth import jwt_required
from app.utils.logger import logger

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/status", methods=["GET"])
@jwt_required(optional=True)
def get_ai_status():
    """
    Returns the operational configuration status of the AI service (without leaking sensitive keys).
    """
    configured = GeminiService.is_configured()
    model = GeminiService.get_model_name()
    return jsonify({
        "configured": configured,
        "model": model,
        "provider": "google-genai",
        "operations": ["explain", "debug", "generate", "improve"]
    }), 200


@ai_bp.route("/explain", methods=["POST"])
@jwt_required(optional=False)
def explain_code():
    """
    Explain a source code snippet: purpose, architectural flow, algorithms, inputs/outputs, edge cases.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body provided.", "error_code": "invalid_payload"}), 400

    code = data.get("code")
    if not code or not isinstance(code, str) or not code.strip():
        return jsonify({"error": "Field 'code' is required and cannot be empty.", "error_code": "validation_error"}), 400

    language = str(data.get("language", "")).strip()
    file_path = str(data.get("file_path", "")).strip()
    context = str(data.get("context", "")).strip()

    try:
        result = GeminiService.explain_code(
            code=code,
            language=language,
            file_path=file_path,
            context=context
        )
        return jsonify(result), 200
    except AIServiceError as e:
        logger.warning(f"AI Service error on explain: {e.message}")
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in explain_code endpoint: {e}")
        return jsonify({"error": "An internal server error occurred while processing your request.", "error_code": "internal_error"}), 500


@ai_bp.route("/debug", methods=["POST"])
@jwt_required(optional=False)
def debug_code():
    """
    Analyze code for bugs, logic errors, or exception stack traces, returning root causes and corrected code.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body provided.", "error_code": "invalid_payload"}), 400

    code = data.get("code")
    if not code or not isinstance(code, str) or not code.strip():
        return jsonify({"error": "Field 'code' is required and cannot be empty.", "error_code": "validation_error"}), 400

    error_message = str(data.get("error_message", "")).strip()
    language = str(data.get("language", "")).strip()
    file_path = str(data.get("file_path", "")).strip()
    context = str(data.get("context", "")).strip()

    try:
        result = GeminiService.debug_code(
            code=code,
            error_message=error_message,
            language=language,
            file_path=file_path,
            context=context
        )
        return jsonify(result), 200
    except AIServiceError as e:
        logger.warning(f"AI Service error on debug: {e.message}")
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in debug_code endpoint: {e}")
        return jsonify({"error": "An internal server error occurred while processing your request.", "error_code": "internal_error"}), 500


@ai_bp.route("/generate", methods=["POST"])
@jwt_required(optional=False)
def generate_code():
    """
    Generate code from a natural language specification.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body provided.", "error_code": "invalid_payload"}), 400

    prompt = data.get("prompt")
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "Field 'prompt' is required and cannot be empty.", "error_code": "validation_error"}), 400

    language = str(data.get("language", "javascript")).strip()
    context = str(data.get("context", "")).strip()

    try:
        result = GeminiService.generate_code(
            prompt=prompt,
            language=language,
            context=context
        )
        return jsonify(result), 200
    except AIServiceError as e:
        logger.warning(f"AI Service error on generate: {e.message}")
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in generate_code endpoint: {e}")
        return jsonify({"error": "An internal server error occurred while processing your request.", "error_code": "internal_error"}), 500


@ai_bp.route("/improve", methods=["POST"])
@jwt_required(optional=False)
def improve_code():
    """
    Suggest refactorings, optimizations, clean code patterns, and security enhancements for code.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body provided.", "error_code": "invalid_payload"}), 400

    code = data.get("code")
    if not code or not isinstance(code, str) or not code.strip():
        return jsonify({"error": "Field 'code' is required and cannot be empty.", "error_code": "validation_error"}), 400

    focus = str(data.get("focus", "all")).strip()
    language = str(data.get("language", "")).strip()
    file_path = str(data.get("file_path", "")).strip()
    context = str(data.get("context", "")).strip()

    try:
        result = GeminiService.improve_code(
            code=code,
            focus=focus,
            language=language,
            file_path=file_path,
            context=context
        )
        return jsonify(result), 200
    except AIServiceError as e:
        logger.warning(f"AI Service error on improve: {e.message}")
        return jsonify({"error": e.message, "error_code": e.error_code}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error in improve_code endpoint: {e}")
        return jsonify({"error": "An internal server error occurred while processing your request.", "error_code": "internal_error"}), 500
