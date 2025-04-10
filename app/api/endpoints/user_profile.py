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
            "skin_type": None,
            "skin_concerns": [],
            "sensitivities": [],
            "climate": None,
            "hair_type": None,
            "hair_concerns": [],
            "brand_info": None
        }
    
    # Format the response
    response = {
        "skin_type": profile.skin_type,
        "skin_concerns": profile.skin_concerns or [],
        "sensitivities": profile.sensitivities or [],
        "climate": profile.climate,
        "hair_type": profile.hair_type,
        "hair_concerns": profile.hair_concerns or [],
    }
    
    # Add brand info for premium/professional users
    if current_user.subscription_type in [models.SubscriptionType.PREMIUM, models.SubscriptionType.PROFESSIONAL]:
        response["brand_info"] = profile.brand_info or {}
    
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
    
    # Format the response (same as get_profile)
    response = {
        "skin_type": profile.skin_type,
        "skin_concerns": profile.skin_concerns or [],
        "sensitivities": profile.sensitivities or [],
        "climate": profile.climate,
        "hair_type": profile.hair_type,
        "hair_concerns": profile.hair_concerns or [],
    }
    
    # Add brand info for premium/professional users
    if current_user.subscription_type in [models.SubscriptionType.PREMIUM, models.SubscriptionType.PROFESSIONAL]:
        response["brand_info"] = profile.brand_info or {}
    
    return response