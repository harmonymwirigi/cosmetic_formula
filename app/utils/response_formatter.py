# app/utils/response_formatter.py
from app import models
from sqlalchemy.orm import Session
from typing import Dict, Any

def format_formula_response(formula: models.Formula, db: Session) -> Dict[str, Any]:
    """
    Format a formula model for response according to the Formula schema.
    
    Args:
        formula: The formula model instance from the database
        db: The database session
        
    Returns:
        A dictionary with properly formatted formula data
    """
    # Get user information
    user = db.query(models.User).filter(models.User.id == formula.user_id).first()
    
    # Get ingredient associations from the formula_ingredients table
    from sqlalchemy import text
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
    
    # Construct the properly formatted response
    return {
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
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "subscription_type": user.subscription_type,
            "subscription_ends_at": user.subscription_expires_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        },
        "ingredients": ingredients_data,
        "steps": [
            {
                "id": step.id,
                "formula_id": step.formula_id,
                "description": step.description,
                "order": step.order
            }
            for step in formula.steps
        ]
    }