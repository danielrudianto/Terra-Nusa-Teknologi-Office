import os
from sqlalchemy import create_engine, MetaData
from databases import Database

# Load the database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create a database connection
database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL, echo=True)
metadata = MetaData()