# backend/app/services/notification_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from app import models
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NotificationData:
    def __init__(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        reference_id: Optional[int] = None
    ):
        self.user_id = user_id
        self.title = title
        self.message = message
        self.notification_type = notification_type
        self.reference_id = reference_id

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        
    def create_notification(self, data: NotificationData) -> models.Notification:
        """Create a new notification"""
        notification = models.Notification(
            user_id=data.user_id,
            title=data.title,
            message=data.message,
            notification_type=data.notification_type,
            reference_id=data.reference_id,
            is_read=False,
            created_at=datetime.utcnow()
        )
        
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        return notification
    
    def get_user_notifications(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        unread_only: bool = False
    ) -> List[models.Notification]:
        """Get notifications for a user"""
        query = self.db.query(models.Notification)\
            .filter(models.Notification.user_id == user_id)
            
        if unread_only:
            query = query.filter(models.Notification.is_read == False)
            
        notifications = query\
            .order_by(models.Notification.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
            
        return notifications
    
    def get_notification(self, notification_id: int, user_id: int) -> Optional[models.Notification]:
        """Get a notification by ID for a specific user"""
        return self.db.query(models.Notification)\
            .filter(
                models.Notification.id == notification_id,
                models.Notification.user_id == user_id
            )\
            .first()
    
    def mark_as_read(self, notification_id: int, user_id: int) -> Optional[models.Notification]:
        """Mark a notification as read"""
        notification = self.get_notification(notification_id, user_id)
        
        if notification:
            notification.is_read = True
            self.db.commit()
            self.db.refresh(notification)
            
        return notification
    
    def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        result = self.db.query(models.Notification)\
            .filter(
                models.Notification.user_id == user_id,
                models.Notification.is_read == False
            )\
            .update({'is_read': True})
            
        self.db.commit()
        return result
    
    def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """Delete a notification"""
        notification = self.get_notification(notification_id, user_id)
        
        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True
            
        return False

    def get_notification_preferences(self, user_id: int) -> Dict[str, Dict[str, bool]]:
        """Get notification preferences for a user, formatted as a dictionary by type"""
        # Get all notification preferences for the user
        preferences = self.db.query(models.NotificationPreference)\
            .filter(models.NotificationPreference.user_id == user_id)\
            .all()
        
        # Format as a dictionary by notification type
        result = {}
        for pref in preferences:
            result[pref.notification_type] = {
                "email_enabled": pref.email_enabled,
                "push_enabled": pref.push_enabled, 
                "sms_enabled": pref.sms_enabled
            }
        
        # Ensure we have entries for all standard notification types
        standard_types = ["system", "formula", "subscription", "order"]
        for type_id in standard_types:
            if type_id not in result:
                # Add default preferences for this type
                result[type_id] = {
                    "email_enabled": True,
                    "push_enabled": True,
                    "sms_enabled": False
                }
        
        logger.info(f"Retrieved preferences for user {user_id}: {result}")
        return result
    
    def update_notification_preferences(
        self,
        user_id: int,
        notification_type: str,
        email_enabled: bool,
        push_enabled: bool,
        sms_enabled: bool
    ) -> Dict[str, Any]:
        """Update notification preferences for a specific type"""
        
        # Validate notification type
        valid_types = ["system", "formula", "subscription", "order"]
        if notification_type not in valid_types:
            raise ValueError(f"Invalid notification type: {notification_type}")
        
        # Find existing preference or create new one
        preference = self.db.query(models.NotificationPreference)\
            .filter(
                models.NotificationPreference.user_id == user_id,
                models.NotificationPreference.notification_type == notification_type
            )\
            .first()
        
        if not preference:
            # Create new preference
            preference = models.NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
                email_enabled=email_enabled,
                push_enabled=push_enabled,
                sms_enabled=sms_enabled
            )
            self.db.add(preference)
        else:
            # Update existing preference
            preference.email_enabled = email_enabled
            preference.push_enabled = push_enabled
            preference.sms_enabled = sms_enabled
        
        # Save changes
        self.db.commit()
        self.db.refresh(preference)
        
        # Return updated preference data
        return {
            "notification_type": preference.notification_type,
            "email_enabled": preference.email_enabled,
            "push_enabled": preference.push_enabled,
            "sms_enabled": preference.sms_enabled
        }
    
    
    def get_recent_notifications_by_type(
        self, 
        user_id: int, 
        notification_type: str,
        hours: int = 24,
        title_contains: Optional[str] = None
    ) -> List[models.Notification]:
        """
        Get recent notifications of a specific type for a user
        Optionally filter by title content and time window
        
        Args:
            user_id: The user ID to get notifications for
            notification_type: The type of notification to filter
            hours: Only get notifications from the last N hours
            title_contains: Optional filter for notification title content
            
        Returns:
            List of notification objects
        """
        from datetime import datetime, timedelta
        
        # Calculate the time threshold
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        # Start query
        query = self.db.query(models.Notification).filter(
            models.Notification.user_id == user_id,
            models.Notification.notification_type == notification_type,
            models.Notification.created_at >= time_threshold
        )
        
        # Add title filter if provided
        if title_contains:
            query = query.filter(models.Notification.title.like(f"%{title_contains}%"))
        
        # Execute query
        notifications = query.all()
        
        return notifications