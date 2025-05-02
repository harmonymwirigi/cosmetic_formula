# backend/app/api/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string
import logging
from app.auth import get_current_user
from app import crud, models, schemas
from app.database import get_db
from app.config import settings
from app.services.sms_service import send_verification_sms  # You'll need to create this

router = APIRouter()

# Request phone verification code
@router.post("/auth/request-phone-verification", response_model=schemas.MessageResponse)
def request_phone_verification(
    request: schemas.PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Request a verification code for phone number
    """
    logging.info(f"Phone verification requested for user {current_user.id} and number {request.phone_number}")
    
    # Generate a 6-digit code
    verification_code = ''.join(random.choices(string.digits, k=6))
    
    # Set expiry (10 minutes)
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Update user record
    current_user.phone_number = request.phone_number
    current_user.phone_verification_code = verification_code
    current_user.phone_verification_expiry = expiry
    current_user.is_phone_verified = False
    
    db.commit()
    
    # Send SMS
    try:
        send_verification_sms(request.phone_number, verification_code)
        logging.info(f"Verification code sent to {request.phone_number}")
        return {"message": "Verification code sent to your phone"}
    except Exception as e:
        logging.error(f"Failed to send verification code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification code: {str(e)}"
        )


# Verify phone number with code
@router.post("/auth/verify-phone", response_model=schemas.MessageResponse)
def verify_phone(
    verification: schemas.PhoneVerificationCode,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Verify a phone number with a received code
    """
    logging.info(f"Phone verification code submitted for user {current_user.id}")
    
    # Check if phone number matches
    if current_user.phone_number != verification.phone_number:
        logging.warning(f"Phone number mismatch for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match"
        )
    
    # Check if code is valid and not expired
    now = datetime.utcnow()
    if (current_user.phone_verification_code != verification.code):
        logging.warning(f"Invalid verification code for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
        
    if (current_user.phone_verification_expiry < now):
        logging.warning(f"Expired verification code for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expired verification code"
        )
    
    # Mark phone as verified
    current_user.is_phone_verified = True
    current_user.phone_verification_code = None  # Clear the code
    
    db.commit()
    
    logging.info(f"Phone number verified successfully for user {current_user.id}")
    return {"message": "Phone number verified successfully"}