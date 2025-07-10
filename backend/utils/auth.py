from functools import wraps
from flask import request, jsonify
from database import supabase, SessionLocal
from models.users import User


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("access_token")
        
        # Debug: Add logging to see if token is being received
        # print(f"DEBUG: Token received: {token is not None}")
        
        if not token:
            return jsonify({"error": "Session token missing"}), 401

        db = SessionLocal()
        try:
            # Get user from Supabase
            user = supabase.auth.get_user(token).user
            if not user:
                return jsonify({"error": "Invalid session"}), 401

            email = user.email

            # Get user from local database
            user_in_db = db.query(User).filter_by(email=email).first()

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
        finally:
            db.close()  # ✅ Always close the database connection

        return f(*args, **kwargs)
    return decorated


def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Check if user context exists (should be set by token_required)
            if not hasattr(request, 'user') or not request.user:
                return jsonify({"error": "User context not found"}), 401
                
            if request.user["role"] != required_role:
                return jsonify({"error": "Forbidden: Insufficient role"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def verified_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if user context exists
        if not hasattr(request, 'user') or not request.user:
            return jsonify({"error": "User context not found"}), 401
            
        db = SessionLocal()
        try:
            user_id = request.user["id"]
            # ✅ Fixed: Use user_id instead of id
            user = db.query(User).filter(User.user_id == user_id).first()

            if not user:
                return jsonify({"error": "User not found"}), 404
            if user.role != "admin":
                return jsonify({"error": "Unauthorized, admin required"}), 403
            if not user.is_verified:
                return jsonify({"error": "Admin account not verified"}), 403

            return func(*args, **kwargs)
        finally:
            db.close()  # ✅ Always close the database connection
            
    return decorated_function
