from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ForeignKey
from database import Base

class Startup(Base):
    __tablename__ = "startup"
    __table_args__ = {"schema": "RIISE"}

    startup_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    founder = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    founded_date = Column(Date, nullable=True)
    status = Column(String, nullable=True)  # Active, Acquired, Stealth, Closed, etc.
    funding = Column(String, nullable=True)  # e.g. "Series A - $1M", "Bootstrapped"
    created_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=True)

    # FK to users table in RIISE schema
    user_id = Column(Integer, ForeignKey("RIISE.users.user_id", ondelete="SET NULL"), nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}