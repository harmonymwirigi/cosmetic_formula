# backend/app/api/endpoints/notifications.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app import models, schemas
from app.database import get_db
from app.auth import get_current_user
from datetime import datetime
import logging
from app.services.notification_service import NotificationService, NotificationData

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[schemas.NotificationRead])
async def get_notifications(
    skip: int = 0,
    limit: int = 100,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user notifications"""
    try:
        notification_service = NotificationService(db)
        notifications = notification_service.get_user_notifications(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            unread_only=unread_only
        )
        
        # Log for debugging
        logger.info(f"Retrieved {len(notifications)} notifications for user {current_user.id}")
        return notifications
    except Exception as e:
        logger.error(f"Error retrieving notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to retrieve notifications"
        )

@router.post("/{notification_id}/read", response_model=Dict[str, Any])
async def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a notification as read"""
    notification_service = NotificationService(db)
    notification = notification_service.mark_as_read(notification_id, current_user.id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}

@router.post("/read-all", response_model=Dict[str, Any])
async def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark all notifications as read"""
    notification_service = NotificationService(db)
    count = notification_service.mark_all_as_read(current_user.id)
    
    return {"message": "All notifications marked as read", "count": count}

@router.delete("/{notification_id}", response_model=Dict[str, bool])
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a notification"""
    notification_service = NotificationService(db)
    success = notification_service.delete_notification(notification_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"success": True}

# Notification preferences endpoints
@router.get("/preferences", response_model=Dict[str, Dict[str, bool]])
async def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user notification preferences"""
    try:
        # Use the notification service to get formatted preferences
        notification_service = NotificationService(db)
        preferences = notification_service.get_notification_preferences(current_user.id)
        
        return preferences
    except Exception as e:
        logger.error(f"Error retrieving notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification preferences"
        )

@router.put("/preferences/{notification_type}", response_model=Dict[str, Any])
async def update_notification_preferences(
    notification_type: str,
    preferences: Dict[str, bool],  # Accept a simple dictionary of preferences
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update notification preferences for a specific type"""
    try:
        # Log the incoming data for debugging
        logger.info(f"Updating preferences for user {current_user.id}, type {notification_type}: {preferences}")
        
        # Validate input data
        required_fields = ["email_enabled", "push_enabled", "sms_enabled"]
        for field in required_fields:
            if field not in preferences:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing required field: {field}"
                )
        
        # Use the notification service to update preferences
        notification_service = NotificationService(db)
        updated_preference = notification_service.update_notification_preferences(
            user_id=current_user.id,
            notification_type=notification_type,
            email_enabled=preferences["email_enabled"],
            push_enabled=preferences["push_enabled"],
            sms_enabled=preferences["sms_enabled"]
        )
        
        return updated_preference
    except ValueError as ve:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error updating notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )
    