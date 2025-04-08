# backend/app/seed_data.py
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
import random
from datetime import datetime, timedelta

def seed_knowledge_base(db: Session):
    """Seed knowledge base with sample data"""
    print("Seeding knowledge base data...")
    
    # Create categories
    categories = [
        {
            "name": "Beginner Formulation",
            "slug": "beginner-formulation",
            "description": "Getting started with cosmetic formulation",
            "is_premium": False,
            "is_professional": False
        },
        {
            "name": "Intermediate Techniques",
            "slug": "intermediate-techniques",
            "description": "Advanced techniques for experienced formulators",
            "is_premium": True,
            "is_professional": False
        },
        {
            "name": "Professional Formulation",
            "slug": "professional-formulation",
            "description": "Professional-grade formulation techniques",
            "is_premium": False,
            "is_professional": True
        },
        {
            "name": "Ingredient Deep Dives",
            "slug": "ingredient-deep-dives",
            "description": "Detailed information about cosmetic ingredients",
            "is_premium": True,
            "is_professional": False
        }
    ]
    
    # Add categories to DB
    db_categories = []
    for category_data in categories:
        category = models.ContentCategory(**category_data)
        db.add(category)
        db_categories.append(category)
    
    db.commit()
    
    # Create sample articles
    articles = [
        {
            "title": "Getting Started with Cosmetic Formulation",
            "slug": "getting-started-with-cosmetic-formulation",
            "content": """
# Getting Started with Cosmetic Formulation

Cosmetic formulation is both an art and a science. This guide will help you understand the basics of formulating your own cosmetic products.

## What You'll Need

- Basic lab equipment
- Quality ingredients
- Good formulation practices
- Patience and creativity

## Basic Formulation Principles

When creating cosmetics, it's important to understand the role of each ingredient in your formula...
            """,
            "excerpt": "Learn the basics of cosmetic formulation with this beginner's guide.",
            "category_id": 1,
            "author_id": 1,
            "is_premium": False,
            "is_professional": False,
            "view_count": random.randint(10, 100)
        },
        {
            "title": "Understanding Emulsion Stability",
            "slug": "understanding-emulsion-stability",
            "content": """
# Understanding Emulsion Stability

Emulsions are the backbone of many cosmetic formulations. This article explores how to create stable emulsions.

## Factors Affecting Stability

- Emulsifier choice and concentration
- Oil phase composition
- Water phase additives
- Processing techniques
- Temperature control

## Advanced Techniques

For particularly challenging formulations, consider these advanced techniques...
            """,
            "excerpt": "Learn how to create stable emulsions for your cosmetic formulations.",
            "category_id": 2,
            "author_id": 1,
            "is_premium": True,
            "is_professional": False,
            "view_count": random.randint(50, 200)
        }
    ]
    
    # Add articles to DB
    for article_data in articles:
        article = models.KnowledgeArticle(**article_data)
        db.add(article)
    
    db.commit()
    
    # Create sample tutorials
    tutorials = [
        {
            "title": "Creating Your First Moisturizer",
            "description": "A step-by-step guide to formulating a basic moisturizer",
            "is_premium": False,
            "is_professional": False
        },
        {
            "title": "Advanced Serum Formulation",
            "description": "Learn how to create professional-grade serums",
            "is_premium": True,
            "is_professional": False
        }
    ]
    
    # Add tutorials to DB
    db_tutorials = []
    for tutorial_data in tutorials:
        tutorial = models.Tutorial(**tutorial_data)
        db.add(tutorial)
        db_tutorials.append(tutorial)
    
    db.commit()
    
    # Create tutorial steps
    tutorial_steps = [
        # Steps for first tutorial
        {
            "tutorial_id": 1,
            "title": "Gather Your Ingredients",
            "content": "For this basic moisturizer, you'll need the following ingredients...",
            "order": 1
        },
        {
            "tutorial_id": 1,
            "title": "Prepare the Water Phase",
            "content": "In a clean beaker, combine all water-soluble ingredients...",
            "order": 2
        },
        {
            "tutorial_id": 1,
            "title": "Prepare the Oil Phase",
            "content": "In a separate container, combine all oil-soluble ingredients...",
            "order": 3
        },
        # Steps for second tutorial
        {
            "tutorial_id": 2,
            "title": "Select Active Ingredients",
            "content": "Choose appropriate active ingredients based on your target skin concerns...",
            "order": 1
        },
        {
            "tutorial_id": 2,
            "title": "Determine Compatibility",
            "content": "Verify the compatibility of your selected active ingredients...",
            "order": 2
        }
    ]
    
    # Add tutorial steps to DB
    for step_data in tutorial_steps:
        step = models.TutorialStep(**step_data)
        db.add(step)
    
    db.commit()
    
    print("Knowledge base data seeded successfully!")

def seed_shop_data(db: Session):
    """Seed shop with sample data"""
    print("Seeding shop data...")
    
    # Create product categories
    categories = [
        {
            "name": "Active Ingredients",
            "slug": "active-ingredients",
            "description": "Specialized ingredients for targeted treatment"
        },
        {
            "name": "Emollients & Oils",
            "slug": "emollients-oils",
            "description": "Natural and synthetic oils for moisture and texture"
        },
        {
            "name": "Preservatives",
            "slug": "preservatives",
            "description": "Keep your formulations safe and fresh"
        },
        {
            "name": "Equipment",
            "slug": "equipment",
            "description": "Tools and equipment for cosmetic formulation"
        }
    ]
    
    # Add categories to DB
    db_categories = []
    for category_data in categories:
        category = models.ProductCategory(**category_data)
        db.add(category)
        db_categories.append(category)
    
    db.commit()
    
    # Create sample products
    products = [
        {
            "name": "Niacinamide Powder",
            "slug": "niacinamide-powder",
            "description": "Pure niacinamide powder for creating serums and treatments. Known for reducing sebum production and improving skin texture.",
            "short_description": "Pure vitamin B3 for skin brightening and texture improvement.",
            "price": 14.99,
            "stock_quantity": 100,
            "category_id": 1,
            "is_featured": True
        },
        {
            "name": "Hyaluronic Acid (Low Molecular Weight)",
            "slug": "hyaluronic-acid-low-molecular-weight",
            "description": "Low molecular weight hyaluronic acid for deeper penetration. Creates hydrating serums with excellent skin feel.",
            "short_description": "Deeply hydrating hyaluronic acid for serums and moisturizers.",
            "price": 19.99,
            "sale_price": 17.99,
            "stock_quantity": 75,
            "category_id": 1,
            "is_featured": True
        },
        {
            "name": "Jojoba Oil (Organic)",
            "slug": "jojoba-oil-organic",
            "description": "Organic, cold-pressed jojoba oil that closely resembles human sebum. Excellent emollient for all skin types.",
            "short_description": "Premium organic jojoba oil for natural formulations.",
            "price": 12.99,
            "stock_quantity": 120,
            "category_id": 2
        },
        {
            "name": "Digital Scale (0.01g precision)",
            "slug": "digital-scale",
            "description": "High-precision digital scale for accurate ingredient measurement. Essential for successful formulation.",
            "short_description": "Precision scale for accurate formulation.",
            "price": 49.99,
            "stock_quantity": 25,
            "category_id": 4,
            "is_featured": True
        },
        {
            "name": "Broad Spectrum Preservative",
            "slug": "broad-spectrum-preservative",
            "description": "Effective broad-spectrum preservative system for water-containing formulations. Protects against bacteria, yeast, and mold.",
            "short_description": "Complete preservative system for water-based formulations.",
            "price": 15.99,
            "stock_quantity": 80,
            "category_id": 3
        }
    ]
    
    # Add products to DB
    for product_data in products:
        product = models.Product(**product_data)
        db.add(product)
    
    db.commit()
    
    # Create inventory entries
    products = db.query(models.Product).all()
    for product in products:
        inventory = models.Inventory(
            product_id=product.id,
            quantity=product.stock_quantity,
            reserved_quantity=0,
            reorder_level=10
        )
        db.add(inventory)
    
    db.commit()
    
    print("Shop data seeded successfully!")

def seed_notification_preferences(db: Session):
    """Seed notification preferences for existing users"""
    print("Seeding notification preferences...")
    
    # Get all users
    users = db.query(models.User).all()
    
    # Notification types
    notification_types = [
        "system", "order", "formula", "subscription", "knowledge"
    ]
    
    # Create default preferences for each user
    for user in users:
        for notification_type in notification_types:
            # Check if preference already exists
            existing = db.query(models.NotificationPreference).filter(
                models.NotificationPreference.user_id == user.id,
                models.NotificationPreference.notification_type == notification_type
            ).first()
            
            if not existing:
                preference = models.NotificationPreference(
                    user_id=user.id,
                    notification_type=notification_type,
                    email_enabled=True,
                    sms_enabled=False,
                    push_enabled=True
                )
                db.add(preference)
    
    db.commit()
    
    print("Notification preferences seeded successfully!")

def run_all_seeds():
    """Run all seed functions"""
    db = next(get_db())
    
    seed_knowledge_base(db)
    seed_shop_data(db)
    seed_notification_preferences(db)
    
    print("All seed data created successfully!")

if __name__ == "__main__":
    run_all_seeds()