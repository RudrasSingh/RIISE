# models/users.py
from sqlalchemy import Column, String, Boolean, Integer
from database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "RIISE"}

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    role = Column(String, default="user")
    scholar_id = Column(String, nullable=True)
    h_index = Column(Integer, nullable=True)
    i10_index = Column(Integer, nullable=True)
    total_citations = Column(Integer, nullable=True)
    id_card_url = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    