# backend/app/api/endpoints/payments.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import stripe
import uuid
import requests

from app import crud, models, schemas
from app.database import get_db
from app.auth import get_current_user
from app.config import settings

router = APIRouter()

# Pydantic models for requests
class SubscriptionCreate(BaseModel):
    subscription_type: str
class SubscriptionData(BaseModel):
    subscription_type: str
class SessionVerify(BaseModel):
    session_id: str


# Setup Stripe on startup
@router.on_event("startup")
async def startup_event():
    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY
    print(f"Stripe initialized with API key ending in ...{settings.STRIPE_SECRET_KEY[-4:]}")

# backend/app/api/endpoints/payments.py

@router.post("/create-checkout-session")
async def create_checkout_session_endpoint(
    subscription_data: SubscriptionData,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a checkout session for subscription"""
    try:
        # Get price based on subscription type
        if subscription_data.subscription_type == "premium":
            price_amount = 1299  # $12.99
            product_name = "Premium Plan"
        elif subscription_data.subscription_type == "professional":
            price_amount = 2999  # $29.99
            product_name = "Professional Plan"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription type: {subscription_data.subscription_type}"
            )
        
        # Set up the frontend URLs
        frontend_url = settings.FRONTEND_URL or "http://localhost:5173"
        success_url = f"{frontend_url}/subscribe/success?session_id={{CHECKOUT_SESSION_ID}}&subscription_type={subscription_data.subscription_type}"
        cancel_url = f"{frontend_url}/subscribe/cancel"
        
        # If we have Stripe API key, create a real session
        if settings.STRIPE_SECRET_KEY and settings.STRIPE_SECRET_KEY != "your_stripe_secret_key":
            try:
                # Create a Stripe checkout session
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[
                        {
                            "price_data": {
                                "currency": "usd",
                                "product_data": {
                                    "name": product_name,
                                },
                                "unit_amount": price_amount,
                            },
                            "quantity": 1,
                        },
                    ],
                    mode="payment",
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "user_id": str(current_user.id),
                        "subscription_type": subscription_data.subscription_type
                    },
                    client_reference_id=str(current_user.id)
                )
                
                return {
                    "checkout_url": checkout_session.url,
                    "session_id": checkout_session.id
                }
            except Exception as e:
                print(f"Stripe error: {str(e)}")
                # Fall back to mock checkout if Stripe fails
        
        # For development or if Stripe key is not set, create a mock session
        print("Using mock checkout session (Stripe key not set or error occurred)")
        
        # Create a mock checkout session
        import uuid
        import time
        
        # Mock a 3-second payment processing delay
        mock_checkout_page_url = f"{frontend_url}/mock-checkout?type={subscription_data.subscription_type}&price={price_amount/100}&redirect_after=3&success_url={success_url.replace('{CHECKOUT_SESSION_ID}', str(uuid.uuid4()))}"
        
        return {
            "checkout_url": mock_checkout_page_url,
            "session_id": f"mock_session_{int(time.time())}"
        }
        
    except Exception as e:
        print(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/verify-session")
async def verify_session(
    session_data: dict,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify subscription after successful checkout"""
    try:
        session_id = session_data.get("session_id")
        subscription_type = session_data.get("subscription_type")
        
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID is required"
            )
        
        if not subscription_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription type is required"
            )
        
        # For a real implementation, verify the session with Stripe
        # For now, we'll just update the user's subscription
        
        # Update user subscription
        current_user.subscription_type = subscription_type
        current_user.needs_subscription = False
        
        # Set subscription expiry date
        current_user.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
        
        # Save to database
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "subscription_type": current_user.subscription_type,
                "needs_subscription": current_user.needs_subscription,
                "subscription_ends_at": current_user.subscription_ends_at.isoformat() if current_user.subscription_ends_at else None
            },
            "message": f"Successfully subscribed to {subscription_type} plan"
        }
    
    except Exception as e:
        print(f"Error verifying session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )@router.get("/subscription-status")
@router.get("/subscription-status")
async def get_subscription_status(
    current_user: models.User = Depends(get_current_user)
):
    """Get current user's subscription status"""
    is_active = True
    if current_user.subscription_ends_at and current_user.subscription_ends_at < datetime.utcnow():
        is_active = False
    
    return {
        "subscription_type": current_user.subscription_type,
        "is_active": is_active,
        "expiration_date": current_user.subscription_ends_at
    }


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Handle webhook events from Stripe"""
    # Get the webhook secret from settings
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    if not webhook_secret and settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret not configured"
        )
    
    try:
        # Get request body as bytes
        payload = await request.body()
        
        # For production, verify webhook signature
        if settings.ENVIRONMENT == "production" and webhook_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, stripe_signature, webhook_secret
                )
            except stripe.error.SignatureVerificationError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid signature"
                )
        else:
            # For development, parse the event without signature verification
            data = await request.json()
            event = data
        
        # Handle different event types
        event_type = event.get('type', '')
        
        if event_type == 'checkout.session.completed':
            # Payment was successful, update subscription
            session = event['data']['object']
            user_id = session.get('client_reference_id') or session.get('metadata', {}).get('user_id')
            
            if user_id:
                subscription_type = session.get('metadata', {}).get('subscription_type')
                if subscription_type:
                    # Update user subscription
                    user = crud.get_user(db, user_id=int(user_id))
                    if user:
                        user.subscription_type = subscription_type
                        user.needs_subscription = False
                        user.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
                        
                        # If there's a Stripe subscription ID, save it
                        stripe_subscription_id = session.get('subscription')
                        if stripe_subscription_id:
                            user.stripe_subscription_id = stripe_subscription_id
                            
                        db.commit()
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription was cancelled
            subscription = event['data']['object']
            # Find user by Stripe customer ID
            customer_id = subscription.get('customer')
            if customer_id:
                # In a real app, you'd look up the user by Stripe customer ID
                # This is a simplified example
                pass
        
        # Return success to acknowledge receipt
        return {"status": "success"}
    
    except Exception as e:
        # Log error but return success to acknowledge receipt (Stripe will retry otherwise)
        print(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}