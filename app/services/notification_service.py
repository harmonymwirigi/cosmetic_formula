# backend/app/services/notification_service.py
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app import models, schemas
from datetime import datetime
import logging
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationData(BaseModel):
    title: str
    message: str
    notification_type: str
    reference_id: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_notification(self, user_id: int, notification_data: NotificationData) -> models.Notification:
        """Create a new notification for a user"""
        try:
            # Create notification record
            db_notification = models.Notification(
                user_id=user_id,
                title=notification_data.title,
                message=notification_data.message,
                notification_type=notification_data.notification_type,
                reference_id=notification_data.reference_id,
                is_read=False,
                created_at=datetime.utcnow()
            )
            
            self.db.add(db_notification)
            self.db.commit()
            self.db.refresh(db_notification)
            
            # Get user's notification preferences
            preferences = self.db.query(models.NotificationPreference).filter(
                models.NotificationPreference.user_id == user_id,
                models.NotificationPreference.notification_type == notification_data.notification_type
            ).first()
            
            # If no preferences exist, create with defaults
            if not preferences:
                preferences = models.NotificationPreference(
                    user_id=user_id,
                    notification_type=notification_data.notification_type,
                    email_enabled=True,
                    push_enabled=True,
                    sms_enabled=False
                )
                self.db.add(preferences)
                self.db.commit()
            
            # TODO: Handle email notifications based on preferences
            if preferences.email_enabled:
                # Implement email sending logic or queue
                logger.info(f"Email notification would be sent to user {user_id}")
                
            # TODO: Handle push notifications based on preferences
            if preferences.push_enabled:
                # Implement push notification logic
                logger.info(f"Push notification would be sent to user {user_id}")
                
            return db_notification
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating notification: {str(e)}")
            raise
    
    def get_user_notifications(self, user_id: int, skip: int = 0, limit: int = 100, 
                              unread_only: bool = False) -> List[models.Notification]:
        """Get notifications for a user with optional filtering"""
        query = self.db.query(models.Notification).filter(models.Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(models.Notification.is_read == False)
            
        return query.order_by(models.Notification.created_at.desc()).offset(skip).limit(limit).all()
    
    def mark_as_read(self, notification_id: int, user_id: int) -> Optional[models.Notification]:
        """Mark a notification as read"""
        notification = self.db.query(models.Notification).filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            self.db.commit()
            self.db.refresh(notification)
            
        return notification
    
    def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user and return count of updated records"""
        result = self.db.query(models.Notification).filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        ).update({"is_read": True})
        
        self.db.commit()
        return result
    
    def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """Delete a notification"""
        notification = self.db.query(models.Notification).filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id
        ).first()
        
        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True
            
        return False
    
    def update_notification_preferences(self, user_id: int, notification_type: str, 
                                       email_enabled: bool, push_enabled: bool, 
                                       sms_enabled: bool) -> models.NotificationPreference:
        """Update notification preferences for a user"""
        preference = self.db.query(models.NotificationPreference).filter(
            models.NotificationPreference.user_id == user_id,
            models.NotificationPreference.notification_type == notification_type
        ).first()
        
        if preference:
            preference.email_enabled = email_enabled
            preference.push_enabled = push_enabled
            preference.sms_enabled = sms_enabled
        else:
            preference = models.NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
                email_enabled=email_enabled,
                push_enabled=push_enabled,
                sms_enabled=sms_enabled
            )
            self.db.add(preference)
            
        self.db.commit()
        self.db.refresh(preference)
        return preference