# backend/app/api/endpoints/ai_formula.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.services.ai_formula import AIFormulaGenerator
from app.services.openai_service import OpenAIFormulaGenerator
from app.utils.response_formatter import format_formula_response

router = APIRouter()

@router.post("/generate_formula", response_model=Dict[str, Any])
async def generate_formula(
    formula_request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate a formula using AI based on user preferences.
    
    formula_request should include:
    - product_type: The type of product (e.g., "serum", "moisturizer")
    - skin_concerns: List of skin concerns (e.g., ["dryness", "aging"])
    - preferred_ingredients: Optional list of ingredient IDs
    - avoided_ingredients: Optional list of ingredient IDs
    """
    # Check subscription tier - restrict AI formula to premium/professional
    if current_user.subscription_type == models.SubscriptionType.FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI formula generation requires a Premium or Professional subscription."
        )
    
    # Check if user has reached formula limit (for premium accounts)
    if current_user.subscription_type == models.SubscriptionType.PREMIUM:
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == current_user.id).count()
        if formula_count >= 10:  # Adjust the limit for premium users
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium accounts are limited to 10 AI-generated formulas per month. Please upgrade to Professional for unlimited formulas."
            )
    
    # Extract request data - handle the case where product_type is a dict
    if isinstance(formula_request.get("product_type"), dict):
        product_type = formula_request["product_type"].get("product_type")
        formula_name = formula_request["product_type"].get("formula_name")
        preferred_ingredients = formula_request["product_type"].get("preferred_ingredients", [])
        avoided_ingredients = formula_request["product_type"].get("avoided_ingredients", [])
    else:
        product_type = formula_request.get("product_type")
        formula_name = formula_request.get("formula_name")
        preferred_ingredients = formula_request.get("preferred_ingredients", [])
        avoided_ingredients = formula_request.get("avoided_ingredients", [])
    
    skin_concerns = formula_request.get("skin_concerns", [])
    
    # Get user profile data (so they don't need to input it repeatedly)
    user_profile = crud.get_user_profile(db, current_user.id)
    
    # Add profile data to the formula generation request
    profile_data = {}
    if user_profile:
        profile_data = {
            "skin_type": user_profile.skin_type,
            "skin_concerns": user_profile.skin_concerns,
            "sensitivities": user_profile.sensitivities,
            "climate": user_profile.climate
        }
    
    # Add professional fields if the user is on professional tier
    professional_data = {}
    if current_user.subscription_type == models.SubscriptionType.PROFESSIONAL:
        professional_data = {
            "brand_name": formula_request.get("brand_name", ""),
            "target_audience": formula_request.get("target_audience", ""),
            "target_markets": formula_request.get("target_markets", []),
            "brand_positioning": formula_request.get("brand_positioning", "")
        }
    
    # Validate input
    if not product_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product type is required"
        )
    
    try:
        # Use OpenAI service with tiered prompt generation
        generator = OpenAIFormulaGenerator(db)
        formula_data = await generator.generate_formula(
            product_type=product_type,
            skin_concerns=skin_concerns,
            user_subscription=current_user.subscription_type,
            preferred_ingredients=preferred_ingredients,
            avoided_ingredients=avoided_ingredients,
            user_profile=profile_data,
            professional_data=professional_data
        )
        
        # Convert the OpenAI response to a FormulaCreate schema
        formula_create = schemas.FormulaCreate(
            name=formula_name or formula_data.get("name", f"AI-Generated {product_type.title()}"),
            description=formula_data.get("description", ""),
            type=product_type.title(),
            is_public=False,
            total_weight=100.0,
            ingredients=formula_data.get("ingredients", []),
            steps=formula_data.get("steps", [])
        )
        
        # Create the formula in the database
        db_formula = crud.create_formula(db=db, formula=formula_create, user_id=current_user.id)
        
        # Format the response to match the expected schema
        return format_formula_response(db_formula, db)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"Error generating formula: {str(e)}")
        print(traceback.format_exc())
        
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
    
    # Get the rule-based generator to check compatibility
    generator = AIFormulaGenerator(db)
    
    # Get ingredient details
    ingredients = db.query(models.Ingredient).filter(
        models.Ingredient.id.in_(ingredient_ids)
    ).all()
    
    # Check for known incompatibilities
    issues = []
    for i, ing1 in enumerate(ingredients):
        for ing2 in ingredients[i+1:]:
            # Check the incompatible ingredients list from the rule-based generator
            for pair in generator.rules.INCOMPATIBLE_INGREDIENTS:
                if ((ing1.name in pair[0] and ing2.name in pair[1]) or
                    (ing1.name in pair[1] and ing2.name in pair[0])):
                    issues.append({
                        "ingredient1": {"id": ing1.id, "name": ing1.name},
                        "ingredient2": {"id": ing2.id, "name": ing2.name},
                        "reason": f"These ingredients may reduce each other's effectiveness."
                    })
    
    return {
        "compatible": len(issues) == 0,
        "issues": issues
    }