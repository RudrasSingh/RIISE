from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import SQLALCHEMY_DATABASE_URL

# Database Setup with appropriate pooling settings for transaction pooler
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # Check connection validity before using it
    pool_size=10,        # Start with 10 connections in the pool
    max_overflow=20,     # Allow up to 20 additional connections
    pool_recycle=3600,   # Recycle connections after an hour
    pool_timeout=30      # Wait up to 30 seconds for a connection
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Supabase Setup (if still needed for other features)
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
