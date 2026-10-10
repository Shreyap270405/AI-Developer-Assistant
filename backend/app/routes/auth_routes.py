import os
from flask import Blueprint, request, jsonify, g, make_response
from app.config import Config
from app.database import db
from app.models.user import User
from app.utils.security import hash_password, check_password, create_access_token
from app.utils.auth import jwt_required
from app.utils.logger import logger

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Valid email address is required"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "An account with this email already exists"}), 409

    new_user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name or email.split("@")[0]
    )

    try:
        db.session.add(new_user)
        db.session.commit()
        token = create_access_token(new_user.id, new_user.email)
        is_prod = (Config.FLASK_ENV == "production") or (os.getenv("COOKIE_SECURE", "false").lower() == "true")
        resp = make_response(jsonify({
            "message": "User registered successfully",
            "user": new_user.to_dict(),
            "token": token
        }), 201)
        resp.set_cookie(
            "access_token", 
            token, 
            httponly=True, 
            samesite="Lax",
            secure=is_prod
        )
        return resp
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registering user: {e}")
        return jsonify({"error": "Failed to create account"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(user.id, user.email)
    is_prod = (Config.FLASK_ENV == "production") or (os.getenv("COOKIE_SECURE", "false").lower() == "true")
    resp = make_response(jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "token": token
    }), 200)
    resp.set_cookie(
        "access_token", 
        token, 
        httponly=True, 
        samesite="Lax",
        secure=is_prod
    )
    return resp

@auth_bp.route("/logout", methods=["POST"])
def logout():
    is_prod = (Config.FLASK_ENV == "production") or (os.getenv("COOKIE_SECURE", "false").lower() == "true")
    resp = make_response(jsonify({"message": "Logged out successfully"}), 200)
    resp.delete_cookie("access_token", httponly=True, samesite="Lax", secure=is_prod)
    return resp


@auth_bp.route("/me", methods=["GET"])
@jwt_required(optional=False)
def get_me():
    user = db.session.get(User, g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_dict()}), 200
