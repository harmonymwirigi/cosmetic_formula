# backend/app/api/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string
from app.auth import get_current_user
from app import crud, models, schemas
from app.database import get_db
from app.config import settings
from app.services.sms_service import send_verification_sms  # You'll need to create this

router = APIRouter()

# Request phone verification
@router.post("/request-phone-verification", response_model=schemas.MessageResponse)
def request_phone_verification(
    request: schemas.PhoneVerificationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
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
        return {"message": "Verification code sent to your phone"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification code: {str(e)}"
        )

# Verify phone number with code
@router.post("/verify-phone", response_model=schemas.MessageResponse)
def verify_phone(
    verification: schemas.PhoneVerificationCode,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if phone number matches
    if current_user.phone_number != verification.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match"
        )
    
    # Check if code is valid and not expired
    now = datetime.utcnow()
    if (current_user.phone_verification_code != verification.code or
            current_user.phone_verification_expiry < now):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    # Mark phone as verified
    current_user.is_phone_verified = True
    current_user.phone_verification_code = None  # Clear the code
    
    db.commit()
    
    return {"message": "Phone number verified successfully"}