# backend/app/api/endpoints/notifications.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app import models, schemas
from app.database import get_db
from app.auth import get_current_user
from app.services.notification_service import NotificationService, NotificationData

router = APIRouter()

@router.get("/", response_model=List[schemas.NotificationRead])
def get_user_notifications(
    skip: int = 0,
    limit: int = 100,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)  # Make sure this works
):
    """Get notifications for the current user"""
    notification_service = NotificationService(db)
    notifications = notification_service.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only
    )
    return notifications

@router.post("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark notification as read"""
    notification_service = NotificationService(db)
    notification = notification_service.mark_as_read(notification_id, current_user.id)
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return {"success": True}

@router.post("/read-all")
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark all notifications as read"""
    notification_service = NotificationService(db)
    count = notification_service.mark_all_as_read(current_user.id)
    return {"success": True, "count": count}

@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a notification"""
    notification_service = NotificationService(db)
    success = notification_service.delete_notification(notification_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return {"success": True}

@router.put("/preferences/{notification_type}")
def update_notification_preferences(
    notification_type: str,
    preferences: schemas.NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update notification preferences"""
    notification_service = NotificationService(db)
    updated_preferences = notification_service.update_notification_preferences(
        user_id=current_user.id,
        notification_type=notification_type,
        email_enabled=preferences.email_enabled,
        push_enabled=preferences.push_enabled,
        sms_enabled=preferences.sms_enabled
    )
    
    return updated_preferences

@router.get("/preferences", response_model=List[schemas.NotificationPreferenceRead])
def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all notification preferences for current user"""
    preferences = db.query(models.NotificationPreference).filter(
        models.NotificationPreference.user_id == current_user.id
    ).all()
    
    return preferences