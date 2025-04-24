# routes/user.py
from flask import Blueprint, request, jsonify, make_response
from database import supabase
from models.users import User
from database import SessionLocal
from sqlalchemy.orm import Session
from utils.auth import token_required, role_required
from werkzeug.utils import secure_filename
import os
from scholarly import scholarly
from datetime import datetime


user_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

# Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@user_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "user")  # Default to 'user' if no role is provided

    try:
        db = next(get_db())
        # Check if the user already exists in the local database
        if db.query(User).filter_by(email=email).first():
            return jsonify({"error": "User already exists, Kindly Login"}), 400

        # Sign up with Supabase
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
        except Exception as e:
            return jsonify({"error": f"Supabase signup failed: {str(e)}"}), 400

        if not response.user:
            return jsonify({"error": "Signup failed. No user returned."}), 400

        new_user = User(email=email, name=name, role=role)
        db.add(new_user)
        db.commit()

        return jsonify({
            "message": "User created successfully. Please check your email to verify."
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@user_bp.route("/login", methods=["POST"])
def login():
    db = next(get_db())

    # Check if user is already logged in by checking the cookie
    token = request.cookies.get("access_token")
    if token:
        try:
            user_info = supabase.auth.get_user(token)
            email = user_info.user.email
            role = db.query(User).filter_by(email=email).first().role

            return jsonify({
                "message": "Already logged in",
                "user": {
                    "email": email,
                    "role": role
                }
            }), 200
        except Exception:
            pass  # Invalid or expired token, continue to login flow

    # Fresh login flow
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not response.user or not response.session:
            return jsonify({"error": "Invalid credentials"}), 401

        user = response.user
        session = response.session

        res = make_response(jsonify({
            "message": "Login successful",
            "user": {
                "email": user.email,
                "role": db.query(User).filter_by(email=email).first().role,
            }
        }))

        #for produn
        res.set_cookie(
            key="access_token",
            value=session.access_token,
            httponly=True,
            secure=True,           # ✅ Required for HTTPS (like on Render)
            samesite="None",       # ✅ Required if your frontend is hosted elsewhere (cross-origin)
            max_age=3600
        )

        #for local testing
        # res.set_cookie(
        #     key="access_token",
        #     value=session.access_token,
        #     httponly=True,
        #     secure=False,  # Set to True in production with HTTPS
        #     samesite="None",
        #     max_age=3600
        # )

        return res

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@user_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Logged out successfully"}))
    response.set_cookie("access_token", "", expires=0)  # Clear the cookie
    return response

# Route to handle ID card upload for verification
@user_bp.route("/upload_id_card", methods=["POST"])
@token_required
def upload_id_card():
    # Get the uploaded file from the request
    file = request.files.get('id_card')
    if not file:
        return jsonify({"error": "No file part"}), 400

    # Secure the filename to avoid issues with special characters
    filename = secure_filename(file.filename)
    
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf')):
        return jsonify({"error": "Invalid file type. Only .jpg, .jpeg, .png, .pdf allowed."}), 400

    try:
        # Upload the file to Supabase storage
        response = supabase.storage.from_("id-card").upload(filename, file)
        
        # Get the file URL after upload
        file_url = supabase.storage.from_("id-card").get_public_url(filename).get('publicURL')

        # Now, update the user's record in the database with the file URL
        db = SessionLocal()
        user_in_db = db.query(User).filter_by(user_id=request.user['id']).first()

        if not user_in_db:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Update the user's ID card URL in the database
        user_in_db.id_card_url = file_url
        db.commit()
        db.close()

        # Update the user's status to not verified yet
        user_in_db.is_verified = False
        db.commit()

        return jsonify({"message": "ID card uploaded successfully. Waiting for verification."}), 200

    except Exception as e:
        return jsonify({"error": f"Error uploading ID card: {str(e)}"}), 500
    

@user_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    db = next(get_db())

    # Get the email from the token (supabase session)
    email = request.user.get("email")

    if not email:
        return jsonify({"error": "Email not found in session"}), 400

    # Retrieve user by email
    user = db.query(User).filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Return the full user profile
    user_data = {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "scholar_id": user.scholar_id,
        "h_index": user.h_index,
        "i10_index": user.i10_index,
        "total_citations": user.total_citations,
        "id_card_url": user.id_card_url,
        "is_verified": user.is_verified
    }

    return jsonify({
        "message": "Profile fetched successfully",
        "profile": user_data
    }), 200


def format_scholarly_paper(p, scholar_id=None):
    pub_date = None
    try:
        year = p.get("bib", {}).get("pub_year")
        month = p.get("bib", {}).get("pub_month", "01")
        pub_date = datetime.strptime(f"{year}-{month}-01", "%Y-%m-%d").date() if year else None
    except:
        pass

    return {
        "paper_id": None,
        "title": p.get("bib", {}).get("title"),
        "abstract": p.get("bib", {}).get("abstract"),
        "authors": ", ".join(p.get("bib", {}).get("author", "").split(" and ")),
        "publication_date": str(pub_date) if pub_date else None,
        "doi": p.get("pub_url", None),
        "status": "Published",
        "citations": p.get("num_citations", 0),
        "scholar_id": p.get("author_pub_id", ""),
        "source": "scholarly",
        "created_at": None,
        "updated_at": None,
        "user_id": None
    }


@user_bp.route("/update_profile", methods=["PUT"])
@token_required
def update_profile():
    data = request.json
    scholar_id = data.get("scholar_id")

    db = next(get_db())

    # Get the email from the token (supabase session)
    email = request.user.get("email")

    if not email:
        return jsonify({"error": "Email not found in session"}), 400

    # Retrieve user by email
    user = db.query(User).filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Update user scholar_id if provided
    if scholar_id:
        user.scholar_id = scholar_id

        # Fetch the scholar's data (h_index, i10_index, total_citations) using the scholarly package
        try:
            scholar_data = scholarly.fill(scholarly.search_author_id(scholar_id),sections=["basics", "indices"])
            print(scholar_data)
            # Fetch the h-index, i10-index, and total citations
            h_index = scholar_data.get("hindex", 0)
            i10_index = scholar_data.get("i10index", 0)
            total_citations = scholar_data.get("citedby", 0)


            # Update the user profile with the fetched scholar data
            user.h_index = h_index
            user.i10_index = i10_index
            user.total_citations = total_citations

            # # Optionally, you can also fetch publications (if needed)
            # publications = scholar_data.publications
            # formatted_publications = [format_scholarly_paper(pub, scholar_id) for pub in publications]
            # TODO:You can save these formatted papers to your database as well if required.

        except Exception as e:
            return jsonify({"error": f"Error fetching scholar data: {str(e)}"}), 500

    db.commit()
    db.close()

    return jsonify({
        "message": "Profile updated successfully."
    }), 200