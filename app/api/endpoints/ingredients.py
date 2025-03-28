# backend/app/api/endpoints/ingredients.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter()


@router.get("/list", response_model=List[schemas.Ingredient])
def read_ingredients(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    phase: Optional[str] = None,
    function: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get all ingredients with optional filtering.
    """
    # Apply subscription-based filtering
    is_premium = None  # Default: show all
    is_professional = None  # Default: show all
    
    # Basic users can't see premium or professional ingredients
    if current_user.subscription_type == models.SubscriptionType.FREE:
        is_premium = False
        is_professional = False
    # Premium users can see premium but not professional ingredients
    elif current_user.subscription_type == models.SubscriptionType.PREMIUM:
        is_professional = False
    
    ingredients = crud.get_ingredients(
        db, 
        skip=skip, 
        limit=limit,
        search=search,
        phase=phase,
        function=function,
        is_premium=is_premium,
        is_professional=is_professional
    )
    return ingredients

@router.get("/functions", response_model=List[str])
def get_ingredient_functions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get all unique ingredient functions.
    """
    # Query distinct function values
    functions = db.query(models.Ingredient.function).distinct().filter(models.Ingredient.function.isnot(None))
    
    # Apply subscription-based filtering
    if current_user.subscription_type == models.SubscriptionType.FREE:
        functions = functions.filter(models.Ingredient.is_premium.is_(False), models.Ingredient.is_professional.is_(False))
    elif current_user.subscription_type == models.SubscriptionType.PREMIUM:
        functions = functions.filter(models.Ingredient.is_professional.is_(False))
    
    return [function[0] for function in functions.all()]

@router.get("/phases", response_model=List[str])
def get_ingredient_phases(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get all unique ingredient phases.
    """
    # Query distinct phase values
    phases = db.query(models.Ingredient.phase).distinct().filter(models.Ingredient.phase.isnot(None))
    
    # Apply subscription-based filtering
    if current_user.subscription_type == models.SubscriptionType.FREE:
        phases = phases.filter(models.Ingredient.is_premium.is_(False), models.Ingredient.is_professional.is_(False))
    elif current_user.subscription_type == models.SubscriptionType.PREMIUM:
        phases = phases.filter(models.Ingredient.is_professional.is_(False))
    
    return [phase[0] for phase in phases.all()]