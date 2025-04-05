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
class SubscriptionData(BaseModel):
    subscription_type: str
    billing_cycle: Optional[str] = "monthly"

class SessionVerify(BaseModel):
    session_id: str
    subscription_type: Optional[str] = None


# Setup Stripe on startup
@router.on_event("startup")
async def startup_event():
    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY
    print(f"Stripe initialized with API key ending in ...{settings.STRIPE_SECRET_KEY[-4:] if settings.STRIPE_SECRET_KEY else 'not set'}")


@router.post("/create-checkout-session")
async def create_checkout_session(
    subscription_data: SubscriptionData,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a checkout session for subscription"""
    try:
        # Get price based on subscription type and billing cycle
        billing_cycle = subscription_data.billing_cycle or "monthly"
        is_annual = billing_cycle == "annual"
        
        if subscription_data.subscription_type == "premium":
            price_amount = 9999 if is_annual else 999  # $99.99/year or $9.99/month
            product_name = "Premium Plan"
        elif subscription_data.subscription_type == "professional":
            price_amount = 24999 if is_annual else 2499  # $249.99/year or $24.99/month
            product_name = "Professional Plan"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription type: {subscription_data.subscription_type}"
            )
        
        # Set up the frontend URLs
        frontend_url = settings.FRONTEND_URL or "http://localhost:5173"
        success_url = f"{frontend_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}&subscription_type={subscription_data.subscription_type}"
        cancel_url = f"{frontend_url}/subscription/cancel"
        
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
                                    "name": f"{product_name} - {billing_cycle.capitalize()}",
                                },
                                "unit_amount": price_amount,
                                "recurring": {
                                    "interval": "year" if is_annual else "month",
                                } if True else None,  # True for subscription, False for one-time
                            },
                            "quantity": 1,
                        },
                    ],
                    mode="subscription",  # Can be "subscription" or "payment"
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "user_id": str(current_user.id),
                        "subscription_type": subscription_data.subscription_type,
                        "billing_cycle": billing_cycle
                    },
                    client_reference_id=str(current_user.id)
                )
                
                return {
                    "checkout_url": checkout_session.url,
                    "session_id": checkout_session.id
                }
            except Exception as e:
                print(f"Stripe error: {str(e)}")
                # Only fall back to mock if in development mode
                if settings.ENVIRONMENT != "production":
                    print("Falling back to mock checkout due to Stripe error")
                else:
                    raise
        
        # For development without Stripe keys, create a mock session
        if settings.ENVIRONMENT != "production":
            print("Using mock checkout session (non-production environment)")
            
            # Create a mock checkout session
            import time
            mock_session_id = f"mock_session_{int(time.time())}"
            
            # In a real implementation, you'd add a redirect to Stripe here
            # For development, we'll use a simulated success flow
            mock_checkout_url = f"{frontend_url}/subscription/confirm?plan={subscription_data.subscription_type}&billing_cycle={billing_cycle}&session_id={mock_session_id}"
            
            return {
                "checkout_url": mock_checkout_url,
                "session_id": mock_session_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe integration is required in production mode"
            )
        
    except Exception as e:
        print(f"Error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/verify-session")
async def verify_session(
    session_data: SessionVerify,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify subscription after successful checkout"""
    try:
        session_id = session_data.session_id
        subscription_type = session_data.subscription_type
        
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session ID is required"
            )
        
        # Handle real Stripe sessions
        if not session_id.startswith("mock_session_") and settings.STRIPE_SECRET_KEY:
            try:
                # Verify with Stripe
                checkout_session = stripe.checkout.Session.retrieve(session_id)
                
                # Check if the session is completed
                if checkout_session.status != "complete":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Payment not completed"
                    )
                
                # Get subscription type from metadata
                subscription_type = checkout_session.metadata.get("subscription_type", subscription_type)
                billing_cycle = checkout_session.metadata.get("billing_cycle", "monthly")
                
                # For subscriptions, get subscription ID
                subscription_id = checkout_session.subscription
            except stripe.error.StripeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stripe error: {str(e)}"
                )
        else:
            # For mock sessions in development
            subscription_id = f"mock_sub_{uuid.uuid4()}"
            if not subscription_type:
                # Try to get from query params if missing
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subscription type is required for mock sessions"
                )
            billing_cycle = "monthly"  # Default for mock
        
        # Update user subscription
        if subscription_type not in ["premium", "professional"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription type: {subscription_type}"
            )
            
        # Convert subscription type string to enum
        user_subscription_type = models.SubscriptionType.PREMIUM
        if subscription_type == "professional":
            user_subscription_type = models.SubscriptionType.PROFESSIONAL
            
        # Calculate subscription end date based on billing cycle
        if billing_cycle == "annual":
            subscription_expires_at = datetime.utcnow() + timedelta(days=365)
        else:
            subscription_expires_at = datetime.utcnow() + timedelta(days=30)
            
        # Update user
        current_user.subscription_type = user_subscription_type
        current_user.needs_subscription = False
        current_user.subscription_id = subscription_id
        current_user.subscription_expires_at = subscription_expires_at
        
        # Save to database
        db.commit()
        db.refresh(current_user)
        
        # Format the date properly for the response
        formatted_date = None
        if current_user.subscription_expires_at:
            formatted_date = current_user.subscription_expires_at.isoformat()
        
        return {
            "success": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "first_name": current_user.first_name,
                "last_name": current_user.last_name,
                "subscription_type": current_user.subscription_type.value,
                "needs_subscription": current_user.needs_subscription,
                "subscription_expires_at": formatted_date
            },
            "message": f"Successfully subscribed to {subscription_type} plan"
        }
    
    except Exception as e:
        print(f"Error verifying session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/subscription-status")
async def get_subscription_status(
    current_user: models.User = Depends(get_current_user)
):
    """Get current user's subscription status"""
    is_active = True
    if current_user.subscription_expires_at and current_user.subscription_expires_at < datetime.utcnow():
        is_active = False
    
    return {
        "subscription_type": current_user.subscription_type.value,
        "is_active": is_active,
        "expiration_date": current_user.subscription_expires_at
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
        print("Warning: Stripe webhook secret not configured in production")
    
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
                billing_cycle = session.get('metadata', {}).get('billing_cycle', 'monthly')
                
                if subscription_type:
                    # Update user subscription
                    user = crud.get_user(db, user_id=int(user_id))
                    if user:
                        # Convert subscription type string to enum
                        user_subscription_type = models.SubscriptionType.PREMIUM
                        if subscription_type == "professional":
                            user_subscription_type = models.SubscriptionType.PROFESSIONAL
                            
                        # Calculate subscription end date
                        if billing_cycle == "annual":
                            subscription_expires_at = datetime.utcnow() + timedelta(days=365)
                        else:
                            subscription_expires_at = datetime.utcnow() + timedelta(days=30)
                        
                        user.subscription_type = user_subscription_type
                        user.needs_subscription = False
                        user.subscription_expires_at = subscription_expires_at
                        
                        # If there's a Stripe subscription ID, save it
                        stripe_subscription_id = session.get('subscription')
                        if stripe_subscription_id:
                            user.subscription_id = stripe_subscription_id
                            
                        db.commit()
        
        elif event_type == 'customer.subscription.deleted':
            # Subscription was cancelled
            subscription = event['data']['object']
            # Find user by Stripe subscription ID
            subscription_id = subscription.get('id')
            if subscription_id:
                # Look up the user by subscription ID
                users = db.query(models.User).filter(models.User.subscription_id == subscription_id).all()
                for user in users:
                    user.subscription_type = models.SubscriptionType.FREE
                    user.needs_subscription = True
                    user.subscription_expires_at = None
                    db.commit()
        
        # Return success to acknowledge receipt
        return {"status": "success"}
    
    except Exception as e:
        # Log error but return success to acknowledge receipt (Stripe will retry otherwise)
        print(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}
    
    
@router.post("/cancel-subscription", response_model=Dict[str, Any])
async def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Cancel a subscription.
    In a real implementation, this would connect to a payment provider like Stripe.
    """
    try:
        # Check if user has an active subscription
        if current_user.subscription_type == models.SubscriptionType.FREE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription to cancel"
            )
        
        # If there's a real Stripe subscription, cancel it
        if current_user.subscription_id and not current_user.subscription_id.startswith("mock_") and settings.STRIPE_SECRET_KEY:
            try:
                # Cancel the subscription in Stripe
                stripe.Subscription.delete(current_user.subscription_id)
            except stripe.error.StripeError as e:
                print(f"Stripe error when cancelling: {str(e)}")
                # We'll still cancel locally even if Stripe fails
        
        # Update user record
        current_user.subscription_type = models.SubscriptionType.FREE
        current_user.subscription_expires_at = None
        current_user.subscription_id = None
        
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling subscription: {str(e)}"
        )