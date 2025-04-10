# backend/app/utils/response_formatter.py
from typing import Dict, Any
from sqlalchemy.orm import Session
from app import models

def format_formula_response(formula: models.Formula, db: Session) -> Dict[str, Any]:
    """
    Format a formula database model into a standardized API response.
    
    Args:
        formula: The Formula database model
        db: Database session
        
    Returns:
        Dictionary with formatted formula data for API response
    """
    # Get ingredient details
    ingredient_details = []
    for item in formula.ingredients:
        # Get the ingredient from the join table
        formula_ingredient = db.query(models.formula_ingredients).filter(
            models.formula_ingredients.c.formula_id == formula.id,
            models.formula_ingredients.c.ingredient_id == item.id
        ).first()
        
        if formula_ingredient:
            ingredient_details.append({
                "ingredient_id": item.id,
                "name": item.name,
                "inci_name": item.inci_name,
                "percentage": formula_ingredient.percentage,
                "order": formula_ingredient.order,
                "phase": item.phase,
                "function": item.function
            })
    
    # Sort ingredients by order
    ingredient_details.sort(key=lambda x: x.get("order", 0))
    
    # Sort steps by order
    steps = []
    for step in formula.steps:
        steps.append({
            "id": step.id,
            "description": step.description,
            "order": step.order
        })
    
    steps.sort(key=lambda x: x.get("order", 0))
    
    # Format the response
    response = {
        "id": formula.id,
        "name": formula.name,
        "description": formula.description,
        "type": formula.type,
        "is_public": formula.is_public,
        "total_weight": formula.total_weight,
        "created_at": formula.created_at.isoformat() if formula.created_at else None,
        "updated_at": formula.updated_at.isoformat() if formula.updated_at else None,
        "user_id": formula.user_id,
        "ingredients": ingredient_details,
        "steps": steps
    }
    
    return response