from flask import Blueprint, request, jsonify
from database import supabase
from models.research import ResearchPaper
from database import SessionLocal
from utils.auth import token_required, role_required
from sqlalchemy.orm import Session
from scholarly import scholarly
from datetime import datetime
import re

research_bp = Blueprint("research", __name__, url_prefix="/api/v1/research")

# Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility: Parse scholarly publication into your ResearchPaper-like schema
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

# Route 1: Search by Scholar ID
@research_bp.route("/fetch-by-id/<string:scholar_id>", methods=["GET"])
@token_required
def fetch_by_scholar_id(scholar_id):
    try:
        author = scholarly.search_author_id(scholar_id)
        filled = scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])
        pubs = [scholarly.fill(p) for p in filled.get("publications", [])[:3]] #limit to 3 publications as backend is overloading
        # pubs = [scholarly.fill(p) for p in filled.get("publications", [])] #no limit to publications as backend is overloading

        formatted = [format_scholarly_paper(p, scholar_id=scholar_id) for p in pubs]

        return jsonify({
            "scholar_id": scholar_id,
            "author_name": filled.get("name"),
            "affiliation": filled.get("affiliation"),
            "email": filled.get("email_domain"),
            "interests": filled.get("interests", []),
            "papers": formatted
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch data for Scholar ID: {str(e)}"}), 500

# Route 2: Search by Name
@research_bp.route("/fetch-by-name", methods=["GET"])
@token_required
def fetch_by_name():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Please provide a name"}), 400

    try:
        author = scholarly.search_author(name)
        first = next(author, None)
        if not first:
            return jsonify({"error": "Author not found"}), 404

        filled = scholarly.fill(first, sections=["basics", "indices", "counts", "publications"])
        pubs = [scholarly.fill(p) for p in filled.get("publications", [])[:3]]
        formatted = [format_scholarly_paper(p, scholar_id=filled.get("scholar_id")) for p in pubs]

        return jsonify({
            "scholar_id": filled.get("scholar_id"),
            "author_name": filled.get("name"),
            "affiliation": filled.get("affiliation"),
            "email": filled.get("email_domain"),
            "interests": filled.get("interests", []),
            "papers": formatted
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch author: {str(e)}"}), 500
    

# Admin or User: View research papers
@research_bp.route("/", methods=["GET"])
@token_required
def get_all_research_papers():
    db = next(get_db())
    role = request.user["role"]
    user_id = request.user["id"]

    if role == "admin":
        papers = db.query(ResearchPaper).all()
    else:
        papers = db.query(ResearchPaper).filter(ResearchPaper.user_id == user_id).all()

    return jsonify([{
        "paper_id": p.paper_id,
        "title": p.title,
        "abstract": p.abstract,
        "authors": p.authors,
        "publication_date": str(p.publication_date) if p.publication_date else None,
        "doi": p.doi,
        "status": p.status,
        "created_at": str(p.created_at) if p.created_at else None,
        "updated_at": str(p.updated_at) if p.updated_at else None,
        "user_id": p.user_id,
    } for p in papers])

# Add research paper
@research_bp.route("/add-paper", methods=["POST"])
@token_required
def add_research_paper():
    db = next(get_db())
    data = request.json
    user_id = request.user["id"]

    new_paper = ResearchPaper(
        title=data.get("title"),
        abstract=data.get("abstract"),
        authors=data.get("authors"),
        publication_date=data.get("publication_date"),
        doi=data.get("doi"),
        status=data.get("status"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        user_id=user_id
    )
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)

    return jsonify({"message": "Research paper created", "paper_id": new_paper.paper_id})

# Update research paper
@research_bp.route("/update-paper/<int:paper_id>", methods=["PUT"])
@token_required
@role_required("admin")
def update_research_paper(paper_id):
    db = next(get_db())
    user_id = request.user["id"]
    role = request.user["role"]

    paper = db.query(ResearchPaper).filter(ResearchPaper.paper_id == paper_id).first()
    if not paper:
        return jsonify({"error": "Research paper not found"}), 404

    if role != "admin" and paper.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    allowed_fields = ["title", "abstract", "authors", "publication_date", "doi", "status", "created_at", "updated_at"]
    for key, value in data.items():
        if key in allowed_fields:
            setattr(paper, key, value)
        else:
            return jsonify({"error": f"Invalid Field - Cannot update: {key}"}), 400

    db.commit()
    db.refresh(paper)

    return jsonify({"message": "Research paper updated"})

# Delete research paper (Admin only)
@research_bp.route("/delete-paper/<int:paper_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_research_paper(paper_id):
    db = next(get_db())
    paper = db.query(ResearchPaper).filter(ResearchPaper.paper_id == paper_id).first()
    if not paper:
        return jsonify({"error": "Research paper not found"}), 404

    db.delete(paper)
    db.commit()
    return jsonify({"message": "Research paper deleted"})
