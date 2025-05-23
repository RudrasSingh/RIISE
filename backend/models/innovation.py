from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ForeignKey
from database import Base

class Innovation(Base):
    __tablename__ = "innovation"
    __table_args__ = {"schema": "RIISE"}

    innovation_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String, nullable=True)
    level = Column(String, nullable=True)  # e.g. "institute", "state", "national"
    status = Column(String, nullable=True)  # e.g. "draft", "submitted", "approved"
    submitted_on = Column(Date, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=True)
    user_id = Column(Integer, ForeignKey("RIISE.users.user_id"), nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}