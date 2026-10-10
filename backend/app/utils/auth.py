from functools import wraps
from flask import request, jsonify, g
from app.utils.security import decode_access_token


def jwt_required(optional=False):
    """
    Route decorator that validates Bearer JWT tokens.
    Sets g.user_id and g.user_email from the decoded token.
    If optional=True, unauthenticated requests are allowed (g.user_id will be None).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.cookies.get("access_token")
            
            # Fallback to Bearer token if not in cookies
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ", 1)[1]

            g.user_id = None
            g.user_email = None

            if token:
                payload = decode_access_token(token)
                if "error" not in payload:
                    g.user_id = payload.get("user_id")
                    g.user_email = payload.get("email")
                elif not optional:
                    return jsonify({"error": payload["error"]}), 401
            elif not optional:
                return jsonify({"error": "Authorization token required"}), 401

            return f(*args, **kwargs)
        return decorated_function
    return decorator
