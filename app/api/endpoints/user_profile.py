# backend/app/api/endpoints/user_profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app import models, crud
from app.database import get_db
from app.auth import get_current_user

router = APIRouter()

@router.get("/profile", response_model=Dict[str, Any])
def get_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the current user's profile"""
    profile = crud.get_user_profile(db, current_user.id)
    
    if not profile:
        # Return an empty profile if it doesn't exist yet
        return {
            "age": None,
            "gender": None,
            "is_pregnant": False,
            "fitzpatrick_type": None,
            "climate": None,
            "skin_type": None,
            "skin_concerns": [],
            "sensitivities": [],
            "skin_texture": [],
            "skin_redness": None,
            "end_of_day_skin_feel": None,
            "preferred_textures": [],
            "preferred_routine_length": None,
            "preferred_product_types": [],
            "lifestyle_factors": [],
            "ingredients_to_avoid": None,
            "hair_type": None,
            "hair_concerns": [],
            "brand_info": {}
        }
    
    # Format the response - handle all fields correctly
    response = {
        # Personal Info & Environment
        "age": profile.age,
        "gender": profile.gender,
        "is_pregnant": profile.is_pregnant if hasattr(profile, "is_pregnant") else False,
        "fitzpatrick_type": profile.fitzpatrick_type,
        "climate": profile.climate,
        
        # Skin Characteristics
        "skin_type": profile.skin_type,
        "breakout_frequency": profile.breakout_frequency,
        "skin_texture": profile.skin_texture or [],
        "skin_redness": profile.skin_redness,
        "end_of_day_skin_feel": profile.end_of_day_skin_feel,
        
        # Skin Concerns & Preferences
        "skin_concerns": profile.skin_concerns or [],
        "preferred_textures": profile.preferred_textures or [],
        "preferred_routine_length": profile.preferred_routine_length,
        "preferred_product_types": profile.preferred_product_types or [],
        "lifestyle_factors": profile.lifestyle_factors or [],
        "sensitivities": profile.sensitivities or [],
        "ingredients_to_avoid": profile.ingredients_to_avoid,
        
        # Hair Profile (check for attributes first)
        "hair_type": profile.hair_type if hasattr(profile, "hair_type") else None,
        "hair_concerns": profile.hair_concerns or [] if hasattr(profile, "hair_concerns") else [],
    }
    
    # Add brand info (for premium/professional users)
    if hasattr(profile, "brand_info"):
        response["brand_info"] = profile.brand_info or {}
    else:
        # Create a structure that matches what the frontend expects
        response["brand_info"] = {
            "brand_name": profile.brand_name,
            "development_stage": profile.development_stage,
            "product_category": profile.product_category,
            "target_demographic": profile.target_demographic,
            "sales_channels": profile.sales_channels or [],
            "target_texture": profile.target_texture,
            "performance_goals": profile.performance_goals or [],
            "desired_certifications": profile.desired_certifications or [],
            "regulatory_requirements": profile.regulatory_requirements,
            "restricted_ingredients": profile.restricted_ingredients,
            "preferred_actives": profile.preferred_actives,
            "production_scale": profile.production_scale,
            "price_positioning": profile.price_positioning,
            "competitor_brands": profile.competitor_brands,
            "brand_voice": profile.brand_voice,
            "product_inspirations": profile.product_inspirations
        } if all(hasattr(profile, attr) for attr in ["brand_name", "brand_voice"]) else {}
    
    return response

@router.post("/profile", response_model=Dict[str, Any])
def create_update_profile(
    profile_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create or update the user's profile"""
    # Filter brand_info if user is not premium/professional
    if current_user.subscription_type not in [models.SubscriptionType.PREMIUM, models.SubscriptionType.PROFESSIONAL]:
        if "brand_info" in profile_data:
            del profile_data["brand_info"]
    
    # Update or create profile
    profile = crud.update_user_profile(db, profile_data, current_user.id)
    
    # Use the same response formatting as get_profile
    # (This avoids duplication of the same logic)
    return get_profile(db=db, current_user=current_user)