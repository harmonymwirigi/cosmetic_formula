# backend/app/utils/notification_utils.py

import logging
from sqlalchemy.orm import Session
from app import models
from app.services.notification_service import NotificationService, NotificationData
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)

def notify_formula_quota(
    db: Session, 
    user_id: int, 
    subscription_type: str, 
    formula_count: int, 
    max_formulas: int
):
    """
    Send a notification about formula quota usage
    
    Args:
        db: Database session
        user_id: User ID to notify
        subscription_type: User's subscription type
        formula_count: Current number of formulas
        max_formulas: Maximum number of formulas allowed
    """
    try:
        # Skip for unlimited plans
        if max_formulas == float('inf'):
            return
        
        # Calculate remaining formulas
        remaining = max_formulas - formula_count
        
        # Create notification service
        notification_service = NotificationService(db)
        
        if formula_count >= max_formulas:
            # User has reached their limit
            notification_data = NotificationData(
                user_id=user_id,
                title="Formula Limit Reached",
                message=f"You have reached your limit of {max_formulas} formulas with your {subscription_type} plan. Upgrade to create more formulas.",
                notification_type="subscription",
                reference_id=None
            )
        elif formula_count >= int(max_formulas * 0.8):
            # User is approaching their limit (80% or more)
            notification_data = NotificationData(
                user_id=user_id,
                title="Formula Limit Approaching",
                message=f"You have used {formula_count} out of {max_formulas} formulas allowed in your {subscription_type} plan. You have {remaining} formula(s) remaining.",
                notification_type="subscription",
                reference_id=None
            )
        else:
            # No notification needed
            return
        
        # Create the notification
        notification = notification_service.create_notification(notification_data)
        logger.info(f"Created formula quota notification for user {user_id}: {notification.title}")
        
    except Exception as e:
        logger.error(f"Error creating formula quota notification: {str(e)}")

def notify_subscription_action(
    db: Session, 
    user_id: int, 
    action_type: str,
    details: Optional[dict] = None
):
    """
    Send a notification about subscription-related events
    
    Args:
        db: Database session
        user_id: User ID to notify
        action_type: Type of action (e.g., 'upgraded', 'renewed', 'canceled')
        details: Optional details about the action
    """
    try:
        notification_service = NotificationService(db)
        
        subscription_type = details.get('subscription_type', 'premium') if details else 'premium'
        
        if action_type == 'upgraded':
            notification_data = NotificationData(
                user_id=user_id,
                title="Subscription Upgraded",
                message=f"Your subscription has been upgraded to {subscription_type}. Enjoy your new features!",
                notification_type="subscription",
                reference_id=None
            )
        elif action_type == 'renewed':
            renewal_date = details.get('renewal_date', 'next billing cycle') if details else 'next billing cycle'
            notification_data = NotificationData(
                user_id=user_id,
                title="Subscription Renewed",
                message=f"Your {subscription_type} subscription has been renewed until {renewal_date}.",
                notification_type="subscription",
                reference_id=None
            )
        elif action_type == 'canceled':
            end_date = details.get('end_date', 'the end of your billing cycle') if details else 'the end of your billing cycle'
            notification_data = NotificationData(
                user_id=user_id,
                title="Subscription Canceled",
                message=f"Your {subscription_type} subscription has been canceled. You'll have access to premium features until {end_date}.",
                notification_type="subscription",
                reference_id=None
            )
        else:
            # Unknown action type
            return
        
        # Create the notification
        notification = notification_service.create_notification(notification_data)
        logger.info(f"Created subscription notification for user {user_id}: {notification.title}")
        
    except Exception as e:
        logger.error(f"Error creating subscription notification: {str(e)}")

def notify_formula_creation(
    db: Session, 
    user_id: int, 
    formula_id: int, 
    formula_name: str
):
    """
    Send a notification when a formula is created
    
    Args:
        db: Database session
        user_id: User ID to notify
        formula_id: ID of the created formula
        formula_name: Name of the created formula
    """
    try:
        notification_service = NotificationService(db)
        
        notification_data = NotificationData(
            user_id=user_id,
            title="Formula Created",
            message=f"Your formula '{formula_name}' has been created successfully.",
            notification_type="formula",
            reference_id=formula_id
        )
        
        # Create the notification
        notification = notification_service.create_notification(notification_data)
        logger.info(f"Created formula creation notification for user {user_id}: {notification.title}")
        
    except Exception as e:
        logger.error(f"Error creating formula creation notification: {str(e)}")