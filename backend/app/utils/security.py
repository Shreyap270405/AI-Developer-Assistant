import os
from pathlib import Path
import datetime
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from app.config import Config

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """
    Ensure target_path resolves strictly within base_dir to prevent path traversal attacks.
    """
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return resolved_base in resolved_target.parents or resolved_base == resolved_target
    except Exception:
        return False

def sanitize_relative_path(path_str: str) -> str:
    """
    Normalizes a path string to POSIX forward-slash format and eliminates traversal characters.
    """
    # Replace backslashes with forward slashes
    clean = path_str.replace("\\", "/").strip()
    # Remove leading slashes and any .. references
    parts = [p for p in clean.split("/") if p and p != "." and p != ".."]
    return "/".join(parts)

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def check_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)

def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}
