# backend/app/schemas.py
from pydantic import BaseModel, EmailStr, validator, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Enum for subscription types
class SubscriptionType(str, Enum):
    FREE = "free"
    CREATOR = "creator"
    PRO_LAB = "pro_lab"

# This matches your models.py SubscriptionType but also supports frontend names
class SubscriptionTypeEnum(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"
    # Add these for frontend compatibility
    CREATOR = "creator"  # Maps to PREMIUM in backend
    PRO_LAB = "pro_lab"  # Maps to PROFESSIONAL in backend
# Schemas for subscription management
class SubscriptionUpdate(BaseModel):
    subscription_type: SubscriptionTypeEnum

class SubscriptionCreate(BaseModel):
    subscription_type: str
    billing_cycle: str = "monthly"  # "monthly" or "annual"
    payment_method_id: Optional[str] = None

class SubscriptionStatusResponse(BaseModel):
    subscription_type: str
    is_active: bool
    expires_at: Optional[datetime] = None
    billing_cycle: Optional[str] = None
    payment_method: Optional[str] = None
    next_billing_date: Optional[datetime] = None
    auto_renew: bool = True
    features: Dict[str, Any]
    formula_limit: Any  # Can be int or "unlimited"
    formula_count: int
    formula_percentage: float

class SubscriptionCancelRequest(BaseModel):
    reason: Optional[str] = None
    feedback: Optional[str] = None

class SubscriptionFeatures(BaseModel):
    max_formulas: Any  # int or "unlimited"
    ingredient_access: str
    ai_recommendations: str
    export_formats: List[str]
    formula_analysis: bool
    formula_version_history: bool
    premium_support: bool
    custom_branding: bool

class SubscriptionPlan(BaseModel):
    plan_id: str
    name: str
    description: str
    monthly_price: float
    annual_price: float
    features: SubscriptionFeatures
    popular: bool = False

class SubscriptionPlansResponse(BaseModel):
    current_plan: str
    plans: Dict[str, SubscriptionPlan]

# Schemas for payment processing
class CheckoutSessionRequest(BaseModel):
    subscription_type: str
    billing_cycle: str = "monthly"  # "monthly" or "annual"

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    subscription_type: str
    billing_cycle: str

class VerifySessionRequest(BaseModel):
    session_id: str
    subscription_type: Optional[str] = None

class VerifySessionResponse(BaseModel):
    success: bool
    message: str
    subscription_type: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None

# Schemas for usage tracking
class FormulaUsageResponse(BaseModel):
    formula_count: int
    formula_limit: Union[int, str]
    percentage_used: float
    status: str
    subscription_type: str
    can_create_more: bool

class MessageResponse(BaseModel):
    message: str
class PhoneVerificationRequest(BaseModel):
    phone_number: str

class PhoneVerificationCode(BaseModel):
    phone_number: str
    code: str

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    subscription_type: SubscriptionTypeEnum = SubscriptionTypeEnum.FREE
    needs_subscription: bool = True

class UserCreate(UserBase):
    first_name: str
    last_name: str
    password: str
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    confirm_password: Optional[str] = None
    is_active: Optional[bool] = None
    subscription_type: Optional[SubscriptionTypeEnum] = None
    needs_subscription: Optional[bool] = None

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UserInDB(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    subscription_type: SubscriptionType
    subscription_ends_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class User(UserBase):
    id: int
    first_name: str
    last_name: str
    is_verified: bool = False
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class TokenPayload(BaseModel):
    sub: str
    exp: int

# Currency-related schemas
class CurrencyBase(BaseModel):
    code: str = Field(..., max_length=3, description="3-letter currency code")
    name: str
    symbol: str = Field(..., max_length=5)
    exchange_rate_to_usd: float = Field(..., gt=0, description="Exchange rate to USD")
    is_active: bool = True

class CurrencyCreate(CurrencyBase):
    pass

class Currency(CurrencyBase):
    id: int
    last_updated: datetime
    
    class Config:
        orm_mode = True

# Unit type enum
class UnitType(str, Enum):
    GRAM = "g"
    OUNCE = "oz"
    KILOGRAM = "kg"
    POUND = "lb"
    MILLILITER = "ml"
    LITER = "l"

# Updated Ingredient schemas
class IngredientBase(BaseModel):
    name: str
    inci_name: str
    description: Optional[str] = None
    recommended_max_percentage: Optional[float] = None
    solubility: Optional[str] = None
    phase: Optional[str] = None
    function: Optional[str] = None
    is_premium: bool = False
    is_professional: bool = False
    
    # Cost fields
    cost_per_gram: Optional[float] = None
    cost_per_oz: Optional[float] = None
    purchase_cost: Optional[float] = None
    purchase_quantity: Optional[float] = None
    purchase_unit: Optional[UnitType] = None
    currency: str = "USD"
    supplier_name: Optional[str] = None
    supplier_sku: Optional[str] = None
    shipping_cost: Optional[float] = None

class IngredientCreate(IngredientBase):
    pass

class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    inci_name: Optional[str] = None
    description: Optional[str] = None
    recommended_max_percentage: Optional[float] = None
    solubility: Optional[str] = None
    phase: Optional[str] = None
    function: Optional[str] = None
    is_premium: Optional[bool] = None
    is_professional: Optional[bool] = None
    
    # Cost fields
    cost_per_gram: Optional[float] = None
    cost_per_oz: Optional[float] = None
    purchase_cost: Optional[float] = None
    purchase_quantity: Optional[float] = None
    purchase_unit: Optional[UnitType] = None
    currency: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_sku: Optional[str] = None
    shipping_cost: Optional[float] = None

class IngredientCostUpdate(BaseModel):
    """Specialized schema for updating only cost information"""
    cost_per_gram: Optional[float] = None
    cost_per_oz: Optional[float] = None
    purchase_cost: Optional[float] = None
    purchase_quantity: Optional[float] = None
    purchase_unit: Optional[UnitType] = None
    currency: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_sku: Optional[str] = None
    shipping_cost: Optional[float] = None

class IngredientInDB(IngredientBase):
    id: int
    last_updated_cost: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Ingredient(IngredientInDB):
    pass

# Formula step schemas
class FormulaStepBase(BaseModel):
    description: str
    order: int

class FormulaStepCreate(FormulaStepBase):
    pass

class FormulaStepUpdate(BaseModel):
    description: Optional[str] = None
    order: Optional[int] = None

class FormulaStepInDB(FormulaStepBase):
    id: int
    formula_id: int

    class Config:
        from_attributes = True

class FormulaStep(FormulaStepInDB):
    pass

# Formula ingredient schemas
class FormulaIngredientBase(BaseModel):
    ingredient_id: int
    percentage: float
    order: int

class FormulaIngredientCreate(FormulaIngredientBase):
    pass

class FormulaIngredientWithDetails(FormulaIngredientBase):
    ingredient: Ingredient

# Updated Formula schemas
class FormulaBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    is_public: bool = False
    total_weight: float = 100.0  # Keep for backward compatibility
    batch_size: float = 100.0
    batch_unit: UnitType = UnitType.GRAM
    msds: Optional[str] = None
    sop: Optional[str] = None

class FormulaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    is_public: bool = False
    total_weight: float = 100.0
    batch_size: float = 100.0
    batch_unit: UnitType = UnitType.GRAM
    ingredients: List[FormulaIngredientCreate] = []
    steps: List[FormulaStepCreate] = []
    msds: Optional[str] = None
    sop: Optional[str] = None

class INCIList(BaseModel):
    """Schema for ingredient list formatted according to INCI standards"""
    formula_id: int
    formula_name: str
    inci_list: str
    inci_list_with_allergens: Optional[str] = None  # With allergens highlighted
    ingredients_by_percentage: Optional[List[Dict[str, Any]]] = None  # Detailed breakdown

class FormulaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    is_public: Optional[bool] = None
    total_weight: Optional[float] = None
    batch_size: Optional[float] = None
    batch_unit: Optional[UnitType] = None

class FormulaInDB(FormulaBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FormulaDuplication(BaseModel):
    new_name: Optional[str] = None

class Formula(FormulaInDB):
    ingredients: List[FormulaIngredientWithDetails] = []
    steps: List[FormulaStep] = []
    user: User

class FormulaList(BaseModel):
    id: int
    name: str
    type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_public: bool = False
    total_weight: float = 100.0
    ingredients: Optional[int] = 0
    
    class Config:
        from_attributes = True

class FormulaIngredientUpdate(BaseModel):
    ingredient_id: int
    percentage: float
    order: int

class FormulaIngredientsUpdate(BaseModel):
    ingredients: List[FormulaIngredientUpdate]

class FormulaStepUpdate(BaseModel):
    description: str
    order: int

class FormulaStepsUpdate(BaseModel):
    steps: List[FormulaStepUpdate]

class FormulaDocumentationUpdate(BaseModel):
    msds: Optional[str] = None
    sop: Optional[str] = None

# Cost calculation schemas
class IngredientCostBreakdown(BaseModel):
    """Cost breakdown for a single ingredient in a formula"""
    ingredient_id: int
    ingredient_name: str
    percentage: float
    quantity_needed: float  # in grams
    quantity_unit: str
    cost_per_unit: float
    total_cost: float
    currency: str

class FormulaCostBreakdown(BaseModel):
    """Complete cost breakdown for a formula"""
    formula_id: int
    formula_name: str
    batch_size: float
    batch_unit: str
    ingredient_costs: List[IngredientCostBreakdown]
    total_batch_cost: float
    cost_per_gram: float
    cost_per_oz: float
    currency: str
    calculation_date: datetime
    missing_cost_ingredients: List[str] = []  # Ingredients without cost data

class CostCalculationRequest(BaseModel):
    """Request schema for cost calculations"""
    formula_id: int
    batch_size: Optional[float] = None
    batch_unit: Optional[UnitType] = None
    target_currency: Optional[str] = "USD"

# Cost history schemas
class IngredientCostHistoryCreate(BaseModel):
    ingredient_id: int
    cost_per_gram: float
    currency: str
    purchase_cost: Optional[float] = None
    purchase_quantity: Optional[float] = None
    purchase_unit: Optional[UnitType] = None
    supplier_name: Optional[str] = None

class IngredientCostHistory(BaseModel):
    id: int
    ingredient_id: int
    cost_per_gram: float
    currency: str
    purchase_cost: Optional[float] = None
    purchase_quantity: Optional[float] = None
    purchase_unit: Optional[str] = None
    supplier_name: Optional[str] = None
    recorded_at: datetime
    
    class Config:
        orm_mode = True

# Bulk cost import schema
class BulkCostImport(BaseModel):
    """Schema for importing multiple ingredient costs at once"""
    costs: List[Dict[str, Any]]  # Flexible structure for CSV/Excel imports
    default_currency: str = "USD"
    supplier_name: Optional[str] = None

class BulkCostImportResult(BaseModel):
    """Result of bulk cost import operation"""
    total_processed: int
    successful_updates: int
    failed_updates: int
    errors: List[str]
    updated_ingredients: List[str]

# Notification schemas
class NotificationBase(BaseModel):
    title: str
    message: str
    notification_type: str
    reference_id: Optional[int] = None

class NotificationCreate(NotificationBase):
    pass

class NotificationRead(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

# Notification preference schemas
class NotificationPreferenceBase(BaseModel):
    notification_type: str
    email_enabled: bool
    push_enabled: bool
    sms_enabled: bool

class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool
    push_enabled: bool
    sms_enabled: bool

class NotificationPreferenceRead(NotificationPreferenceBase):
    user_id: int
    
    class Config:
        orm_mode = True

# Response models for notification endpoints
class NotificationResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None

class NotificationPreferencesResponse(BaseModel):
    system: Optional[Dict[str, bool]] = None
    formula: Optional[Dict[str, bool]] = None
    subscription: Optional[Dict[str, bool]] = None
    order: Optional[Dict[str, bool]] = None

# User Profile schemas
class UserProfileBase(BaseModel):
    # Personal Info & Environment
    age: Optional[int] = None
    gender: Optional[str] = None
    is_pregnant: Optional[bool] = None
    fitzpatrick_type: Optional[int] = None
    climate: Optional[str] = None
    
    # Skin Characteristics
    skin_type: Optional[str] = None
    breakout_frequency: Optional[str] = None
    skin_texture: Optional[List[str]] = None
    skin_redness: Optional[str] = None
    end_of_day_skin_feel: Optional[str] = None
    
    # Skin Concerns & Preferences
    skin_concerns: Optional[List[str]] = None
    preferred_textures: Optional[List[str]] = None
    preferred_routine_length: Optional[str] = None
    preferred_product_types: Optional[List[str]] = None
    lifestyle_factors: Optional[List[str]] = None
    sensitivities: Optional[List[str]] = None
    ingredients_to_avoid: Optional[str] = None
    
    # Professional Fields (only used for professional tier)
    brand_name: Optional[str] = None
    development_stage: Optional[str] = None
    product_category: Optional[str] = None
    target_demographic: Optional[str] = None
    sales_channels: Optional[List[str]] = None
    target_texture: Optional[str] = None
    performance_goals: Optional[List[str]] = None
    desired_certifications: Optional[List[str]] = None
    regulatory_requirements: Optional[str] = None
    restricted_ingredients: Optional[str] = None
    preferred_actives: Optional[str] = None
    production_scale: Optional[str] = None
    price_positioning: Optional[str] = None
    competitor_brands: Optional[str] = None
    brand_voice: Optional[str] = None
    product_inspirations: Optional[str] = None

class UserProfileCreate(UserProfileBase):
    pass

class UserProfileUpdate(UserProfileBase):
    pass

class UserProfileResponse(UserProfileBase):
    id: Optional[int] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# UPDATED: New schema for AI Formula Generation - includes pet care and simplified ingredient preferences
class FormulaGenerationRequest(BaseModel):
    product_type: str
    formula_name: Optional[str] = None
    
    # Questionnaire data (all optional as they might come from profile)
    # Personal Info
    age: Optional[int] = None
    gender: Optional[str] = None
    is_pregnant: Optional[bool] = None
    fitzpatrick_type: Optional[int] = None
    climate: Optional[str] = None
    
    # Skin Characteristics
    skin_type: Optional[str] = None
    breakout_frequency: Optional[str] = None
    skin_texture: Optional[List[str]] = None
    skin_redness: Optional[str] = None
    end_of_day_skin_feel: Optional[str] = None
    
    # Skin Concerns & Preferences
    skin_concerns: Optional[List[str]] = None
    preferred_textures: Optional[List[str]] = None
    preferred_routine_length: Optional[str] = None
    preferred_product_types: Optional[List[str]] = None
    lifestyle_factors: Optional[List[str]] = None
    sensitivities: Optional[List[str]] = None
    ingredients_to_avoid: Optional[str] = None
    
    # Ingredient preferences
    preferred_ingredients: Optional[List[int]] = None
    avoided_ingredients: Optional[List[int]] = None
    
    # Professional Fields (only used for professional tier)
    brand_name: Optional[str] = None
    development_stage: Optional[str] = None
    product_category: Optional[str] = None
    target_demographic: Optional[str] = None
    sales_channels: Optional[List[str]] = None
    target_texture: Optional[str] = None
    performance_goals: Optional[List[str]] = None
    desired_certifications: Optional[List[str]] = None
    regulatory_requirements: Optional[str] = None
    restricted_ingredients: Optional[str] = None
    preferred_actives: Optional[str] = None
    production_scale: Optional[str] = None
    price_positioning: Optional[str] = None
    competitor_brands: Optional[str] = None
    brand_voice: Optional[str] = None
    product_inspirations: Optional[str] = None

# NEW: Updated schema for questionnaire-based generation - WITH PET CARE
class QuestionnaireFormulaRequest(BaseModel):
    # Optional purpose field - defaults to 'personal' 
    purpose: Optional[str] = "personal"  # 'personal' or 'brand'
    product_category: str  # 'face_care', 'hair_care', 'body_care', 'pet_care'
    formula_types: List[str]  # ['serum', 'cream', 'pet_shampoo', etc.]
    primary_goals: List[str]  # ['hydrate', 'anti_aging', 'clean', 'soothe_skin', etc.]
    
    # Target user (required for brand, optional for personal)
    target_user: Optional[Dict[str, Any]] = {}
    
    # SIMPLIFIED: Single field instead of multiple ingredient fields
    additional_information: Optional[str] = ""  # Replaces preferred_ingredients_text and avoided_ingredients_text
    
    # Brand and experience
    brand_vision: Optional[str] = ""
    desired_experience: Optional[List[str]] = []
    
    # Optional fields
    packaging_preferences: Optional[str] = ""
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    additional_notes: Optional[str] = ""
    
    # AI name generation flag
    generate_name: Optional[bool] = True