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
from scholarly import scholarly
from datetime import datetime
from os import environ


user_bp = Blueprint("users", __name__, url_prefix="/api/v1/users")
ADMIN_SECRET_KEY = environ.get("ADMIN_SECRET")

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


@user_bp.route("/all-profile", methods=["GET"])
@token_required
# @role_required("admin")
def get_all_profiles():
    db = next(get_db())
    
    # Fetch all users except admins
    users = db.query(User).filter(User.role != "admin").all()

    profiles = []

    for user in users:
        user_id = user.user_id
        profile = {
            "user_id": user_id,
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
                "startups": db.query(Startup).filter_by(user_id=user_id).count(),
                "ipr": db.query(IPR).filter_by(user_id=user_id).count(),
                "innovations": db.query(Innovation).filter_by(user_id=user_id).count(),
                "research_papers": db.query(ResearchPaper).filter_by(user_id=user_id).count()
            }
        }
        profiles.append(profile)

    return jsonify({
        "message": "All user profiles fetched successfully",
        "profiles": profiles
    }), 200

@user_bp.route("/fetch-profile/<string:email>", methods=["GET"])
@token_required
# @role_required("admin")
def get_user_profile_by_email(email):
    db = next(get_db())

    # Fetch the user by email, excluding admins
    user = db.query(User).filter(User.email == email, User.role != "admin").first()

    if not user:
        return jsonify({"error": "User not found or is an admin"}), 404

    profile = {
        "user_id": user.user_id,
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
            "startups": db.query(Startup).filter_by(user_id=user.user_id).count(),
            "ipr": db.query(IPR).filter_by(user_id=user.user_id).count(),
            "innovations": db.query(Innovation).filter_by(user_id=user.user_id).count(),
            "research_papers": db.query(ResearchPaper).filter_by(user_id=user.user_id).count()
        }
    }

    return jsonify({
        "message": "User profile fetched successfully",
        "profile": profile
    }), 200


@user_bp.route('/verify-admin', methods=['POST'])
@token_required
def verify_admin():
    """
    Route to verify an admin user with a secret key
    Only users with role 'admin' can attempt verification
    """
    # Get database session
    db = SessionLocal()
    
    try:
        # Get the email from the token
        email = request.user.get("email")
        if not email:
            return jsonify({
                'success': False,
                'message': 'Email not found in token'
            }), 400
            
        # Get the current user from database
        current_user = db.query(User).filter_by(email=email).first()
        if not current_user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Check if user is admin
        if current_user.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Only users with admin role can be verified'
            }), 403
            
        # Check if already verified
        if current_user.is_verified:
            return jsonify({
                'success': True,
                'message': 'Admin already verified',
                'is_verified': True,
                'user_id': current_user.user_id,
                'email': current_user.email,
                'name': current_user.name,
                'role': current_user.role
            }), 200
            
        # Get secret key from request
        data = request.get_json()
        if not data or 'secret_key' not in data:
            return jsonify({
                'success': False,
                'message': 'Secret key is required'
            }), 400
            
        # Verify the secret key
        if data['secret_key'] == ADMIN_SECRET_KEY:
            current_user.is_verified = True
            db.commit()
            
            return jsonify({
                'success': True,
                'message': 'Admin verified successfully',
                'is_verified': True,
                'user_id': current_user.user_id,
                'email': current_user.email,
                'name': current_user.name,
                'role': current_user.role
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid secret key provided'
            }), 401
    
    except Exception as e:
        db.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
    
    finally:
        db.close()