# backend/app/api/endpoints/formulas.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.utils.response_formatter import format_formula_response
from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter()

@router.get("/recent", response_model=List[schemas.FormulaList])
def get_recent_formulas(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get user's recent formulas
    """
    try:
        # Get user's formulas, ordered by creation date
        formulas = (
            db.query(models.Formula)
            .filter(models.Formula.user_id == current_user.id)
            .order_by(models.Formula.created_at.desc())
            .limit(limit)
            .all()
        )
        
        # Return will be automatically converted to the response_model type
        return formulas
    except Exception as e:
        # Add better error logging
        print(f"Error fetching recent formulas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching recent formulas"
        )
@router.post("/duplicate/{formula_id}", response_model=schemas.Formula)
def duplicate_formula(
    formula_id: int,
    data: schemas.FormulaDuplication,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Duplicate an existing formula with a new name.
    """
    # Get the original formula
    original_formula = crud.get_formula(db, formula_id)
    
    # Check if formula exists and belongs to the current user
    if not original_formula:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if original_formula.user_id != current_user.id and not original_formula.is_public:
        raise HTTPException(status_code=403, detail="Not authorized to access this formula")
    
    # Check if user has reached formula limit (for free accounts)
    if current_user.subscription_type == models.SubscriptionType.FREE:
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == current_user.id).count()
        if formula_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free accounts are limited to 3 formulas. Please upgrade your subscription."
            )
    
    # Create a new formula based on the original
    new_formula = models.Formula(
        name=data.new_name or f"{original_formula.name} (Copy)",
        description=original_formula.description,
        type=original_formula.type,
        is_public=False,  # Default to private for duplicated formulas
        total_weight=original_formula.total_weight,
        user_id=current_user.id
    )
    
    db.add(new_formula)
    db.commit()
    db.refresh(new_formula)
    
    # Get ingredient associations from the original formula
    from sqlalchemy import text
    sql = text(f"SELECT ingredient_id, percentage, \"order\" FROM formula_ingredients WHERE formula_id = :formula_id")
    ingredients_assoc = db.execute(sql, {"formula_id": original_formula.id}).fetchall()
    
    # Duplicate the ingredient associations
    for assoc in ingredients_assoc:
        stmt = models.formula_ingredients.insert().values(
            formula_id=new_formula.id,
            ingredient_id=assoc.ingredient_id,
            percentage=assoc.percentage,
            order=assoc.order
        )
        db.execute(stmt)
    
    # Duplicate the steps
    for step in original_formula.steps:
        new_step = models.FormulaStep(
            formula_id=new_formula.id,
            description=step.description,
            order=step.order
        )
        db.add(new_step)
    
    db.commit()
    db.refresh(new_formula)
    
    # Return formatted formula response
    return format_formula_response(new_formula, db)


@router.put("/{formula_id}/ingredients", response_model=schemas.Formula)
def update_formula_ingredients(
    formula_id: int,
    data: schemas.FormulaIngredientsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update the ingredients of an existing formula.
    """
    # Get the formula
    formula = crud.get_formula(db, formula_id)
    
    # Check if formula exists and belongs to the current user
    if not formula:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if formula.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this formula")
    
    # Delete existing ingredient associations
    from sqlalchemy import text
    delete_sql = text("DELETE FROM formula_ingredients WHERE formula_id = :formula_id")
    db.execute(delete_sql, {"formula_id": formula_id})
    
    # Add new ingredient associations
    for ingredient_data in data.ingredients:
        stmt = models.formula_ingredients.insert().values(
            formula_id=formula_id,
            ingredient_id=ingredient_data.ingredient_id,
            percentage=ingredient_data.percentage,
            order=ingredient_data.order
        )
        db.execute(stmt)
    
    db.commit()
    db.refresh(formula)
    
    # Return formatted formula response
    return utils.response_formatter.format_formula_response(formula, db)

@router.put("/{formula_id}/steps", response_model=schemas.Formula)
def update_formula_steps(
    formula_id: int,
    data: schemas.FormulaStepsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update the steps of an existing formula.
    """
    # Get the formula
    formula = crud.get_formula(db, formula_id)
    
    # Check if formula exists and belongs to the current user
    if not formula:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if formula.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this formula")
    
    # Delete existing steps
    db.query(models.FormulaStep).filter(models.FormulaStep.formula_id == formula_id).delete()
    
    # Add new steps
    for step_data in data.steps:
        new_step = models.FormulaStep(
            formula_id=formula_id,
            description=step_data.description,
            order=step_data.order
        )
        db.add(new_step)
    
    db.commit()
    db.refresh(formula)
    
    # Return formatted formula response
    return utils.response_formatter.format_formula_response(formula, db)
@router.get("/read_formulas", response_model=List[schemas.FormulaList])
def read_formulas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get all formulas for the current user.
    """
    formulas = crud.get_user_formulas(db, user_id=current_user.id, skip=skip, limit=limit)
    return formulas
@router.get("/{formula_id}", response_model=None)
def read_formula(
    formula_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get a specific formula by ID.
    """
    # Get the formula from the database
    formula = crud.get_formula(db, formula_id)
    
    # Check if formula exists and belongs to the current user
    if not formula:
        raise HTTPException(status_code=404, detail="Formula not found")
    
    if formula.user_id != current_user.id and not formula.is_public:
        raise HTTPException(status_code=403, detail="Not authorized to access this formula")
    
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
    
    # Construct the response manually to match the expected schema
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
@router.post("/create_formula", response_model=None)
def create_formula(
    formula: schemas.FormulaCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Create a new formula.
    """
    # Check if user has reached formula limit (for free accounts)
    if current_user.subscription_type == models.SubscriptionType.FREE:
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == current_user.id).count()
        if formula_count >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free accounts are limited to 3 formulas. Please upgrade your subscription."
            )
    
    # Create the formula in the database
    db_formula = crud.create_formula(db=db, formula=formula, user_id=current_user.id)
    
    # Get a fresh copy of the formula with all relationships loaded
    formula_with_details = db.query(models.Formula).filter(models.Formula.id == db_formula.id).first()
    
    # Get user information
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    
    # Query the formula_ingredients association table using SQLAlchemy syntax
    from sqlalchemy import text
    sql = text(f"SELECT ingredient_id, percentage, \"order\" FROM formula_ingredients WHERE formula_id = :formula_id")
    ingredients_assoc = db.execute(sql, {"formula_id": formula_with_details.id}).fetchall()
    
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
    
    # Return the formatted response
    return {
        "id": formula_with_details.id,
        "name": formula_with_details.name,
        "description": formula_with_details.description,
        "type": formula_with_details.type,
        "user_id": formula_with_details.user_id,
        "is_public": formula_with_details.is_public,
        "total_weight": formula_with_details.total_weight,
        "created_at": formula_with_details.created_at,
        "updated_at": formula_with_details.updated_at,
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
            for step in formula_with_details.steps
        ]
    }