from flask import Blueprint, request, jsonify
from database import supabase
from models.research import ResearchPaper
from database import SessionLocal
from utils.auth import token_required, role_required
from sqlalchemy.orm import Session
from datetime import datetime
import time
import random
import os
import requests

research_bp = Blueprint("research", __name__, url_prefix="/api/v1/research")

# SerpAPI configuration
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "serpapi_key_here")
SERPAPI_BASE_URL = "https://serpapi.com/search"

def serpapi_search_author(author_name, num_results=10):
    """Search for author using SerpAPI Google Scholar API"""
    params = {
        "engine": "google_scholar",
        "q": f"author:{author_name}",
        "api_key": SERPAPI_KEY,
        "num": num_results
    }
    
    try:
        response = requests.get(SERPAPI_BASE_URL, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

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

def extract_author_id_from_result(result):
    """Extract author ID from search result"""
    try:
        organic_results = result.get("organic_results", [])
        
        for item in organic_results:
            if "author_info" in item and "author_id" in item["author_info"]:
                return item["author_info"]["author_id"]
            
            link = item.get("link", "")
            if "scholar.google.com/citations?user=" in link:
                author_id = link.split("user=")[1].split("&")[0]
                return author_id
        
        return None
    except:
        return None

# Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Format SerpAPI paper for response
def format_serpapi_paper(p, scholar_id=None):
    pub_date = None
    try:
        year = p.get("year")
        if year:
            pub_date = datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date()
    except:
        pass

    return {
        "paper_id": None,
        "title": p.get("title"),
        "abstract": p.get("snippet"),
        "authors": ", ".join([author.get("name", "") for author in p.get("authors", [])]),
        "publication_date": str(pub_date) if pub_date else None,
        "doi": p.get("link"),
        "status": "Published",
        "citations": p.get("cited_by", {}).get("value", 0),
        "scholar_id": p.get("result_id", ""),
        "source": "serpapi",
        "created_at": None,
        "updated_at": None,
        "user_id": None
    }

# Search by name
@research_bp.route("/fetch-by-name", methods=["GET"])
@token_required
def fetch_by_name():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Please provide a name"}), 400

    try:
        if not SERPAPI_KEY or SERPAPI_KEY == "your_serpapi_key_here":
            return jsonify({"error": "SERPAPI_KEY not configured"}), 500
        
        cleaned_name = name.replace("%20", " ").strip()
        result = serpapi_search_author(cleaned_name)
        
        if not result or result.get("search_metadata", {}).get("status") != "Success":
            return jsonify({"error": "Search failed"}), 500
        
        organic_results = result.get("organic_results", [])
        if not organic_results:
            return jsonify({"error": "Author not found"}), 404
        
        # Try to extract author ID
        author_id = extract_author_id_from_result(result)
        
        if not author_id:
            # Return basic information from search results
            first_result = organic_results[0]
            publications = organic_results[:3]
            formatted_pubs = []
            
            for pub in publications:
                try:
                    formatted_pubs.append(format_serpapi_paper(pub))
                except:
                    continue
            
            return jsonify({
                "scholar_id": None,
                "author_name": cleaned_name,
                "affiliation": first_result.get("author_info", {}).get("affiliation"),
                "email": None,
                "interests": [],
                "papers": formatted_pubs,
                "source": "serpapi"
            })
        
        # Get detailed information
        detailed_result = serpapi_get_author_details(author_id)
        
        if not detailed_result:
            return jsonify({"error": "Failed to fetch author details"}), 500
        
        # Extract author information
        author_info = detailed_result.get("author", {})
        
        # Get publications (limited to 10)
        publications = detailed_result.get("articles", [])[:10]
        formatted_pubs = []
        
        for pub in publications:
            try:
                formatted_pubs.append(format_serpapi_paper(pub, scholar_id=author_id))
            except:
                continue

        return jsonify({
            "scholar_id": author_id,
            "author_name": author_info.get("name"),
            "affiliation": author_info.get("affiliations"),
            "email": author_info.get("email"),
            "interests": author_info.get("interests", []),
            "papers": formatted_pubs,
            "source": "serpapi",
            "citation_indices": {
                "h_index": author_info.get("cited_by", {}).get("table", [{}])[0].get("h_index"),
                "i10_index": author_info.get("cited_by", {}).get("table", [{}])[0].get("i10_index"),
                "total_citations": author_info.get("cited_by", {}).get("table", [{}])[0].get("citations", {}).get("all")
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Failed to fetch author"}), 500

# Search by Scholar ID
@research_bp.route("/fetch-by-id/<string:scholar_id>", methods=["GET"])
@token_required
def fetch_by_scholar_id(scholar_id):
    try:
        if not SERPAPI_KEY or SERPAPI_KEY == "your_serpapi_key_here":
            return jsonify({"error": "SERPAPI_KEY not configured"}), 500
        
        result = serpapi_get_author_details(scholar_id)
        
        if not result or result.get("search_metadata", {}).get("status") != "Success":
            return jsonify({"error": "Scholar ID not found"}), 404
        
        # Extract author information
        author_info = result.get("author", {})
        
        # Get publications (limited to 10)
        publications = result.get("articles", [])[:10]
        formatted_pubs = []
        
        for pub in publications:
            try:
                formatted_pubs.append(format_serpapi_paper(pub, scholar_id=scholar_id))
            except:
                continue

        return jsonify({
            "scholar_id": scholar_id,
            "author_name": author_info.get("name"),
            "affiliation": author_info.get("affiliations"),
            "email": author_info.get("email"),
            "interests": author_info.get("interests", []),
            "papers": formatted_pubs,
            "source": "serpapi",
            "citation_indices": {
                "h_index": author_info.get("cited_by", {}).get("table", [{}])[0].get("h_index"),
                "i10_index": author_info.get("cited_by", {}).get("table", [{}])[0].get("i10_index"),
                "total_citations": author_info.get("cited_by", {}).get("table", [{}])[0].get("citations", {}).get("all")
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Failed to fetch data"}), 500

# Database operations
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

@research_bp.route("/update-paper/<int:paper_id>", methods=["PUT"])
@token_required
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
