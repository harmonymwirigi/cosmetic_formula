# backend/app/api/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging

# Import subscription mapping functions
from app.utils.subscription_mapper import (
    map_to_backend_type, 
    map_to_frontend_type, 
    get_formula_limit,
    get_display_name
)

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user, get_password_hash, verify_password
from app.services.notification_service import NotificationService, NotificationData

# Configure logging
logger = logging.getLogger(__name__)

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
    Get user status including subscription needs and basic user info
    """
    # Map backend subscription type to frontend format
    frontend_subscription_type = map_to_frontend_type(current_user.subscription_type)
    
    return {
        "id": current_user.id,
        "needs_subscription": current_user.needs_subscription,
        "subscription_type": frontend_subscription_type,  # Return frontend-compatible type
        "is_active": current_user.is_active,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_phone_verified": current_user.is_phone_verified,
        "subscription_expires_at": current_user.subscription_expires_at
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
    # Get current subscription before updating
    old_subscription_type = current_user.subscription_type
    
    # Map frontend subscription type to backend enum
    backend_subscription_type = map_to_backend_type(subscription_data.subscription_type)
    
    # Update user
    current_user.subscription_type = backend_subscription_type
    current_user.needs_subscription = False
    
    # Set subscription expiry for premium subscriptions (for demo purposes)
    # In a real app, this would be handled by the payment provider's webhook
    if backend_subscription_type in [models.SubscriptionType.PREMIUM, models.SubscriptionType.PROFESSIONAL]:
        current_user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
    
    db.commit()
    db.refresh(current_user)
    
    # Send notification about subscription change
    try:
        notification_service = NotificationService(db)
        notification_service.notify_subscription_change(
            user_id=current_user.id,
            new_subscription_type=backend_subscription_type.value,
            old_subscription_type=old_subscription_type.value
        )
        
        # Send SMS notification if user has verified phone number
        if current_user.phone_number and current_user.is_phone_verified:
            try:
                from app.services.sms_service import send_subscription_change_sms
                send_subscription_change_sms(
                    phone_number=current_user.phone_number,
                    old_plan=old_subscription_type.value,
                    new_plan=backend_subscription_type.value,
                    expires_at=current_user.subscription_expires_at
                )
            except Exception as e:
                logger.error(f"Failed to send subscription change SMS: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to send subscription change notification: {str(e)}")
    
    # Return user with frontend-compatible subscription type
    user_data = current_user.__dict__.copy()
    user_data["subscription_type"] = map_to_frontend_type(current_user.subscription_type)
    return schemas.User(**user_data)

@router.get("/formula-usage", response_model=schemas.FormulaUsageResponse)
async def get_formula_usage(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get formula usage statistics for the current user"""
    try:
        # Count user's formulas
        formula_count = db.query(models.Formula).filter(models.Formula.user_id == current_user.id).count()
        
        # Import get_formula_limit from the subscription mapper if not already imported
        from app.utils.subscription_mapper import get_formula_limit
        
        # Get formula limit based on subscription type
        formula_limit = get_formula_limit(current_user.subscription_type)
        
        # Map backend subscription type to frontend format
        from app.utils.subscription_mapper import map_to_frontend_type
        frontend_subscription_type = map_to_frontend_type(current_user.subscription_type)
        
        # Initialize status variable with a default value
        status = "normal"
        can_create_more = True
        percentage_used = 0
        
        # Calculate percentage used (handle unlimited case)
        if formula_limit == float('inf') or formula_limit == 'Unlimited':
            percentage_used = 0  # Percentage doesn't make sense for unlimited
            can_create_more = True
            status = "normal"
        else:
            # Convert formula_limit to int if it's a string number
            if isinstance(formula_limit, str) and formula_limit.isdigit():
                formula_limit = int(formula_limit)
                
            # Now calculate percentage
            if isinstance(formula_limit, (int, float)) and formula_limit > 0:
                percentage_used = (formula_count / formula_limit) * 100
                can_create_more = formula_count < formula_limit
                
                # Determine status based on usage
                if formula_count >= formula_limit:
                    status = "limit_reached"
                elif percentage_used >= 80:
                    status = "approaching_limit"
                else:
                    status = "normal"
            else:
                # Handle unexpected formula_limit value
                formula_limit = 3  # Default to free tier
                percentage_used = (formula_count / formula_limit) * 100
                can_create_more = formula_count < formula_limit
                
                if formula_count >= formula_limit:
                    status = "limit_reached"
                elif percentage_used >= 80:
                    status = "approaching_limit"
        
        # Create a notification if approaching limit or reached limit
        if status in ["approaching_limit", "limit_reached"]:
            try:
                from app.services.notification_service import NotificationService
                notification_service = NotificationService(db)
                notification_service.notify_formula_quota(
                    user_id=current_user.id,
                    formula_count=formula_count,
                    formula_limit=formula_limit,
                    subscription_type=frontend_subscription_type  # Use frontend type for display
                )
                
                # If user has a verified phone number and limit reached, send SMS
                if status == "limit_reached" and current_user.phone_number and current_user.is_phone_verified:
                    try:
                        from app.services.sms_service import send_formula_limit_sms
                        send_formula_limit_sms(
                            phone_number=current_user.phone_number,
                            formula_count=formula_count,
                            formula_limit=formula_limit,
                            subscription_type=frontend_subscription_type  # Use frontend type for display
                        )
                    except Exception as e:
                        logger.error(f"Error sending SMS notification: {str(e)}")
            except Exception as e:
                logger.error(f"Error creating formula limit notification: {str(e)}")
        
        # Format the response
        formatted_limit = "Unlimited" if formula_limit == float('inf') else formula_limit
        
        return {
            "formula_count": formula_count,
            "formula_limit": formatted_limit,
            "percentage_used": percentage_used,
            "status": status,
            "subscription_type": frontend_subscription_type,  # Return frontend-compatible type
            "can_create_more": can_create_more
        }
    except Exception as e:
        logger.error(f"Error getting formula usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve formula usage: {str(e)}"
        )