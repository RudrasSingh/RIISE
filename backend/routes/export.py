from flask import Blueprint, Response, request
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import numpy as np
from database import SessionLocal
from models.innovation import Innovation
from models.startup import Startup
from models.users import User
from models.IPR import IPR
from models.research import ResearchPaper
from utils.auth import token_required, role_required
from datetime import datetime

export_bp = Blueprint("export", __name__, url_prefix="/api/v1/export")

# Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to generate a chart
def generate_chart(data, title, chart_type="bar"):
    plt.figure(figsize=(7, 4))
    
    if chart_type == "bar":
        plt.bar(list(data.keys()), list(data.values()), color='skyblue')
    elif chart_type == "pie" and sum(data.values()) > 0:
        plt.pie(list(data.values()), labels=list(data.keys()), autopct='%1.1f%%')
        plt.axis('equal')
    
    plt.title(title)
    plt.tight_layout()
    
    # Save to BytesIO
    img_data = BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)
    plt.close()
    
    return img_data

# Helper function to generate the styled report with proper formatting
def generate_professional_report(user_data, title, charts=None):
    buffer = BytesIO()
    # Use landscape orientation for reports with many columns
    doc = SimpleDocTemplate(buffer, pagesize=(letter[1], letter[0]) if "All Users" in title else letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        alignment=1,  # Center alignment
        spaceAfter=20,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.darkblue,
        spaceAfter=10,
    )
    normal_style = styles["Normal"]
    
    # Create smaller text style for tables
    table_text_style = ParagraphStyle(
        "TableText",
        parent=styles["Normal"],
        fontSize=8,
        wordWrap='CJK'
    )

    elements = []

    # Add header (Logo + Title)
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 20))

    # Add admin/user details with proper label
    header_label = "Administrator Details" if "All Users" in title else "User Details"
    elements.append(Paragraph(header_label, section_header_style))
    
    user_details = [
        ["Name", user_data["name"]],
        ["Department", user_data["department"]],
        ["Designation", user_data["designation"]],
        ["Email", user_data["email"]],
        ["Phone", user_data["phone"]],
    ]
    user_table = Table(user_details, colWidths=[150, 300])
    user_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    elements.append(user_table)
    elements.append(Spacer(1, 20))

    # Add progress overview
    elements.append(Paragraph("Progress Overview", section_header_style))
    elements.append(Paragraph(user_data["progress_overview"], normal_style))
    elements.append(Spacer(1, 20))

    # Add charts if available
    if charts:
        elements.append(Paragraph("Visual Analytics", section_header_style))
        for chart_title, chart_data in charts.items():
            if chart_data:
                elements.append(Paragraph(chart_title, normal_style))
                # Set chart size based on orientation
                width = 500 if "All Users" in title else 400
                elements.append(Image(chart_data, width=width, height=200))
                elements.append(Spacer(1, 10))
        elements.append(Spacer(1, 20))

    # Add sections for IPR, Research, Innovations, and Startups
    for section, items in user_data["sections"].items():
        elements.append(Paragraph(section, section_header_style))
        if items and len(items) > 0:
            # Get all keys for table headers
            headers = list(items[0].keys())
            
            # Process data with proper formatting
            table_data = []
            # Format header row with bold text
            header_row = [f"<b>{key}</b>" for key in headers]
            table_data.append(header_row)
            
            # Format data rows with word wrapping
            for item in items:
                row = []
                for key in headers:
                    cell_value = str(item.get(key, ""))
                    # Wrap cell content in Paragraph for word wrapping
                    cell = Paragraph(cell_value, table_text_style)
                    row.append(cell)
                table_data.append(row)
            
            # Calculate appropriate column widths based on content and available space
            # For summary tables (typically wider), use smaller column widths
            available_width = 540 if "All Users" in title else 450  # Available width in points
            
            if "Summary" in section:
                # For summary tables, use dynamic column widths
                col_count = len(headers)
                col_width = min(available_width / col_count, 80)  # Limit max column width
                col_widths = [col_width] * col_count
            else:
                # For detailed tables, allocate space proportionally
                col_count = len(headers)
                col_widths = [available_width / col_count] * col_count
            
            # Create the table with calculated column widths
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Style the table
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("WORDWRAP", (0, 0), (-1, -1), True),
                    ]
                )
            )
            elements.append(table)
        else:
            elements.append(Paragraph("No data available.", normal_style))
        elements.append(Spacer(1, 20))

    # Add final summary
    elements.append(Paragraph("Final Summary", section_header_style))
    elements.append(Paragraph(user_data["final_summary"], normal_style))
    elements.append(Spacer(1, 50))

    # Add signature placeholder
    elements.append(Paragraph("Authorized Signature: ___________________________", normal_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Date: {user_data['date']}", normal_style))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Admin: Export all users data with detailed contributions
@export_bp.route("/admin/all", methods=["GET"])
@token_required
@role_required("admin")
def export_all_users_data():
    db = next(get_db())

    # Fetch all regular users
    users = db.query(User).filter_by(role="user").all()
    if not users:
        return Response("No users found", status=404)
    
    # Get total counts
    total_iprs = db.query(IPR).count()
    total_papers = db.query(ResearchPaper).count()
    total_innovations = db.query(Innovation).count()
    total_startups = db.query(Startup).count()
    
    # Get date for the report
    current_date = datetime.now().strftime("%d %B, %Y")

    # Prepare summary data for all users
    all_users_data = []
    
    # Store detailed data for all users
    all_users_detailed = {}
    
    for user in users:
        user_iprs = db.query(IPR).filter_by(user_id=user.user_id).all()
        user_papers = db.query(ResearchPaper).filter_by(user_id=user.user_id).all()
        user_innovations = db.query(Innovation).filter_by(user_id=user.user_id).all()
        user_startups = db.query(Startup).filter_by(user_id=user.user_id).all()
        
        all_users_data.append({
            "name": user.name,
            "email": user.email,
            "ipr_count": len(user_iprs),
            "paper_count": len(user_papers),
            "innovation_count": len(user_innovations),
            "startup_count": len(user_startups),
            "total_contributions": len(user_iprs) + len(user_papers) + len(user_innovations) + len(user_startups)
        })
        
        # Store detailed data for this user
        all_users_detailed[user.name] = {
            "IPRs": [
                {"Title": ipr.title, "Type": ipr.ipr_type, "Status": ipr.status} 
                for ipr in user_iprs
            ],
            "Research Papers": [
                {"Title": paper.title, "Citations": paper.citations if paper.citations else 0} 
                for paper in user_papers
            ],
            "Innovations": [
                {"Title": innovation.title, "Domain": innovation.domain} 
                for innovation in user_innovations
            ],
            "Startups": [
                {"Name": startup.name, "Status": startup.status} 
                for startup in user_startups
            ]
        }
    
    # Generate chart data
    user_names = [user["name"] for user in all_users_data]
    contribution_counts = [user["total_contributions"] for user in all_users_data]
    
    # Generate pie chart for overall distribution
    overall_data = {
        "IPRs": total_iprs,
        "Research Papers": total_papers,
        "Innovations": total_innovations,
        "Startups": total_startups
    }
    
    pie_chart = generate_chart(overall_data, "Distribution of Contributions", "pie")
    
    # Generate bar chart for user contributions
    plt.figure(figsize=(10, 6))
    x = np.arange(len(user_names))
    width = 0.2
    
    plt.bar(x - 1.5*width, [user["ipr_count"] for user in all_users_data], width, label='IPRs')
    plt.bar(x - 0.5*width, [user["paper_count"] for user in all_users_data], width, label='Papers')
    plt.bar(x + 0.5*width, [user["innovation_count"] for user in all_users_data], width, label='Innovations')
    plt.bar(x + 1.5*width, [user["startup_count"] for user in all_users_data], width, label='Startups')
    
    plt.xlabel('Users')
    plt.ylabel('Count')
    plt.title('Contribution Breakdown by User')
    plt.xticks(x, user_names, rotation=45)
    plt.legend()
    plt.tight_layout()
    
    # Save to BytesIO
    bar_chart = BytesIO()
    plt.savefig(bar_chart, format='png')
    bar_chart.seek(0)
    plt.close()
    
    # Prepare admin user data for the report
    admin_user = db.query(User).filter_by(role="admin").first()
    if not admin_user:
        admin_user = db.query(User).first()
    
    # Create sections for the report
    sections = {
        "User Contributions Summary": [
            {
                "User": user["name"], 
                "IPRs": user["ipr_count"],
                "Research Papers": user["paper_count"],
                "Innovations": user["innovation_count"],
                "Startups": user["startup_count"],
                "Total": user["total_contributions"]
            } 
            for user in all_users_data
        ]
    }
    
    # Add detailed user sections
    for username, details in all_users_detailed.items():
        # Only include users with contributions
        if sum(len(items) for items in details.values()) > 0:
            # Detailed IPRs
            if details["IPRs"]:
                sections[f"{username} - Intellectual Property Rights"] = details["IPRs"]
                
            # Detailed Research Papers
            if details["Research Papers"]:
                sections[f"{username} - Research Contributions"] = details["Research Papers"]
                
            # Detailed Innovations
            if details["Innovations"]:
                sections[f"{username} - Innovations"] = details["Innovations"]
                
            # Detailed Startups
            if details["Startups"]:
                sections[f"{username} - Startups"] = details["Startups"]
    
    user_data = {
        "name": admin_user.name,
        "department": "Research and Innovation Hub",
        "designation": "Administrator",
        "email": admin_user.email,
        "phone": "Contact Administration",
        "progress_overview": (
            f"This is an official report generated on {current_date} summarizing the research and innovation "
            f"activities across all users in the department. The report includes data on {total_iprs} Intellectual Property Rights (IPR) filings, "
            f"{total_papers} research publications, {total_innovations} innovations developed, and {total_startups} "
            f"startup ventures initiated by members of the Research and Innovation Hub."
        ),
        "sections": sections,
        "final_summary": (
            f"This report summarizes contributions from {len(users)} users, including a total of {total_iprs} IPRs, "
            f"{total_papers} research publications, {total_innovations} innovations, and {total_startups} startup ventures. "
            f"The Research and Innovation Hub continues to foster academic excellence, innovation, and entrepreneurship. "
            f"The department is committed to supporting these initiatives and furthering their impact "
            f"in the coming academic year."
        ),
        "date": current_date,
    }

    # Add charts
    charts = {
        "Contribution Distribution": pie_chart,
        "User Contribution Breakdown": bar_chart
    }

    # Generate professional report
    pdf_buffer = generate_professional_report(user_data, "Research and Innovation Hub: All Users Report", charts)

    # Return PDF as response
    return Response(
        pdf_buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=all_users_report.pdf"
        },
    )

# Admin: Export single user data by email
@export_bp.route("/admin/user/<email>", methods=["GET"])
@token_required
@role_required("admin")
def export_user_data_by_admin(email):
    db = next(get_db())
    
    # Fetch specified user by email
    user = db.query(User).filter_by(email=email).first()
    if not user:
        return Response("User not found", status=404)
    
    # Get user-specific data
    user_iprs = db.query(IPR).filter_by(user_id=user.user_id).all()
    user_papers = db.query(ResearchPaper).filter_by(user_id=user.user_id).all()
    user_innovations = db.query(Innovation).filter_by(user_id=user.user_id).all()
    user_startups = db.query(Startup).filter_by(user_id=user.user_id).all()
    
    # Get counts
    ipr_count = len(user_iprs)
    paper_count = len(user_papers)
    innovation_count = len(user_innovations)
    startup_count = len(user_startups)
    
    # Get date for the report
    current_date = datetime.now().strftime("%d %B, %Y")
    
    # Generate chart for user's contribution distribution
    contribution_data = {
        "IPRs": ipr_count,
        "Research Papers": paper_count,
        "Innovations": innovation_count,
        "Startups": startup_count
    }
    
    pie_chart = generate_chart(contribution_data, f"{user.name}'s Contribution Distribution", "pie")
    
    # Prepare timeline data if dates are available
    timeline_data = {}
    
    # Add data with dates to timeline
    for ipr in user_iprs:
        if ipr.filing_date:
            year = ipr.filing_date.year
            if year not in timeline_data:
                timeline_data[year] = {"IPRs": 0, "Papers": 0, "Innovations": 0, "Startups": 0}
            timeline_data[year]["IPRs"] += 1
            
    for paper in user_papers:
        if paper.publication_date:
            year = paper.publication_date.year
            if year not in timeline_data:
                timeline_data[year] = {"IPRs": 0, "Papers": 0, "Innovations": 0, "Startups": 0}
            timeline_data[year]["Papers"] += 1
    
    # Generate timeline chart if we have timeline data
    timeline_chart = None
    if timeline_data:
        plt.figure(figsize=(8, 4))
        years = sorted(timeline_data.keys())
        
        iprs = [timeline_data[year]["IPRs"] for year in years]
        papers = [timeline_data[year]["Papers"] for year in years]
        
        plt.plot(years, iprs, marker='o', label='IPRs')
        plt.plot(years, papers, marker='s', label='Papers')
        
        plt.title(f"{user.name}'s Contribution Timeline")
        plt.xlabel('Year')
        plt.ylabel('Count')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # Save to BytesIO
        timeline_chart_data = BytesIO()
        plt.savefig(timeline_chart_data, format='png')
        timeline_chart_data.seek(0)
        plt.close()
        
        timeline_chart = timeline_chart_data
    
    # Prepare user data
    user_data = {
        "name": user.name,
        "department": "Research and Innovation Hub",  # Updated department name for consistency
        "designation": user.role.capitalize(),
        "email": user.email,
        "phone": "Contact Administration",
        "progress_overview": (
            f"This report provides a detailed overview of {user.name}'s contributions as of {current_date}. "
            f"The user has contributed to {ipr_count} Intellectual Property Rights (IPR) filings, "
            f"{paper_count} research publications, {innovation_count} innovations, and {startup_count} "
            f"startup ventures."
        ),
        "sections": {
            "Intellectual Property Rights (IPR)": [
                {"Title": ipr.title, "Type": ipr.ipr_type, "Status": ipr.status, 
                 "Filing Date": str(ipr.filing_date) if ipr.filing_date else "Not filed"} 
                for ipr in user_iprs
            ],
            "Research Contributions": [
                {"Title": paper.title, 
                 "Authors": paper.authors if paper.authors else "Not specified",
                 "Citations": paper.citations if paper.citations else 0,
                 "Publication Date": str(paper.publication_date) if paper.publication_date else "Not published"}
                for paper in user_papers
            ],
            "Innovations Developed": [
                {"Title": innovation.title, 
                 "Domain": innovation.domain,
                 "Level": innovation.level,
                 "Status": innovation.status}
                for innovation in user_innovations
            ],
            "Startups Initiated": [
                {"Name": startup.name, 
                 "Industry": startup.industry, 
                 "Founder": startup.founder,
                 "Status": startup.status}
                for startup in user_startups
            ],
        },
        "final_summary": (
            f"{user.name} has made significant contributions with {ipr_count} IPR filings, "
            f"{paper_count} research publications, {innovation_count} innovations, and "
            f"{startup_count} startup ventures. This performance demonstrates strong engagement "
            f"across multiple domains of research and innovation."
        ),
        "date": current_date,
    }

    # Prepare charts
    charts = {
        "Contribution Distribution": pie_chart
    }
    
    if timeline_chart:
        charts["Contribution Timeline"] = timeline_chart

    # Generate professional report
    pdf_buffer = generate_professional_report(user_data, f"User Report: {user.name}", charts)

    # Return PDF as response
    return Response(
        pdf_buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=user_report_{user.name.replace(' ', '_')}.pdf"
        },
    )

# User: Export own data
@export_bp.route("/user", methods=["GET"])
@token_required
def export_own_data():
    db = next(get_db())
    user_id = request.user["id"]
    
    # Fetch user
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        return Response("User not found", status=404)
    
    # Get user-specific data
    user_iprs = db.query(IPR).filter_by(user_id=user_id).all()
    user_papers = db.query(ResearchPaper).filter_by(user_id=user_id).all()
    user_innovations = db.query(Innovation).filter_by(user_id=user_id).all()
    user_startups = db.query(Startup).filter_by(user_id=user_id).all()
    
    # Get counts
    ipr_count = len(user_iprs)
    paper_count = len(user_papers)
    innovation_count = len(user_innovations)
    startup_count = len(user_startups)
    
    # Get date for the report
    current_date = datetime.now().strftime("%d %B, %Y")
    
    # Generate chart for user's contribution distribution
    contribution_data = {
        "IPRs": ipr_count,
        "Research Papers": paper_count,
        "Innovations": innovation_count,
        "Startups": startup_count
    }
    
    pie_chart = generate_chart(contribution_data, "My Contribution Distribution", "pie")
    
    # Prepare timeline data if dates are available (consistent with admin view)
    timeline_data = {}
    
    # Add data with dates to timeline
    for ipr in user_iprs:
        if ipr.filing_date:
            year = ipr.filing_date.year
            if year not in timeline_data:
                timeline_data[year] = {"IPRs": 0, "Papers": 0, "Innovations": 0, "Startups": 0}
            timeline_data[year]["IPRs"] += 1
            
    for paper in user_papers:
        if paper.publication_date:
            year = paper.publication_date.year
            if year not in timeline_data:
                timeline_data[year] = {"IPRs": 0, "Papers": 0, "Innovations": 0, "Startups": 0}
            timeline_data[year]["Papers"] += 1
    
    # Generate timeline chart if we have timeline data
    timeline_chart = None
    if timeline_data:
        plt.figure(figsize=(8, 4))
        years = sorted(timeline_data.keys())
        
        iprs = [timeline_data[year]["IPRs"] for year in years]
        papers = [timeline_data[year]["Papers"] for year in years]
        
        plt.plot(years, iprs, marker='o', label='IPRs')
        plt.plot(years, papers, marker='s', label='Papers')
        
        plt.title("Your Contribution Timeline")
        plt.xlabel('Year')
        plt.ylabel('Count')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # Save to BytesIO
        timeline_chart_data = BytesIO()
        plt.savefig(timeline_chart_data, format='png')
        timeline_chart_data.seek(0)
        plt.close()
        
        timeline_chart = timeline_chart_data
    
    # Prepare user data
    user_data = {
        "name": user.name,
        "department": "Research and Innovation Hub",  # Updated department name for consistency
        "designation": user.role.capitalize(),
        "email": user.email,
        "phone": "Contact Administration",
        "progress_overview": (
            f"This report summarizes your contributions as of {current_date}. "
            f"You have contributed to {ipr_count} Intellectual Property Rights (IPR) filings, "
            f"{paper_count} research publications, {innovation_count} innovations, and {startup_count} "
            f"startup ventures."
        ),
        "sections": {
            "Intellectual Property Rights (IPR)": [
                {"Title": ipr.title, "Type": ipr.ipr_type, "Status": ipr.status, 
                 "Filing Date": str(ipr.filing_date) if ipr.filing_date else "Not filed"} 
                for ipr in user_iprs
            ],
            "Research Contributions": [
                {"Title": paper.title, 
                 "Authors": paper.authors if paper.authors else "Not specified",
                 "Citations": paper.citations if paper.citations else 0,
                 "Publication Date": str(paper.publication_date) if paper.publication_date else "Not published"}
                for paper in user_papers
            ],
            "Innovations Developed": [
                {"Title": innovation.title, 
                 "Domain": innovation.domain,
                 "Level": innovation.level,
                 "Status": innovation.status}
                for innovation in user_innovations
            ],
            "Startups Initiated": [
                {"Name": startup.name, 
                 "Industry": startup.industry, 
                 "Founder": startup.founder,
                 "Status": startup.status}
                for startup in user_startups
            ],
        },
        "final_summary": (
            f"You have made significant contributions with {ipr_count} IPR filings, "
            f"{paper_count} research publications, {innovation_count} innovations, and "
            f"{startup_count} startup ventures. Your continued engagement across multiple domains "
            f"of research and innovation is highly valued."
        ),
        "date": current_date,
    }

    # Prepare charts
    charts = {
        "Contribution Distribution": pie_chart
    }
    
    # Add timeline chart if available (consistent with admin view)
    if timeline_chart:
        charts["Your Contribution Timeline"] = timeline_chart

    # Generate professional report
    pdf_buffer = generate_professional_report(user_data, "My Progress Report", charts)

    # Return PDF as response
    return Response(
        pdf_buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=my_progress_report.pdf"
        },
    )