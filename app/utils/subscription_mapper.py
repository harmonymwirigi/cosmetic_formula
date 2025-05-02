# backend/app/utils/subscription_mapper.py

from app.models import SubscriptionType
from typing import Dict, Any, Union, Optional

# Frontend to backend mapping
FRONTEND_TO_BACKEND = {
    "free": SubscriptionType.FREE,
    "premium": SubscriptionType.PREMIUM,
    "professional": SubscriptionType.PROFESSIONAL,
    "creator": SubscriptionType.PREMIUM,  # Map creator to premium
    "pro_lab": SubscriptionType.PROFESSIONAL  # Map pro_lab to professional
}

# Backend to frontend mapping (for display)
BACKEND_TO_FRONTEND = {
    SubscriptionType.FREE.value: "free",
    SubscriptionType.PREMIUM.value: "creator",  # Map premium to creator for frontend
    SubscriptionType.PROFESSIONAL.value: "pro_lab"  # Map professional to pro_lab for frontend
}

# Display names for each subscription type
SUBSCRIPTION_DISPLAY_NAMES = {
    "free": "Free",
    "premium": "Premium",
    "professional": "Professional",
    "creator": "Creator",
    "pro_lab": "Pro Lab"
}

def map_to_backend_type(frontend_type: str) -> SubscriptionType:
    """
    Maps a frontend subscription type to the corresponding backend enum value
    
    Args:
        frontend_type: The subscription type as used in the frontend
        
    Returns:
        The corresponding SubscriptionType enum value
    """
    if not frontend_type:
        return SubscriptionType.FREE
        
    return FRONTEND_TO_BACKEND.get(frontend_type.lower(), SubscriptionType.FREE)

def map_to_frontend_type(backend_type: Union[SubscriptionType, str]) -> str:
    """
    Maps a backend subscription type to the corresponding frontend string
    
    Args:
        backend_type: The subscription type as used in the backend (enum or string)
        
    Returns:
        The corresponding frontend subscription type string
    """
    # Return default if input is None
    if backend_type is None:
        return "free"
        
    # Convert enum to string if needed
    if isinstance(backend_type, SubscriptionType):
        backend_type = backend_type.value
    
    # Handle string values
    backend_type_str = str(backend_type).lower()
    
    # Map directly from string if it matches a backend value
    if backend_type_str in BACKEND_TO_FRONTEND:
        return BACKEND_TO_FRONTEND[backend_type_str]
        
    # If it's already a frontend type, return it
    for frontend_type in ["free", "creator", "pro_lab"]:
        if backend_type_str == frontend_type:
            return frontend_type
            
    # Default to free
    return "free"

def get_display_name(subscription_type: str) -> str:
    """
    Gets a human-readable display name for a subscription type
    
    Args:
        subscription_type: The subscription type (backend or frontend format)
        
    Returns:
        A formatted display name for the subscription type
    """
    if not subscription_type:
        return "Free"
        
    return SUBSCRIPTION_DISPLAY_NAMES.get(subscription_type.lower(), subscription_type.capitalize())

def get_formula_limit(subscription_type: Union[SubscriptionType, str]) -> Union[int, float]:
    """
    Gets the formula limit for a given subscription type
    
    Args:
        subscription_type: The subscription type (enum or string)
        
    Returns:
        The formula limit (int or float('inf') for unlimited)
    """
    # Handle None value
    if subscription_type is None:
        return 3  # Default to free tier
        
    # Convert enum to string if needed
    if isinstance(subscription_type, SubscriptionType):
        subscription_type = subscription_type.value
        
    # Convert to lowercase string for comparison
    sub_type = str(subscription_type).lower()
    
    # Handle frontend types
    if sub_type in ["creator", "premium"]:
        return 30
    elif sub_type in ["pro_lab", "professional"]:
        return float('inf')  # Unlimited
    else:
        return 3  # Free tier