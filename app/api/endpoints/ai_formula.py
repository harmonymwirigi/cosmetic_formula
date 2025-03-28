# backend/app/api/endpoints/ai_formula.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.services.ai_formula import AIFormulaGenerator

router = APIRouter()

@router.post("/generate", response_model=schemas.Formula)
def generate_formula(
    formula_request: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate a formula using AI based on user preferences.
    
    formula_request should include:
    - product_type: The type of product (e.g., "serum", "moisturizer")
    - skin_concerns: List of skin concerns (e.g., ["dryness", "aging"])
    - preferred_ingredients: Optional list of ingredient IDs
    - avoided_ingredients: Optional list of ingredient IDs
    """
    # Check if user has reached formula limit (for free accounts)
    if current_user.subscription_type == models.SubscriptionType.FREE:
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == current_user.id).count()
        if formula_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free accounts are limited to 3 formulas. Please upgrade your subscription."
            )
    
    # Extract request data
    product_type = formula_request.get("product_type")
    skin_concerns = formula_request.get("skin_concerns", [])
    preferred_ingredients = formula_request.get("preferred_ingredients", [])
    avoided_ingredients = formula_request.get("avoided_ingredients", [])
    
    # Validate input
    if not product_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product type is required"
        )
    
    try:
        # Create AI generator and generate formula
        generator = AIFormulaGenerator(db)
        formula_data = generator.generate_formula(
            product_type=product_type,
            skin_concerns=skin_concerns,
            user_subscription=current_user.subscription_type,
            preferred_ingredients=preferred_ingredients,
            avoided_ingredients=avoided_ingredients
        )
        
        # Create the formula in the database
        return crud.create_formula(db=db, formula=formula_data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating formula: {str(e)}"
        )
    

@router.post("/check-compatibility")
def check_ingredient_compatibility(
    request: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Check compatibility between ingredients.
    
    request should include:
    - ingredient_ids: List of ingredient IDs to check
    """
    ingredient_ids = request.get("ingredient_ids", [])
    if not ingredient_ids or len(ingredient_ids) < 2:
        return {"compatible": True, "issues": []}
    
    # Simple implementation for now
    # In a real implementation, you would check actual ingredient compatibility
    # For now, we'll return a dummy response
    return {
        "compatible": True,
        "issues": []
    }