from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ForeignKey
from database import Base

class IPR(Base):
    __tablename__ = "ipr"
    __table_args__ = {"schema": "RIISE"}

    ipr_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    ipr_type = Column(String, nullable=False)  # e.g., Patent, Trademark
    title = Column(String, nullable=False)
    ipr_number = Column(String, nullable=True)
    filing_date = Column(Date, nullable=True)
    status = Column(String, nullable=True)
    related_startup_id = Column(Integer, ForeignKey("RIISE.startup.startup_id"), nullable=True)
    created_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=True)
    user_id = Column(Integer, ForeignKey("RIISE.users.user_id"), nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}