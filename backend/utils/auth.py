from functools import wraps
from flask import request, jsonify
from database import supabase, SessionLocal
from models.users import User # Assuming there's a User model that stores verification status

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("access_token")
        if not token:
            return jsonify({"error": "Session token missing"}), 401

        try:
            user = supabase.auth.get_user(token).user
            if not user:
                return jsonify({"error": "Invalid session"}), 401

            email = user.email

            db = SessionLocal()
            user_in_db = db.query(User).filter_by(email=email).first()
            db.close()

            if not user_in_db:
                return jsonify({"error": "User not found in internal DB"}), 404

            # Inject user identity into request context
            request.user = {
                "id": user_in_db.user_id,
                "email": email,
                "role": user_in_db.role,
                "is_verified": user_in_db.is_verified
            }

        except Exception as e:
            return jsonify({"error": "Token error", "detail": str(e)}), 401

        return f(*args, **kwargs)
    return decorated

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.user["role"] != required_role:
                return jsonify({"error": "Forbidden: Insufficient role"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def verified_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        db = SessionLocal()
        user_id = request.user["id"]
        user = db.query(User).filter(User.id == user_id).first()
        db.close()

        if not user:
            return jsonify({"error": "User not found"}), 404
        if user.role != "admin":
            return jsonify({"error": "Unauthorized, admin required"}), 403
        if not user.is_verified:  # Only check verification for admin users
            return jsonify({"error": "Admin account not verified"}), 403

        return func(*args, **kwargs)
    return decorated_function
