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
from app.utils.subscription_mapper import get_formula_limit, map_to_backend_type
from datetime import datetime

router = APIRouter()

# Updated schema for questionnaire-based generation
class QuestionnaireFormulaRequest(schemas.BaseModel):
    # Required fields
    purpose: str  # 'personal' or 'brand'
    product_category: str  # 'face_care', 'hair_care', 'body_care'
    formula_types: List[str]  # ['serum', 'cream', etc.]
    primary_goals: List[str]  # ['hydrate', 'anti_aging', etc.]
    
    # Target user (required for brand, optional for personal)
    target_user: Optional[Dict[str, Any]] = {}
    
    # Ingredient preferences
    preferred_ingredients_text: Optional[str] = ""
    avoided_ingredients_text: Optional[str] = ""
    
    # Brand and experience
    brand_vision: Optional[str] = ""
    desired_experience: Optional[List[str]] = []
    
    # Optional fields
    packaging_preferences: Optional[str] = ""
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    additional_notes: Optional[str] = ""
    
    # AI name generation flag
    generate_name: Optional[bool] = True


@router.post("/generate_formula_questionnaire", response_model=Dict[str, Any])
async def generate_formula_from_questionnaire(
    formula_request: QuestionnaireFormulaRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate a formula using AI based on comprehensive questionnaire responses.
    """
    
    print(f"Received questionnaire formula generation request for user {current_user.id}")
    
    # Check user's monthly formula count
    current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    formula_count = db.query(models.Formula).filter(
        models.Formula.user_id == current_user.id,
        models.Formula.created_at >= current_month_start
    ).count()
    
    # Get formula limit based on subscription
    formula_limit = get_formula_limit(current_user.subscription_type)
    
    # Check if limit is reached
    if formula_count >= formula_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You've reached your monthly limit of {formula_limit} formulas for your {current_user.subscription_type.value} plan. Upgrade for more formulas."
        )
    
    # Validate required fields
    if not formula_request.purpose:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purpose (personal/brand) is required"
        )
    
    if not formula_request.product_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product category is required"
        )
    
    if not formula_request.formula_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one formula type is required"
        )
    
    if not formula_request.primary_goals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one primary goal is required"
        )
    
    # For brand purpose, validate target user information
    if formula_request.purpose == 'brand':
        target_user = formula_request.target_user or {}
        if not target_user.get('gender') and not target_user.get('ageGroup'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user information is required for brand products"
            )
    
    try:
        # Use OpenAI service for questionnaire-based generation
        generator = OpenAIFormulaGenerator(db)
        
        # Convert request to dictionary for processing
        request_dict = formula_request.dict()
        
        # Generate formula using questionnaire data
        formula_data = await generator.generate_formula_from_questionnaire(
            questionnaire_data=request_dict,
            user_subscription=current_user.subscription_type,
            user_id=current_user.id
        )
        
        # Create the formula in the database
        ingredients_data = formula_data.get("ingredients", [])
        steps_data = formula_data.get("steps", [])
        
        # Convert to proper schema objects
        ingredients = []
        for ing_data in ingredients_data:
            if isinstance(ing_data, dict):
                ingredients.append(schemas.FormulaIngredientCreate(**ing_data))
            else:
                ingredients.append(ing_data)
        
        steps = []
        for step_data in steps_data:
            if isinstance(step_data, dict):
                steps.append(schemas.FormulaStepCreate(**step_data))
            else:
                steps.append(step_data)
        
        # Create the formula
        formula_create = schemas.FormulaCreate(
            name=formula_data.get("name", "AI-Generated Formula"),
            description=formula_data.get("description", ""),
            type=formula_data.get("type", formula_request.formula_types[0].title()),
            is_public=False,  # Default to private
            total_weight=100.0,
            ingredients=ingredients,
            steps=steps,
            msds=formula_data.get("msds", ""),
            sop=formula_data.get("sop", "")
        )
        
        # Save to database
        db_formula = await crud.create_formula(db=db, formula=formula_create, user_id=current_user.id)
        
        # Format the response properly
        response_data = {
            "id": db_formula.id,
            "name": db_formula.name,
            "description": db_formula.description,
            "type": db_formula.type,
            "user_id": db_formula.user_id,
            "is_public": db_formula.is_public,
            "total_weight": float(db_formula.total_weight or 100.0),
            "created_at": db_formula.created_at.isoformat() if db_formula.created_at else None,
            "updated_at": db_formula.updated_at.isoformat() if db_formula.updated_at else None,
            "questionnaire_data": {
                "purpose": formula_request.purpose,
                "product_category": formula_request.product_category,
                "formula_types": formula_request.formula_types,
                "primary_goals": formula_request.primary_goals,
                "target_user": formula_request.target_user or {}
            },
            "benefits": formula_data.get("benefits", ""),
            "usage": formula_data.get("usage", ""),
            "marketing_claims": formula_data.get("marketing_claims", ""),
            "ai_generated": True,
            "generation_method": "questionnaire",
            "ingredients_count": len(ingredients),
            "steps_count": len(steps)
        }
        
        print(f"Successfully created formula with ID: {db_formula.id}")
        return response_data
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the full error for debugging
        import traceback
        print(f"Error generating formula from questionnaire: {str(e)}")
        print(traceback.format_exc())
        
        # Return a more specific error message
        error_message = "Error generating formula. Please try again."
        if "OpenAI" in str(e):
            error_message = "AI service temporarily unavailable. Please try again in a few moments."
        elif "database" in str(e).lower():
            error_message = "Database error occurred. Please try again."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )

# Keep the original endpoint for backward compatibility
@router.post("/generate_formula", response_model=Dict[str, Any])
async def generate_formula(
    formula_request: schemas.FormulaGenerationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate a formula using AI based on user preferences and profile.
    
    This is the legacy endpoint for backward compatibility.
    New implementations should use the questionnaire endpoint.
    """
    
    print(f"Received legacy formula generation request type: {formula_request.product_type}")
    
    # Check user's monthly formula count
    current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    formula_count = db.query(models.Formula).filter(
        models.Formula.user_id == current_user.id,
        models.Formula.created_at >= current_month_start
    ).count()
    
    # Get formula limit based on subscription
    formula_limit = get_formula_limit(current_user.subscription_type)
    
    # Check if limit is reached
    if formula_count >= formula_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You've reached your monthly limit of {formula_limit} formulas for your {current_user.subscription_type.value} plan. Upgrade for more formulas."
        )
    
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
        # Use OpenAI service
        generator = OpenAIFormulaGenerator(db)
        
        # Convert legacy request to questionnaire format
        legacy_request_dict = formula_request.dict(exclude_unset=True)
        
        # Map legacy fields to questionnaire format
        questionnaire_data = {
            "purpose": "personal",  # Default for legacy requests
            "product_category": "face_care",  # Default
            "formula_types": [formula_request.product_type],
            "primary_goals": legacy_request_dict.get("skin_concerns", ["hydrate"]),
            "target_user": {
                "gender": legacy_request_dict.get("gender", ""),
                "ageGroup": str(legacy_request_dict.get("age", "")),
                "skinHairType": legacy_request_dict.get("skin_type", ""),
                "concerns": ""
            },
            "preferred_ingredients_text": "",
            "avoided_ingredients_text": legacy_request_dict.get("ingredients_to_avoid", ""),
            "brand_vision": "",
            "desired_experience": [],
            "generate_name": True
        }
        
        # Generate formula using questionnaire method
        formula_data = await generator.generate_formula_from_questionnaire(
            questionnaire_data=questionnaire_data,
            user_subscription=current_user.subscription_type,
            user_id=current_user.id
        )
        
        # Create the formula in the database
        ingredients_data = formula_data.get("ingredients", [])
        steps_data = formula_data.get("steps", [])
        
        # Convert to proper schema objects
        ingredients = []
        for ing_data in ingredients_data:
            if isinstance(ing_data, dict):
                ingredients.append(schemas.FormulaIngredientCreate(**ing_data))
            else:
                ingredients.append(ing_data)
        
        steps = []
        for step_data in steps_data:
            if isinstance(step_data, dict):
                steps.append(schemas.FormulaStepCreate(**step_data))
            else:
                steps.append(step_data)
        
        formula_create = schemas.FormulaCreate(
            name=formula_request.formula_name or formula_data.get("name", f"AI-Generated {formula_request.product_type.title()}"),
            description=formula_data.get("description", ""),
            type=formula_data.get("type", formula_request.product_type.title()),
            is_public=False,
            total_weight=100.0,
            ingredients=ingredients,
            steps=steps,
            msds=formula_data.get("msds", ""),
            sop=formula_data.get("sop", "")
        )
        
        # Create the formula in the database
        db_formula = await crud.create_formula(db=db, formula=formula_create, user_id=current_user.id)
        
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