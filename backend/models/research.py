from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ForeignKey
from database import Base

class ResearchPaper(Base):
    __tablename__ = "research_paper"
    __table_args__ = {"schema": "RIISE"}

    paper_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    title = Column(String, nullable=False)
    abstract = Column(Text, nullable=True)
    authors = Column(String, nullable=True)  # Comma-separated names (or move to separate table for 1:N)
    publication_date = Column(Date, nullable=True)
    doi = Column(String, nullable=True)
    status = Column(String, nullable=True)  # e.g., Published, Under Review
    citations = Column(Integer, nullable=True)
    scholar_id = Column(String, nullable=True)  # Google Scholar unique paper ID
    source = Column(String, nullable=True, default="manual")  # manual, scholarly, or imported

    created_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=True)

    # FK to users table in RIISE schema
    user_id = Column(Integer, ForeignKey("RIISE.users.user_id", ondelete="CASCADE"), nullable=False)
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}