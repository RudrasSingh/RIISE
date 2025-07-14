# routes/user.py
from flask import Blueprint, request, jsonify, make_response
from database import supabase
from models.users import User
from models.startup import Startup
from models.IPR import IPR
from models.innovation import Innovation
from models.research import ResearchPaper
from database import SessionLocal
from sqlalchemy.orm import Session
from utils.auth import token_required,role_required
from werkzeug.utils import secure_filename
from datetime import datetime
from os import environ
import requests
import os

user_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")
ADMIN_SECRET_KEY = environ.get("ADMIN_SECRET")

# SerpAPI configuration
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "your_serpapi_key_here")
SERPAPI_BASE_URL = "https://serpapi.com/search"

def serpapi_get_author_details(author_id):
    """Get detailed author information using SerpAPI"""
    params = {
        "engine": "google_scholar_author",
        "author_id": author_id,
        "api_key": SERPAPI_KEY
    }
    
    try:
        response = requests.get(SERPAPI_BASE_URL, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

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
            max_age=3600,
            path='/'
        )

        # for local testing
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
@token_required
def logout():
    try:
        # Get the current token to sign out from Supabase
        token = request.cookies.get("access_token")
        if token:
            try:
                # Sign out from Supabase
                supabase.auth.sign_out()
            except Exception as e:
                # Continue even if Supabase logout fails
                print(f"Supabase logout error: {str(e)}")
        
        # Create response
        response = make_response(jsonify({"message": "Logged out successfully"}))
        
        # Clear the cookie with the EXACT SAME parameters used in login
        # This matches your production cookie settings exactly
        response.set_cookie(
            key="access_token",
            value="",
            httponly=True,
            secure=True,           # ✅ Same as login - Required for HTTPS
            samesite="None",       # ✅ Same as login - Required for cross-origin
            expires=0,             # ✅ Expire immediately
            path='/',              # ✅ Same as login - Important for cookie clearing
            max_age=0              # ✅ Additional expiration setting
        )
        
        return response
        
    except Exception as e:
        # Even if there's an error, still try to clear the cookie
        response = make_response(jsonify({"message": "Logged out successfully"}))
        response.set_cookie(
            key="access_token",
            value="",
            httponly=True,
            secure=True,
            samesite="None",
            expires=0,
            path='/',
            max_age=0
        )
        return response, 200

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
    
    # Validate the file type (only jpg, jpeg, png, pdf)
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.pdf')):
        return jsonify({"error": "Invalid file type. Only .jpg, .jpeg, .png, .pdf allowed."}), 400

    try:
        # Get the user's id from the token
        user_id = request.user['id']
        
        # Define the file path within the user's own folder (using user_id)
        file_path = f"{user_id}/{filename}"  # User folder will be named with their ID
        
        # Upload the file to Supabase storage
        response = supabase.storage.from_("id-card").upload(
            file_path,
            file,
            {"content-type": file.content_type}  # Set content type for file
        )

        # Get the file's public URL after uploading
        file_url = supabase.storage.from_("id-card").get_public_url(file_path).get('publicURL')

        # Retrieve the user's record from the database
        db = SessionLocal()
        user_in_db = db.query(User).filter_by(user_id=user_id).first()

        if not user_in_db:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Update the user's ID card URL and set the verification status to False
        user_in_db.id_card_url = file_url
        user_in_db.is_verified = False
        db.commit()
        db.close()

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

    # Fetch counts for startups, IPR, innovations, and research
    startups_count = db.query(Startup).filter_by(user_id=user.user_id).count()
    ipr_count = db.query(IPR).filter_by(user_id=user.user_id).count()
    innovations_count = db.query(Innovation).filter_by(user_id=user.user_id).count()
    research_count = db.query(ResearchPaper).filter_by(user_id=user.user_id).count()

    # Return the full user profile along with counts
    user_data = {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "scholar_id": user.scholar_id,
        "h_index": user.h_index,
        "i10_index": user.i10_index,
        "total_citations": user.total_citations,
        "id_card_url": user.id_card_url,
        "is_verified": user.is_verified,
        "stats": {
            "startups": startups_count,
            "ipr": ipr_count,
            "innovations": innovations_count,
            "research": research_count
        }
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
    
    db = next(get_db())

    # Get the email from the token (supabase session)
    email = request.user.get("email")

    if not email:
        return jsonify({"error": "Email not found in session"}), 400

    # Retrieve user by email
    user = db.query(User).filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # List of fields that can be updated by the user
    updatable_fields = ["name", "scholar_id"]
    updated_fields = []

    # Update allowed fields if provided
    for field in updatable_fields:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
            updated_fields.append(field)

    # Special handling for scholar_id - fetch additional scholar data using SerpAPI
    if "scholar_id" in data and data["scholar_id"]:
        try:
            if not SERPAPI_KEY or SERPAPI_KEY == "your_serpapi_key_here":
                # Still update the scholar_id but return warning
                db.commit()
                db.close()
                return jsonify({
                    "message": "Profile updated successfully",
                    "updated_fields": updated_fields,
                    "warning": "SERPAPI_KEY not configured, scholar metrics not fetched"
                }), 200
            
            # Get detailed author information using SerpAPI
            result = serpapi_get_author_details(data["scholar_id"])
            
            if result and result.get("search_metadata", {}).get("status") == "Success":
                # Extract author information
                author_info = result.get("author", {})
                
                # Get citation indices from the cited_by table
                cited_by_table = author_info.get("cited_by", {}).get("table", [])
                if cited_by_table:
                    citation_data = cited_by_table[0]  # First row contains the data
                    h_index = citation_data.get("h_index", 0)
                    i10_index = citation_data.get("i10_index", 0)
                    total_citations = citation_data.get("citations", {}).get("all", 0)
                else:
                    h_index = 0
                    i10_index = 0
                    total_citations = 0

                # Update the user profile with the fetched scholar data
                user.h_index = h_index
                user.i10_index = i10_index
                user.total_citations = total_citations
                
                updated_fields.extend(["h_index", "i10_index", "total_citations"])
            else:
                # Still update the scholar_id but return warning
                db.commit()
                db.close()
                return jsonify({
                    "message": "Profile updated successfully",
                    "updated_fields": updated_fields,
                    "warning": "Scholar data not found for this ID"
                }), 200

        except Exception as e:
            # Still update the scholar_id but return error info
            db.commit()
            db.close()
            return jsonify({
                "message": "Profile updated successfully",
                "updated_fields": updated_fields,
                "error": f"Error fetching scholar data: {str(e)}"
            }), 200

    # Check if any fields were actually updated
    if not updated_fields:
        return jsonify({"error": "No valid fields provided for update"}), 400

    try:
        db.commit()
        db.close()

        return jsonify({
            "message": "Profile updated successfully",
            "updated_fields": updated_fields
        }), 200

    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@user_bp.route("/update_profile_field", methods=["PATCH"])
@token_required
def update_profile_field():
    """
    Update a specific field of the user's profile
    Supports updating: name, scholar_id
    """
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400

    db = next(get_db())

    # Get the email from the token (supabase session)
    email = request.user.get("email")

    if not email:
        return jsonify({"error": "Email not found in session"}), 400

    # Retrieve user by email
    user = db.query(User).filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Define which fields can be updated by users
    updatable_fields = {
        "name": str,
        "scholar_id": str
    }

    # Validate that only one field is being updated
    provided_fields = [key for key in data.keys() if key in updatable_fields]
    
    if len(provided_fields) == 0:
        return jsonify({
            "error": "No valid field provided",
            "updatable_fields": list(updatable_fields.keys())
        }), 400

    if len(provided_fields) > 1:
        return jsonify({
            "error": "Only one field can be updated at a time",
            "provided_fields": provided_fields
        }), 400

    field_name = provided_fields[0]
    field_value = data[field_name]

    # Validate field value type
    expected_type = updatable_fields[field_name]
    if not isinstance(field_value, expected_type):
        return jsonify({
            "error": f"Invalid type for {field_name}. Expected {expected_type.__name__}"
        }), 400

    # Additional validation for specific fields
    if field_name == "name" and (not field_value or len(field_value.strip()) < 2):
        return jsonify({"error": "Name must be at least 2 characters long"}), 400

    if field_name == "scholar_id" and (not field_value or len(field_value.strip()) < 5):
        return jsonify({"error": "Scholar ID must be at least 5 characters long"}), 400

    try:
        # Update the field
        setattr(user, field_name, field_value.strip() if isinstance(field_value, str) else field_value)
        
        # Special handling for scholar_id - fetch additional scholar data using SerpAPI
        if field_name == "scholar_id":
            try:
                if not SERPAPI_KEY or SERPAPI_KEY == "your_serpapi_key_here":
                    # Still update the scholar_id but return warning
                    db.commit()
                    db.close()
                    return jsonify({
                        "message": f"Profile {field_name} updated successfully",
                        "updated_field": field_name,
                        "new_value": field_value,
                        "warning": "SERPAPI_KEY not configured, scholar metrics not fetched"
                    }), 200
                
                # Get detailed author information using SerpAPI
                result = serpapi_get_author_details(field_value)
                
                if result and result.get("search_metadata", {}).get("status") == "Success":
                    # Extract author information
                    author_info = result.get("author", {})
                    
                    # Get citation indices from the cited_by table
                    cited_by_table = author_info.get("cited_by", {}).get("table", [])
                    if cited_by_table:
                        citation_data = cited_by_table[0]  # First row contains the data
                        h_index = citation_data.get("h_index", 0)
                        i10_index = citation_data.get("i10_index", 0)
                        total_citations = citation_data.get("citations", {}).get("all", 0)
                    else:
                        h_index = 0
                        i10_index = 0
                        total_citations = 0

                    # Update the user profile with the fetched scholar data
                    user.h_index = h_index
                    user.i10_index = i10_index
                    user.total_citations = total_citations
                    
                    db.commit()
                    db.close()

                    return jsonify({
                        "message": f"Profile {field_name} updated successfully",
                        "updated_field": field_name,
                        "new_value": field_value,
                        "scholar_data": {
                            "h_index": h_index,
                            "i10_index": i10_index,
                            "total_citations": total_citations
                        }
                    }), 200
                else:
                    # Still update the scholar_id but return warning
                    db.commit()
                    db.close()
                    return jsonify({
                        "message": f"Profile {field_name} updated successfully",
                        "updated_field": field_name,
                        "new_value": field_value,
                        "warning": "Scholar data not found for this ID"
                    }), 200

            except Exception as e:
                # Still update the scholar_id but return error info
                db.commit()
                db.close()
                return jsonify({
                    "message": f"Profile {field_name} updated successfully",
                    "updated_field": field_name,
                    "new_value": field_value,
                    "error": f"Error fetching scholar data: {str(e)}"
                }), 200

        # For other fields, just commit the change
        db.commit()
        db.close()

        return jsonify({
            "message": f"Profile {field_name} updated successfully",
            "updated_field": field_name,
            "new_value": field_value
        }), 200

    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

# ...existing code...