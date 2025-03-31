# backend/app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use the Supabase PostgreSQL URL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.fjdlhdnwsfgxkirkxynl:JWYJzoejzNmBqzGt@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()