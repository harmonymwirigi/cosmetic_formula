# backend/app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("postgres://postgres.fjdlhdnwsfgxkirkxynl:JWYJzoejzNmBqzGt@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require&supa=base-pooler.x")
    print("Database URL:", DATABASE_URL)  # Debugging line to check the database URL
    # Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your_super_secret_key_change_this_in_production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # Frontend URL for redirects (IMPORTANT for OAuth)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")
    
    # CORS origins
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173").split(",")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    
    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Environment
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ('true', '1', 't')
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    class Config:
        env_file = ".env"

settings = Settings()

# Subscription configuration
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "formulas_per_month": 3,
        "features": [
            "AI Formula Generation",
            "Basic Formula Management"
        ]
    },
    "creator": {
        "name": "Creator",
        "price": 19.99,
        "formulas_per_month": 30,
        "features": [
            "AI Formula Generation",
            "PDF & Notion Export",
            "Formula Sharing"
        ]
    },
    "pro_lab": {
        "name": "Pro Lab",
        "price": 49.99,
        "formulas_per_month": float('inf'),  # Unlimited
        "features": [
            "Unlimited Formulas",
            "SOP & SDS Generation",
            "Regulatory Features",
            "Priority Support"
        ]
    }
}