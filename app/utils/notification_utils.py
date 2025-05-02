# backend/app/utils/notification_utils.py
from sqlalchemy.orm import Session
from app.services.notification_service import NotificationService, NotificationData
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def notify_formula_quota(
    db: Session,
    user_id: int,
    subscription_type: str,
    formula_count: int,
    max_formulas: int
):
    """
    Send a notification to the user about approaching their formula quota
    """
    try:
        # Initialize notification service
        notification_service = NotificationService(db)
        
        # Check if user has already been notified recently
        existing_notifications = notification_service.get_recent_notifications_by_type(
            user_id=user_id,
            notification_type="subscription",
            hours=24,  # Only check notifications from the last 24 hours
            title_contains="Formula Limit"
        )
        
        # Don't send duplicate notifications
        if existing_notifications:
            logger.info(f"Skipping quota notification for user {user_id} as one was recently sent")
            return
        
        # Create notification using service helper
        notification_service.notify_formula_quota(
            user_id=user_id,
            formula_count=formula_count,
            formula_limit=max_formulas,
            subscription_type=subscription_type
        )
        
        logger.info(f"Created quota notification for user {user_id}: {formula_count}/{max_formulas} formulas used")
    except Exception as e:
        # Log error but don't disrupt the main functionality
        logger.error(f"Error sending formula quota notification: {str(e)}")

def notify_formula_creation(
    db: Session,
    user_id: int,
    formula_id: int,
    formula_name: str
):
    """
    Send a notification to the user about a new formula being created
    """
    try:
        # Initialize notification service
        notification_service = NotificationService(db)
        
        # Create notification using service helper
        notification_service.notify_formula_creation(
            user_id=user_id,
            formula_id=formula_id,
            formula_name=formula_name
        )
        
        logger.info(f"Created formula creation notification for user {user_id}: Formula {formula_id}")
    except Exception as e:
        # Log error but don't disrupt the main functionality
        logger.error(f"Error sending formula creation notification: {str(e)}")

def notify_subscription_change(
    db: Session,
    user_id: int,
    new_subscription_type: str,
    old_subscription_type: str
):
    """
    Send a notification to the user about a subscription change
    """
    try:
        # Initialize notification service
        notification_service = NotificationService(db)
        
        # Create notification using service helper
        notification_service.notify_subscription_change(
            user_id=user_id,
            new_subscription_type=new_subscription_type,
            old_subscription_type=old_subscription_type
        )
        
        logger.info(f"Created subscription change notification for user {user_id}: {old_subscription_type} -> {new_subscription_type}")
    except Exception as e:
        # Log error but don't disrupt the main functionality
        logger.error(f"Error sending subscription change notification: {str(e)}")

def get_formula_limit_by_subscription(subscription_type: str) -> int:
    """Return the maximum number of formulas allowed for a subscription type"""
    limits = {
        "free": 3,
        "creator": 30,
        "pro_lab": float('inf')  # Unlimited
    }
    return limits.get(subscription_type.lower(), 3)  # Default to free tier limit if unknown