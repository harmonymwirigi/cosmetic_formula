# backend/app/schemas.py
from pydantic import BaseModel, EmailStr, validator, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enum for subscription types
class SubscriptionType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"
class SubscriptionUpdate(BaseModel):
    subscription_type: str
# User schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str

class UserCreate(UserBase):
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

class User(UserInDB):
    pass

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class TokenPayload(BaseModel):
    sub: str
    exp: int

# Ingredient schemas
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

class IngredientInDB(IngredientBase):
    id: int
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

# Formula schemas
class FormulaBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    is_public: bool = False
    total_weight: float = 100.0

class FormulaCreate(FormulaBase):
    ingredients: List[FormulaIngredientCreate]
    steps: List[FormulaStepCreate]

class FormulaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    is_public: Optional[bool] = None
    total_weight: Optional[float] = None

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
        from_attributes = True

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
        from_attributes = True