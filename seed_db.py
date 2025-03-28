# backend/seed_db.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal, Base
from app.models import User, Ingredient, SubscriptionType
from app.auth import get_password_hash
import json
from datetime import datetime, timedelta

# Create tables
Base.metadata.create_all(bind=engine)

# Create a database session
db = SessionLocal()

def seed_users():
    """Add demo users with different subscription levels"""
    print("Seeding users...")
    
    # Check if users already exist
    if db.query(User).count() > 0:
        print("Users already exist, skipping...")
        return
    
    # Create admin user
    admin_user = User(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_verified=True,
        subscription_type=SubscriptionType.PROFESSIONAL,
        subscription_expires_at=datetime.utcnow() + timedelta(days=365)
    )
    
    # Create premium user
    premium_user = User(
        first_name="Premium",
        last_name="User",
        email="premium@example.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_verified=True,
        subscription_type=SubscriptionType.PREMIUM,
        subscription_expires_at=datetime.utcnow() + timedelta(days=30)
    )
    
    # Create free user
    free_user = User(
        first_name="Free",
        last_name="User",
        email="free@example.com",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_verified=True,
        subscription_type=SubscriptionType.FREE
    )
    
    # Add users to database
    db.add(admin_user)
    db.add(premium_user)
    db.add(free_user)
    db.commit()
    print("Users added successfully")

def seed_ingredients():
    """Add sample ingredients to the database"""
    print("Seeding ingredients...")
    
    # Check if ingredients already exist
    if db.query(Ingredient).count() > 0:
        print("Ingredients already exist, skipping...")
        return
    
    # Sample ingredients data - this would typically be much more extensive
    ingredients_data = [
        # Water phase ingredients
        {
            "name": "Distilled Water",
            "inci_name": "Aqua",
            "description": "Base solvent for water-soluble ingredients",
            "recommended_max_percentage": 100.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Solvent",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Glycerin",
            "inci_name": "Glycerin",
            "description": "Humectant that attracts moisture to the skin",
            "recommended_max_percentage": 10.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Humectant",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Hyaluronic Acid (Low Molecular Weight)",
            "inci_name": "Sodium Hyaluronate",
            "description": "Hydrating ingredient that can penetrate deeper into the skin",
            "recommended_max_percentage": 2.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Humectant",
            "is_premium": True,
            "is_professional": False
        },
        {
            "name": "Niacinamide",
            "inci_name": "Niacinamide",
            "description": "Form of Vitamin B3 that brightens skin and improves barrier function",
            "recommended_max_percentage": 5.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Active",
            "is_premium": True,
            "is_professional": False
        },
        
        # Oil phase ingredients
        {
            "name": "Sweet Almond Oil",
            "inci_name": "Prunus Amygdalus Dulcis Oil",
            "description": "Lightweight oil rich in Vitamin E",
            "recommended_max_percentage": 20.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Emollient",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Jojoba Oil",
            "inci_name": "Simmondsia Chinensis Seed Oil",
            "description": "Actually a liquid wax that closely resembles human sebum",
            "recommended_max_percentage": 20.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Emollient",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Shea Butter",
            "inci_name": "Butyrospermum Parkii Butter",
            "description": "Rich butter that soothes and conditions skin",
            "recommended_max_percentage": 15.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Emollient",
            "is_premium": False,
            "is_professional": False
        },
        
        # Emulsifiers
        {
            "name": "Olivem 1000",
            "inci_name": "Cetearyl Olivate (and) Sorbitan Olivate",
            "description": "Natural PEG-free emulsifier derived from olive oil",
            "recommended_max_percentage": 8.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Emulsifier",
            "is_premium": True,
            "is_professional": False
        },
        {
            "name": "Polawax",
            "inci_name": "Emulsifying Wax NF",
            "description": "Reliable complete emulsifier for oil-in-water emulsions",
            "recommended_max_percentage": 10.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Emulsifier",
            "is_premium": False,
            "is_professional": False
        },
        
        # Actives and additives
        {
            "name": "Vitamin C (L-Ascorbic Acid)",
            "inci_name": "Ascorbic Acid",
            "description": "Potent antioxidant that brightens skin and boosts collagen production",
            "recommended_max_percentage": 20.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Antioxidant",
            "is_premium": True,
            "is_professional": False
        },
        {
            "name": "Retinol",
            "inci_name": "Retinol",
            "description": "Vitamin A derivative that promotes cell turnover and reduces signs of aging",
            "recommended_max_percentage": 1.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Active",
            "is_premium": True,
            "is_professional": True
        },
        {
            "name": "Alpha Lipoic Acid",
            "inci_name": "Thioctic Acid",
            "description": "Powerful antioxidant that is both water and oil-soluble",
            "recommended_max_percentage": 5.0,
            "solubility": "Both",
            "phase": "Cool Down Phase",
            "function": "Antioxidant",
            "is_premium": False,
            "is_professional": True
        },
        {
            "name": "Peptide Complex",
            "inci_name": "Acetyl Hexapeptide-8 (and) Acetyl Octapeptide-3",
            "description": "Amino acid complexes that signal skin cells to perform specific functions",
            "recommended_max_percentage": 10.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Active",
            "is_premium": True,
            "is_professional": True
        },
        
        # Preservatives
        {
            "name": "Liquid Germall Plus",
            "inci_name": "Propylene Glycol (and) Diazolidinyl Urea (and) Iodopropynyl Butylcarbamate",
            "description": "Broad-spectrum preservative effective against bacteria, yeast, and mold",
            "recommended_max_percentage": 0.5,
            "solubility": "Water-soluble",
            "phase": "Cool Down Phase",
            "function": "Preservative",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Phenoxyethanol (and) Ethylhexylglycerin",
            "inci_name": "Phenoxyethanol (and) Ethylhexylglycerin",
            "description": "Preservative system with broad-spectrum activity",
            "recommended_max_percentage": 1.0,
            "solubility": "Water-soluble",
            "phase": "Cool Down Phase",
            "function": "Preservative",
            "is_premium": False,
            "is_professional": False
        },
        
        # Thickeners and stabilizers
        {
            "name": "Xanthan Gum",
            "inci_name": "Xanthan Gum",
            "description": "Natural thickener and stabilizer for water-based formulations",
            "recommended_max_percentage": 1.0,
            "solubility": "Water-soluble",
            "phase": "Water Phase",
            "function": "Thickener",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Cetyl Alcohol",
            "inci_name": "Cetyl Alcohol",
            "description": "Fatty alcohol that thickens and adds slip to formulations",
            "recommended_max_percentage": 5.0,
            "solubility": "Oil-soluble",
            "phase": "Oil Phase",
            "function": "Thickener",
            "is_premium": False,
            "is_professional": False
        }
    ]
    
    # Add ingredients to database
    for ingredient_data in ingredients_data:
        ingredient = Ingredient(**ingredient_data)
        db.add(ingredient)
    
    db.commit()
    print(f"Added {len(ingredients_data)} ingredients to the database")

if __name__ == "__main__":
    try:
        seed_users()
        seed_ingredients()
        print("Database seeding completed successfully")
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()