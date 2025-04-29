# backend/app/api/endpoints/ai_formula.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.services.ai_formula import AIFormulaGenerator
from app.services.openai_service import OpenAIFormulaGenerator
from app.utils.response_formatter import format_formula_response

from datetime import datetime
router = APIRouter()

# In backend/app/api/endpoints/ai_formula.py
# Update to improve validation and handle array fields correctly

@router.post("/generate_formula", response_model=Dict[str, Any])
async def generate_formula(
    formula_request: schemas.FormulaGenerationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate a formula using AI based on user preferences and profile.
    
    All users can access this endpoint, but monthly limits apply based on subscription.
    """
    # Add detailed logging 
    print(f"Received formula generation request type: {formula_request.product_type}")
    
    # Check user's monthly formula count
    current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    formula_count = db.query(models.Formula).filter(
        models.Formula.user_id == current_user.id,
        models.Formula.created_at >= current_month_start
    ).count()
    
    # Get formula limit based on subscription
    if current_user.subscription_type == models.SubscriptionType.FREE:
        formula_limit = 3
    elif current_user.subscription_type == models.SubscriptionType.CREATOR:
        formula_limit = 30
    else:  # PRO_LAB
        formula_limit = float('inf')  # Unlimited
    
    # Check if limit is reached
    if formula_count >= formula_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You've reached your monthly limit of {formula_limit} formulas for your {current_user.subscription_type.value} plan. Upgrade for more formulas."
        )
    
    # Get user profile or create one if it doesn't exist
    user_profile = db.query(models.UserProfile).filter(
        models.UserProfile.user_id == current_user.id
    ).first()
    
    if not user_profile:
        user_profile = models.UserProfile(user_id=current_user.id)
        db.add(user_profile)
        db.commit()
        db.refresh(user_profile)
    
    # Update request_dict to ensure all required fields are present and in the correct format
    request_dict = formula_request.dict(exclude_unset=True)
    
    # Ensure all array fields are actually arrays
    array_fields = [
        "skin_concerns", "sensitivities", "preferred_textures", 
        "preferred_product_types", "lifestyle_factors", "sales_channels",
        "performance_goals", "desired_certifications", "preferred_ingredients",
        "avoided_ingredients"
    ]
    
    for field in array_fields:
        if field in request_dict:
            if not isinstance(request_dict[field], list):
                print(f"Converting {field} to empty list")
                request_dict[field] = []
    
    # Update user profile with new data if provided
    profile_updated = False
    for key, value in request_dict.items():
        if value is not None and key not in [
            'product_type', 'formula_name', 'preferred_ingredients', 'avoided_ingredients'
        ]:
            # For list fields, we need to convert to JSON strings for the database
            if isinstance(value, list):
                value = json.dumps(value)
                
            setattr(user_profile, key, value)
            profile_updated = True
    
    if profile_updated:
        db.commit()
        db.refresh(user_profile)
    
    # Validate input
    if not formula_request.product_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product type is required"
        )
    
    # Check if product_type is valid
    valid_product_types = ["serum", "moisturizer", "cleanser", "toner", "mask", "essence"]
    if formula_request.product_type.lower() not in valid_product_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid product type. Must be one of: {', '.join(valid_product_types)}"
        )
    
    try:
        # Use OpenAI service with tiered prompt generation
        generator = OpenAIFormulaGenerator(db)
        
        # Ensure the request_dict has proper array types before sending
        for field in array_fields:
            if field in request_dict and not isinstance(request_dict[field], list):
                request_dict[field] = []
                
        # Log the sanitized request
        print(f"Sanitized request for OpenAI: {request_dict.get('product_type')}")
        
        try:
            formula_data = await generator.generate_formula(
                formula_request=request_dict,
                user_subscription=current_user.subscription_type,
                user_id=current_user.id
            )
        except ValueError as e:
            # Handle specific validation errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            # Log the error
            import traceback
            print(f"Error in OpenAI formula generation: {str(e)}")
            print(traceback.format_exc())
            
            # If there's an issue with OpenAI, fall back to rule-based generation
            print("Falling back to rule-based generation")
            fallback_generator = AIFormulaGenerator(db)
            
            # Make sure to have valid arrays for the fallback generator
            skin_concerns = request_dict.get("skin_concerns", [])
            preferred_ingredients = request_dict.get("preferred_ingredients", [])
            avoided_ingredients = request_dict.get("avoided_ingredients", [])
            
            if not isinstance(skin_concerns, list):
                skin_concerns = []
            if not isinstance(preferred_ingredients, list):
                preferred_ingredients = []
            if not isinstance(avoided_ingredients, list):
                avoided_ingredients = []
            
            rule_based_formula = fallback_generator.generate_formula(
                product_type=formula_request.product_type,
                skin_concerns=skin_concerns,
                user_subscription=current_user.subscription_type,
                preferred_ingredients=preferred_ingredients,
                avoided_ingredients=avoided_ingredients
            )
            
            # Convert the Pydantic model to a dictionary
            formula_data = {
                "name": rule_based_formula.name,
                "description": rule_based_formula.description,
                "type": rule_based_formula.type,
                "ingredients": [ingredient.dict() for ingredient in rule_based_formula.ingredients],
                "steps": [step.dict() for step in rule_based_formula.steps]
            }
        
        # Convert the response to a FormulaCreate schema
        # Make sure ingredients and steps are processed correctly
        ingredients_data = formula_data.get("ingredients", [])
        steps_data = formula_data.get("steps", [])
        
        # Convert to proper FormulaIngredientCreate/FormulaStepCreate objects if needed
        ingredients = []
        for ing in ingredients_data:
            if isinstance(ing, dict):
                ingredients.append(schemas.FormulaIngredientCreate(**ing))
            else:
                ingredients.append(ing)
        
        steps = []
        for step in steps_data:
            if isinstance(step, dict):
                steps.append(schemas.FormulaStepCreate(**step))
            else:
                steps.append(step)
        
        formula_create = schemas.FormulaCreate(
            name=formula_request.formula_name or formula_data.get("name", f"AI-Generated {formula_request.product_type.title()}"),
            description=formula_data.get("description", ""),
            type=formula_data.get("type", formula_request.product_type.title()),
            is_public=False,
            total_weight=100.0,
            ingredients=ingredients,
            steps=steps
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