# backend/app/services/sms_service.py
import logging
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

def send_verification_code(phone_number, verification_code):
    """
    Send a verification code SMS to the given phone number.
    
    Args:
        phone_number: The phone number to send the SMS to
        verification_code: The verification code to send
        
    Returns:
        str: A message ID if sent, or None if there was an error
    """
    # For development, just log the verification code
    logger.info(f"SMS to {phone_number}: Your verification code is: {verification_code}")
    
    # In production with Twilio:
    if settings.ENVIRONMENT == "production" and hasattr(settings, "TWILIO_ENABLED") and settings.TWILIO_ENABLED:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=f"Your verification code for Cosmetic Formula Lab is: {verification_code}",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            logger.info(f"SMS sent successfully with ID: {message.sid}")
            return message.sid
        except Exception as e:
            logger.error(f"Twilio SMS error: {str(e)}")
            return None
    return "dev-mode-no-sms-sent"

def send_verification_sms(phone_number, verification_code):
    """
    Alias for send_verification_code for backward compatibility
    """
    return send_verification_code(phone_number, verification_code)
def send_formula_limit_sms(phone_number, formula_count, formula_limit, subscription_type):
    """
    Send an SMS notification about reaching the formula limit.
    
    Args:
        phone_number: The phone number to send the SMS to
        formula_count: Current number of formulas
        formula_limit: Maximum number of formulas allowed
        subscription_type: Current subscription type
        
    Returns:
        str: A message ID if sent, or None if there was an error
    """
    # Format the message based on how close the user is to their limit
    if formula_limit == 'Unlimited' or formula_limit == float('inf'):
        # No need to send notification for unlimited plans
        return None
        
    # Calculate percentage used
    percentage = (formula_count / formula_limit) * 100 if isinstance(formula_limit, (int, float)) else 0
    
    # Determine message based on usage level
    if formula_count >= formula_limit:
        message = f"Cosmetic Formula Lab: You've reached your formula limit ({formula_count}/{formula_limit}) with your {subscription_type} plan. Please upgrade to create more formulas."
    elif percentage >= 90:
        remaining = formula_limit - formula_count
        message = f"Cosmetic Formula Lab: You're almost at your formula limit! {formula_count}/{formula_limit} formulas used. Only {remaining} left with your {subscription_type} plan."
    else:
        remaining = formula_limit - formula_count
        message = f"Cosmetic Formula Lab: You've used {formula_count} of your {formula_limit} formulas. {remaining} formulas remaining with your {subscription_type} plan."
    
    logger.info(f"Formula limit SMS to {phone_number}: {message}")
    
    # In production with Twilio:
    if settings.ENVIRONMENT == "production" and hasattr(settings, "TWILIO_ENABLED") and settings.TWILIO_ENABLED:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            sms = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            logger.info(f"Formula limit SMS sent successfully with ID: {sms.sid}")
            return sms.sid
        except Exception as e:
            logger.error(f"Twilio SMS error for formula limit notification: {str(e)}")
            return None
    
    return "dev-mode-no-sms-sent"

def send_subscription_change_sms(phone_number, old_plan, new_plan, expires_at=None):
    """
    Send an SMS notification about a subscription change.
    
    Args:
        phone_number: The phone number to send the SMS to
        old_plan: Previous subscription plan
        new_plan: New subscription plan
        expires_at: When the subscription expires (optional)
        
    Returns:
        str: A message ID if sent, or None if there was an error
    """
    # Format display names for plans
    plan_display_names = {
        "free": "Free",
        "premium": "Premium",
        "creator": "Creator",
        "professional": "Professional",
        "pro_lab": "Pro Lab"
    }
    
    old_plan_display = plan_display_names.get(old_plan, old_plan.capitalize())
    new_plan_display = plan_display_names.get(new_plan, new_plan.capitalize())
    
    # Format expiration date if provided
    expiry_text = ""
    if expires_at:
        try:
            from datetime import datetime
            # Convert string to datetime if needed
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            
            expiry_text = f" Your subscription renews on {expires_at.strftime('%b %d, %Y')}."
        except Exception as e:
            logger.error(f"Error formatting expiration date: {str(e)}")
    
    # Create the message based on upgrade or downgrade
    if new_plan == 'free':
        if old_plan != 'free':
            message = f"Cosmetic Formula Lab: Your subscription has been downgraded to the Free plan. Some features may no longer be available."
        else:
            message = f"Cosmetic Formula Lab: Your Free plan is active. Upgrade anytime to access premium features."
    elif new_plan in ['premium', 'professional', 'creator', 'pro_lab']:
        if old_plan == 'free':
            message = f"Cosmetic Formula Lab: Your subscription has been upgraded to the {new_plan_display} plan! Enjoy your new features.{expiry_text}"
        elif (old_plan in ['premium', 'creator'] and new_plan in ['professional', 'pro_lab']):
            message = f"Cosmetic Formula Lab: Your subscription has been upgraded to the {new_plan_display} plan. You now have access to all professional features!{expiry_text}"
        elif (old_plan in ['professional', 'pro_lab'] and new_plan in ['premium', 'creator']):
            message = f"Cosmetic Formula Lab: Your subscription has been changed to the {new_plan_display} plan. Some professional features may no longer be available.{expiry_text}"
        else:
            message = f"Cosmetic Formula Lab: Your subscription has been updated to the {new_plan_display} plan.{expiry_text}"
    else:
        message = f"Cosmetic Formula Lab: Your subscription has been changed to {new_plan_display}.{expiry_text}"
    
    logger.info(f"Subscription change SMS to {phone_number}: {message}")
    
    # In production with Twilio:
    if settings.ENVIRONMENT == "production" and hasattr(settings, "TWILIO_ENABLED") and settings.TWILIO_ENABLED:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            sms = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            logger.info(f"Subscription change SMS sent successfully with ID: {sms.sid}")
            return sms.sid
        except Exception as e:
            logger.error(f"Twilio SMS error for subscription change notification: {str(e)}")
            return None
    
    return "dev-mode-no-sms-sent"