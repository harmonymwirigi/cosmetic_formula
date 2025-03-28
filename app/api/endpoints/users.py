# backend/app/api/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from typing import Dict, Any
from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user, get_password_hash, verify_password

router = APIRouter()


@router.get("/me", response_model=schemas.User)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

@router.put("/me", response_model=schemas.User)
def update_user_me(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update current user information.
    """
    # Check if email is being updated and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        db_user = crud.get_user_by_email(db, email=user_update.email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    return crud.update_user(db=db, user_id=current_user.id, user=user_update)


@router.get("/status", response_model=Dict[str, Any])
def get_user_status(current_user: models.User = Depends(get_current_user)):
    """
    Get user status including subscription needs
    """
    return {
        "id": current_user.id,
        "needs_subscription": current_user.needs_subscription,
        "subscription_type": current_user.subscription_type,
        "is_active": current_user.is_active
    }


@router.post("/subscription", response_model=schemas.User)
def update_subscription(
    subscription_data: schemas.SubscriptionUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user subscription type
    """
    # Validate subscription type
    try:
        subscription_type = models.SubscriptionType(subscription_data.subscription_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription type: {subscription_data.subscription_type}"
        )
    
    # Update user
    current_user.subscription_type = subscription_type
    current_user.needs_subscription = False
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.get("/{user_id}", response_model=schemas.User)
def read_user(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user by ID (only for admin users or user themselves)
    """
    # Check if user is querying themselves
    if current_user.id != user_id:  # and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user