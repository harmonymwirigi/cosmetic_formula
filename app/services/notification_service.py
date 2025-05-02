# backend/app/services/notification_service.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app import models
import logging

logger = logging.getLogger(__name__)

class NotificationData(BaseModel):
    """Data required to create a notification"""
    user_id: int
    title: str
    message: str
    notification_type: str  # 'system', 'order', 'formula', 'subscription', etc.
    reference_id: Optional[int] = None

class NotificationService:
    """Service for handling user notifications"""
    
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
        
        logger.info(f"Created notification for user {data.user_id}: {data.title}")
        
        return notification
    
    def get_user_notifications(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        unread_only: bool = False
    ) -> List[models.Notification]:
        """Get notifications for a user"""
        query = (
            self.db.query(models.Notification)
            .filter(models.Notification.user_id == user_id)
            .order_by(models.Notification.created_at.desc())
        )
        
        if unread_only:
            query = query.filter(models.Notification.is_read == False)
        
        return query.offset(skip).limit(limit).all()
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a notification as read"""
        notification = (
            self.db.query(models.Notification)
            .filter(
                models.Notification.id == notification_id,
                models.Notification.user_id == user_id
            )
            .first()
        )
        
        if not notification:
            return False
        
        notification.is_read = True
        self.db.commit()
        return True
    
    def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user and return count"""
        result = (
            self.db.query(models.Notification)
            .filter(
                models.Notification.user_id == user_id,
                models.Notification.is_read == False
            )
            .update({"is_read": True})
        )
        
        self.db.commit()
        return result
    
    def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """Delete a notification"""
        notification = (
            self.db.query(models.Notification)
            .filter(
                models.Notification.id == notification_id,
                models.Notification.user_id == user_id
            )
            .first()
        )
        
        if not notification:
            return False
        
        self.db.delete(notification)
        self.db.commit()
        return True
    
    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user"""
        return (
            self.db.query(models.Notification)
            .filter(
                models.Notification.user_id == user_id,
                models.Notification.is_read == False
            )
            .count()
        )
    
    def get_notification_preferences(self, user_id: int) -> Dict[str, Dict[str, bool]]:
        """Get notification preferences for a user, formatted by type"""
        preferences = (
            self.db.query(models.NotificationPreference)
            .filter(models.NotificationPreference.user_id == user_id)
            .all()
        )
        
        # Group by notification_type
        result = {}
        
        if not preferences:
            # Create default preferences if none exist
            default_types = ["system", "formula", "subscription", "order"]
            preferences = []
            
            for ntype in default_types:
                pref = models.NotificationPreference(
                    user_id=user_id,
                    notification_type=ntype,
                    email_enabled=True,
                    push_enabled=True,
                    sms_enabled=False
                )
                self.db.add(pref)
                preferences.append(pref)
            
            self.db.commit()
        
        # Format preferences by type
        for pref in preferences:
            result[pref.notification_type] = {
                "email_enabled": pref.email_enabled,
                "push_enabled": pref.push_enabled,
                "sms_enabled": pref.sms_enabled
            }
        
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
        # Check if preference exists
        preference = (
            self.db.query(models.NotificationPreference)
            .filter(
                models.NotificationPreference.user_id == user_id,
                models.NotificationPreference.notification_type == notification_type
            )
            .first()
        )
        
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
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "notification_type": notification_type,
            "email_enabled": email_enabled,
            "push_enabled": push_enabled,
            "sms_enabled": sms_enabled
        }
    
    # Formula-specific notification helpers
    def notify_formula_quota(
        self, 
        user_id: int, 
        formula_count: int, 
        formula_limit: int or str or float,
        subscription_type: str
    ) -> Optional[models.Notification]:
        """
        Create a notification when user is approaching formula quota limit
        
        Args:
            user_id: User ID
            formula_count: Current number of formulas
            formula_limit: Maximum allowed (can be 'Unlimited' or int)
            subscription_type: User's subscription type
            
        Returns:
            Notification or None
        """
        # Handle unlimited plans properly
        if (formula_limit == 'Unlimited' or 
            formula_limit == float('inf') or 
            formula_limit == 'Infinity' or
            formula_limit == "∞"):
            # No notification needed for unlimited plans
            return None
            
        # Convert string to int if needed
        if isinstance(formula_limit, str) and formula_limit.isdigit():
            formula_limit = int(formula_limit)
            
        # Skip if formula_limit is not a valid number
        if not isinstance(formula_limit, (int, float)):
            logger.error(f"Invalid formula_limit type: {type(formula_limit)}")
            return None
        
        # Calculate remaining formulas
        remaining = formula_limit - formula_count
        percentage = (formula_count / formula_limit) * 100 if formula_limit > 0 else 100
        
        # Determine severity level
        if formula_count >= formula_limit:
            title = "Formula Limit Reached"
            message = f"You have used all {formula_limit} formulas allowed in your {subscription_type} plan. Please upgrade to create more formulas."
        elif percentage >= 90:
            title = "Formula Limit Almost Reached"
            message = f"You have used {formula_count} out of {formula_limit} formulas allowed in your {subscription_type} plan. You have only {remaining} formula(s) remaining."
        elif percentage >= 80:
            title = "Formula Limit Approaching"
            message = f"You have used {formula_count} out of {formula_limit} formulas allowed in your {subscription_type} plan. You have {remaining} formula(s) remaining. Consider upgrading your subscription for more formulas."
        else:
            # No notification needed if below 80%
            return None
        
        # Check if similar notification already exists recently to avoid spam
        recent_notifications = self.get_recent_notifications_by_type(
            user_id=user_id,
            notification_type="subscription",
            hours=24,  # Only check notifications from the last 24 hours
            title_contains="Formula Limit"
        )
        
        # If a similar notification was sent in the last 24 hours, don't send another one
        if recent_notifications:
            logger.info(f"Similar formula quota notification already sent in the last 24 hours to user {user_id}")
            return None
        
        # Create notification
        notification_data = NotificationData(
            user_id=user_id,
            title=title,
            message=message,
            notification_type="subscription",
            reference_id=None
        )
        
        return self.create_notification(notification_data)
    
    def notify_formula_creation(
        self, 
        user_id: int, 
        formula_id: int, 
        formula_name: str
    ) -> models.Notification:
        """
        Create a notification when a new formula is created
        """
        notification_data = NotificationData(
            user_id=user_id,
            title="Formula Created",
            message=f"Your formula '{formula_name}' has been created successfully.",
            notification_type="formula",
            reference_id=formula_id
        )
        
        return self.create_notification(notification_data)
    
    def notify_subscription_change(
        self,
        user_id: int,
        new_subscription_type: str,
        old_subscription_type: str
    ) -> models.Notification:
        """
        Create a notification when subscription changes
        """
        # Format display name for subscription types
        def format_subscription_type(type_str):
            if type_str == "premium":
                return "Premium"
            elif type_str == "professional":
                return "Professional"
            elif type_str == "creator":
                return "Creator"
            elif type_str == "pro_lab":
                return "Pro Lab"
            else:
                return type_str.capitalize()
        
        new_type_display = format_subscription_type(new_subscription_type)
        old_type_display = format_subscription_type(old_subscription_type)
        
        # Handle upgrade vs. downgrade messaging
        if new_subscription_type == 'free':
            if old_subscription_type != 'free':
                title = "Subscription Downgraded"
                message = f"Your subscription has been downgraded to the Free plan. Some features may no longer be available."
            else:
                title = "Free Plan Active"
                message = "You are currently on the Free plan. Upgrade to access premium features."
        elif new_subscription_type in ['premium', 'professional']:
            if old_subscription_type == 'free':
                title = "Subscription Upgraded"
                message = f"Your subscription has been upgraded to the {new_type_display} plan. Enjoy your new features!"
            elif (old_subscription_type == 'premium' and new_subscription_type == 'professional'):
                title = "Subscription Upgraded"
                message = f"Your subscription has been upgraded to the {new_type_display} plan. You now have access to all professional features!"
            elif (old_subscription_type == 'professional' and new_subscription_type == 'premium'):
                title = "Subscription Changed"
                message = f"Your subscription has been changed to the {new_type_display} plan. Some professional features may no longer be available."
            else:
                title = "Subscription Updated"
                message = f"Your subscription has been updated to the {new_type_display} plan."
        else:
            title = "Subscription Changed"
            message = f"Your subscription has been changed to {new_type_display}."
        
        notification_data = NotificationData(
            user_id=user_id,
            title=title,
            message=message,
            notification_type="subscription",
            reference_id=None
        )
        
        return self.create_notification(notification_data)
    
    def notify_subscription_expiring(
        self,
        user_id: int,
        subscription_type: str,
        days_remaining: int
    ) -> models.Notification:
        """
        Create a notification when subscription is about to expire
        """
        # Format display name for subscription type
        if subscription_type == "premium":
            display_name = "Premium"
        elif subscription_type == "professional":
            display_name = "Professional"
        else:
            display_name = subscription_type.capitalize()
            
        notification_data = NotificationData(
            user_id=user_id,
            title="Subscription Expiring Soon",
            message=f"Your {display_name} plan will expire in {days_remaining} days. Please renew to maintain access to premium features.",
            notification_type="subscription",
            reference_id=None
        )
        
        return self.create_notification(notification_data)
    def get_recent_notifications_by_type(self, user_id, notification_type, hours=24, title_contains=None):
        """
        Get recent notifications of a specific type for a user
        
        Args:
            user_id: The user ID
            notification_type: The type of notification to filter by
            hours: Number of hours to look back (default: 24)
            title_contains: Optional string to filter notification titles
            
        Returns:
            List of notifications matching the criteria
        """
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        query = (
            self.db.query(models.Notification)
            .filter(models.Notification.user_id == user_id)
            .filter(models.Notification.notification_type == notification_type)
            .filter(models.Notification.created_at >= time_threshold)
        )
        
        if title_contains:
            query = query.filter(models.Notification.title.ilike(f"%{title_contains}%"))
        
        return query.all()