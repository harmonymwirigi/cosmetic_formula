# backend/app/crud.py
from sqlalchemy.orm import Session
from . import models, schemas
from typing import List,Dict,Optional, Any
from fastapi import HTTPException, status

# User CRUD operations
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    # Hash password already done at this point
    db_user = models.User(
        email=user.email,
        hashed_password=user.password,  # Already hashed in auth.py
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=True,
        needs_subscription=True  # Set needs_subscription=True for new users
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user: schemas.UserUpdate) -> models.User:
    db_user = get_user(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_subscription(db: Session, user_id: int, subscription_type: str, subscription_id: str = None):
    user = get_user(db, user_id)
    if not user:
        return None
    
    user.subscription_type = subscription_type
    user.needs_subscription = False
    if subscription_id:
        user.subscription_id = subscription_id
    
    db.commit()
    db.refresh(user)
    return user

# Ingredient CRUD operations
def get_ingredient(db: Session, ingredient_id: int) -> Optional[models.Ingredient]:
    return db.query(models.Ingredient).filter(models.Ingredient.id == ingredient_id).first()

def get_ingredients(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    phase: Optional[str] = None,
    function: Optional[str] = None,
    is_premium: Optional[bool] = None,
    is_professional: Optional[bool] = None
) -> List[models.Ingredient]:
    query = db.query(models.Ingredient)
    
    if search:
        query = query.filter(
            (models.Ingredient.name.ilike(f"%{search}%")) | 
            (models.Ingredient.inci_name.ilike(f"%{search}%"))
        )
    
    if phase:
        query = query.filter(models.Ingredient.phase == phase)
    
    if function:
        query = query.filter(models.Ingredient.function == function)
    
    if is_premium is not None:
        query = query.filter(models.Ingredient.is_premium == is_premium)
        
    if is_professional is not None:
        query = query.filter(models.Ingredient.is_professional == is_professional)
    
    return query.offset(skip).limit(limit).all()

def create_ingredient(db: Session, ingredient: schemas.IngredientCreate) -> models.Ingredient:
    db_ingredient = models.Ingredient(**ingredient.dict())
    db.add(db_ingredient)
    db.commit()
    db.refresh(db_ingredient)
    return db_ingredient

def update_ingredient(
    db: Session, 
    ingredient_id: int, 
    ingredient: schemas.IngredientUpdate
) -> models.Ingredient:
    db_ingredient = get_ingredient(db, ingredient_id)
    if db_ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    update_data = ingredient.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ingredient, key, value)
    
    db.commit()
    db.refresh(db_ingredient)
    return db_ingredient

def delete_ingredient(db: Session, ingredient_id: int) -> None:
    db_ingredient = get_ingredient(db, ingredient_id)
    if db_ingredient is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    
    db.delete(db_ingredient)
    db.commit()

# Formula CRUD operations
def get_formula(db: Session, formula_id: int) -> Optional[models.Formula]:
    return db.query(models.Formula).filter(models.Formula.id == formula_id).first()

def get_user_formulas(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[models.Formula]:
    return (
        db.query(models.Formula)
        .filter(models.Formula.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_formula_step(
    db: Session, 
    step: schemas.FormulaStepCreate, 
    formula_id: int
) -> models.FormulaStep:
    db_step = models.FormulaStep(
        **step.dict(),
        formula_id=formula_id
    )
    db.add(db_step)
    db.commit()
    db.refresh(db_step)
    return db_step

def create_formula(
    db: Session, 
    formula: schemas.FormulaCreate, 
    user_id: int
) -> models.Formula:
    # Create formula
    db_formula = models.Formula(
        name=formula.name,
        description=formula.description,
        type=formula.type,
        is_public=formula.is_public,
        total_weight=formula.total_weight,
        user_id=user_id
    )
    db.add(db_formula)
    db.commit()
    db.refresh(db_formula)
    
    # Add ingredients
    for ingredient_data in formula.ingredients:
        # Check if ingredient exists
        db_ingredient = db.query(models.Ingredient).get(ingredient_data.ingredient_id)
        if not db_ingredient:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingredient with id {ingredient_data.ingredient_id} not found"
            )
        
        # Add to formula_ingredients association table
        stmt = models.formula_ingredients.insert().values(
            formula_id=db_formula.id,
            ingredient_id=ingredient_data.ingredient_id,
            percentage=ingredient_data.percentage,
            order=ingredient_data.order
        )
        db.execute(stmt)
    
    # Add steps
    for step_data in formula.steps:
        create_formula_step(db, step_data, db_formula.id)
    
    db.commit()
    db.refresh(db_formula)
    return db_formula

def update_formula(
    db: Session, 
    formula_id: int, 
    formula: schemas.FormulaUpdate,
    user_id: int
) -> models.Formula:
    db_formula = get_formula(db, formula_id)
    
    if db_formula is None:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if db_formula.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this formula")
    
    # Update formula fields
    update_data = formula.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_formula, key, value)
    
    db.commit()
    db.refresh(db_formula)
    return db_formula

def delete_formula(db: Session, formula_id: int, user_id: int) -> None:
    db_formula = get_formula(db, formula_id)
    
    if db_formula is None:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if db_formula.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this formula")
    
    # Delete associated steps first (due to foreign key constraints)
    db.query(models.FormulaStep).filter(models.FormulaStep.formula_id == formula_id).delete()
    
    # The many-to-many relationship will be automatically handled by SQLAlchemy
    
    # Delete the formula
    db.delete(db_formula)
    db.commit()


def get_user_profile(db: Session, user_id: int) -> Optional[models.UserProfile]:
    """Get a user's profile"""
    return db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()

def create_user_profile(db: Session, profile_data: Dict[str, Any], user_id: int) -> models.UserProfile:
    """Create a new user profile"""
    db_profile = models.UserProfile(
        user_id=user_id,
        skin_type=profile_data.get("skin_type"),
        skin_concerns=profile_data.get("skin_concerns"),
        sensitivities=profile_data.get("sensitivities"),
        climate=profile_data.get("climate"),
        hair_type=profile_data.get("hair_type"),
        hair_concerns=profile_data.get("hair_concerns"),
        brand_info=profile_data.get("brand_info")
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_user_profile(db: Session, profile_data: Dict[str, Any], user_id: int) -> models.UserProfile:
    """Update an existing user profile"""
    db_profile = get_user_profile(db, user_id)
    
    if not db_profile:
        # Create a new profile if it doesn't exist
        return create_user_profile(db, profile_data, user_id)
    
    # Update fields that are provided
    if "skin_type" in profile_data:
        db_profile.skin_type = profile_data["skin_type"]
    if "skin_concerns" in profile_data:
        db_profile.skin_concerns = profile_data["skin_concerns"]
    if "sensitivities" in profile_data:
        db_profile.sensitivities = profile_data["sensitivities"]
    if "climate" in profile_data:
        db_profile.climate = profile_data["climate"]
    if "hair_type" in profile_data:
        db_profile.hair_type = profile_data["hair_type"]
    if "hair_concerns" in profile_data:
        db_profile.hair_concerns = profile_data["hair_concerns"]
    if "brand_info" in profile_data:
        db_profile.brand_info = profile_data["brand_info"]
    
    db.commit()
    db.refresh(db_profile)
    return db_profile