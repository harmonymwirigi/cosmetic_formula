# backend/app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use the Supabase PostgreSQL URL
DATABASE_URL =  os.getenv("DATABASE_URL", "postgresql://postgres.fjdlhdnwsfgxkirkxynl:JWYJzoejzNmBqzGt@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require")

# Create engine with connection pooling options
engine = create_engine(
    DATABASE_URL,
    pool_size=10,               # Maximum number of connections to keep persistent
    max_overflow=20,            # Maximum number of connections to create above pool_size
    pool_timeout=30,            # Seconds to wait before giving up on getting a connection
    pool_recycle=300,           # Recycle connections after 5 minutes to avoid stale connections
    pool_pre_ping=True,         # Check connection validity before using it from the pool
    connect_args={"sslmode": "require"}  # Ensure SSL connection for security
)



SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()