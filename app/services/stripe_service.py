# backend/app/services/stripe_service.py
import stripe
from app.config import settings
from app.models import SubscriptionType
from datetime import datetime, timedelta
import logging

# Configure Stripe with API key
stripe.api_key = settings.STRIPE_SECRET_KEY

# Define subscription plan IDs
STRIPE_PLAN_IDS = {
    SubscriptionType.PREMIUM: "premium_monthly",
    SubscriptionType.PROFESSIONAL: "professional_monthly",
}

# Price mapping
SUBSCRIPTION_PRICES = {
    SubscriptionType.PREMIUM: 1299,  # $12.99
    SubscriptionType.PROFESSIONAL: 2999,  # $29.99
}

def setup_stripe():
    """
    Setup Stripe products and prices if they don't exist
    """
    if not settings.STRIPE_SECRET_KEY:
        logging.warning("Stripe API key not set, skipping Stripe setup")
        return
    
    try:
        # Check if products exist, if not create them
        products = stripe.Product.list(limit=100)
        product_map = {product.name.lower(): product.id for product in products.data}
        
        # Create Premium product if it doesn't exist
        if "premium" not in product_map:
            premium_product = stripe.Product.create(
                name="Premium",
                description="Premium subscription for Cosmetic Formula Lab",
            )
            premium_price = stripe.Price.create(
                product=premium_product.id,
                unit_amount=SUBSCRIPTION_PRICES[SubscriptionType.PREMIUM],
                currency="usd",
                recurring={"interval": "month"},
                lookup_key=STRIPE_PLAN_IDS[SubscriptionType.PREMIUM],
            )
            logging.info(f"Created Premium product and price: {premium_price.id}")
        
        # Create Professional product if it doesn't exist
        if "professional" not in product_map:
            professional_product = stripe.Product.create(
                name="Professional",
                description="Professional subscription for Cosmetic Formula Lab",
            )
            professional_price = stripe.Price.create(
                product=professional_product.id,
                unit_amount=SUBSCRIPTION_PRICES[SubscriptionType.PROFESSIONAL],
                currency="usd",
                recurring={"interval": "month"},
                lookup_key=STRIPE_PLAN_IDS[SubscriptionType.PROFESSIONAL],
            )
            logging.info(f"Created Professional product and price: {professional_price.id}")
        
        return True
    except Exception as e:
        logging.error(f"Error setting up Stripe products: {e}")
        return False

def create_checkout_session(subscription_type: SubscriptionType, user_id: int, success_url: str, cancel_url: str):
    """
    Create a Stripe checkout session for subscription
    """
    try:
        # Get price based on subscription type
        price_lookup_key = STRIPE_PLAN_IDS.get(subscription_type)
        if not price_lookup_key:
            raise ValueError(f"Invalid subscription type: {subscription_type}")
        
        # Get price ID
        prices = stripe.Price.list(lookup_keys=[price_lookup_key], limit=1)
        if not prices.data:
            raise ValueError(f"Price not found for lookup key: {price_lookup_key}")
        
        price_id = prices.data[0].id
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            success_url=success_url,
            cancel_url=cancel_url,
            payment_method_types=["card"],
            mode="subscription",
            client_reference_id=str(user_id),
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            metadata={
                "user_id": user_id,
                "subscription_type": subscription_type,
            },
        )
        
        return checkout_session
    except Exception as e:
        logging.error(f"Error creating checkout session: {e}")
        raise

def handle_webhook_event(payload, sig_header):
    """
    Handle Stripe webhook events
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        
        # Handle checkout session completed
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            return {
                'event_type': event['type'],
                'user_id': int(session.get('client_reference_id')),
                'subscription_id': session.get('subscription'),
                'subscription_type': session.get('metadata', {}).get('subscription_type'),
                'status': 'success',
            }
        
        # Handle subscription updated
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            
            # Get user_id from metadata or subscription
            user_id = None
            if subscription.get('metadata') and subscription.get('metadata').get('user_id'):
                user_id = int(subscription.get('metadata').get('user_id'))
            
            return {
                'event_type': event['type'],
                'user_id': user_id,
                'subscription_id': subscription.get('id'),
                'status': subscription.get('status'),
                'current_period_end': subscription.get('current_period_end'),
            }
        
        # Handle subscription deleted
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            
            # Get user_id from metadata or subscription
            user_id = None
            if subscription.get('metadata') and subscription.get('metadata').get('user_id'):
                user_id = int(subscription.get('metadata').get('user_id'))
            
            return {
                'event_type': event['type'],
                'user_id': user_id,
                'subscription_id': subscription.get('id'),
                'status': 'canceled',
            }
        
        # Return the event type for other events
        return {
            'event_type': event['type'],
            'status': 'unhandled',
        }
    
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"Invalid signature: {e}")
        raise
    except Exception as e:
        logging.error(f"Error handling webhook: {e}")
        raise

def create_stripe_customer(email, name=None):
    """
    Create a Stripe customer
    """
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name
        )
        return customer.id
    except Exception as e:
        logging.error(f"Error creating Stripe customer: {e}")
        raise