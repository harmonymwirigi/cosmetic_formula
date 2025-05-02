# backend/app/utils/response_formatter.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app import models
from app.utils.notification_utils import get_formula_limit_by_subscription

def format_formula_response(formula, db):
    """
    Format a formula database object into a complete response with related data.
    
    Args:
        formula: The formula database object
        db: Database session
    
    Returns:
        Dictionary with formatted formula data including user, ingredients, and steps
    """
    # Get user information
    user = db.query(models.User).filter(models.User.id == formula.user_id).first()
    
    # Get ingredient associations from the formula_ingredients table
    sql = text(f"SELECT ingredient_id, percentage, \"order\" FROM formula_ingredients WHERE formula_id = :formula_id")
    ingredients_assoc = db.execute(sql, {"formula_id": formula.id}).fetchall()
    
    # Get ingredient details for each association
    ingredients_data = []
    for assoc in ingredients_assoc:
        ingredient = db.query(models.Ingredient).filter(models.Ingredient.id == assoc.ingredient_id).first()
        if ingredient:
            ingredients_data.append({
                "ingredient_id": assoc.ingredient_id,
                "percentage": assoc.percentage,
                "order": assoc.order,
                "ingredient": {
                    "id": ingredient.id,
                    "name": ingredient.name,
                    "inci_name": ingredient.inci_name,
                    "description": ingredient.description,
                    "recommended_max_percentage": ingredient.recommended_max_percentage,
                    "solubility": ingredient.solubility,
                    "phase": ingredient.phase,
                    "function": ingredient.function,
                    "is_premium": ingredient.is_premium,
                    "is_professional": ingredient.is_professional,
                    "created_at": ingredient.created_at,
                    "updated_at": ingredient.updated_at
                }
            })
    
    # Get steps
    steps_data = []
    for step in formula.steps:
        steps_data.append({
            "id": step.id,
            "formula_id": step.formula_id,
            "description": step.description,
            "order": step.order
        })
    
    # Add formula limit information to help UI display quota progress
    if user:
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == user.id).count()
        formula_limit = get_formula_limit_by_subscription(user.subscription_type)
        formula_limit_display = "Unlimited" if formula_limit == float('inf') else formula_limit
        formula_usage_percentage = 0 if formula_limit == float('inf') else min(100, (formula_count / formula_limit) * 100)
    else:
        formula_count = 0
        formula_limit_display = "Unknown"
        formula_usage_percentage = 0
    
    # Construct the response
    response = {
        "id": formula.id,
        "name": formula.name,
        "description": formula.description,
        "type": formula.type,
        "user_id": formula.user_id,
        "is_public": formula.is_public,
        "total_weight": formula.total_weight,
        "created_at": formula.created_at,
        "updated_at": formula.updated_at,
        "user": {
            "id": user.id if user else None,
            "email": user.email if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "is_active": user.is_active if user else None,
            "is_verified": user.is_verified if user else None,
            "subscription_type": user.subscription_type if user else None,
            "subscription_ends_at": user.subscription_expires_at if user else None,
            "created_at": user.created_at if user else None,
            "updated_at": user.updated_at if user else None,
            "formula_count": formula_count,
            "formula_limit": formula_limit_display,
            "formula_usage_percentage": formula_usage_percentage
        },
        "ingredients": ingredients_data,
        "steps": steps_data
    }
    
    return response