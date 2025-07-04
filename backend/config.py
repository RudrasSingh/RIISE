import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
load_dotenv()

# URL-encode the password for safety with special characters
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))

# Supabase API connection details
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Database connection details
DB_USER = os.getenv("DB_USER")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Construct the SQLAlchemy connection URL
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
)
