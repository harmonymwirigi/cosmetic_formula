import logging
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

def send_verification_sms(phone_number, verification_code):
    """
    Send a verification SMS to the given phone number.
    
    In production, this would use a service like Twilio, but for development,
    we'll just log the message.
    """
    # For development, just log the verification code
    logger.info(f"SMS to {phone_number}: Your verification code is: {verification_code}")
    
    # In production with Twilio:
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     body=f"Your verification code is: {verification_code}",
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )
    # return message.sid