# backend/app/models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime, Enum, Table
from sqlalchemy.orm import relationship
import enum
from sqlalchemy.sql import func
from .database import Base
import uuid
from datetime import datetime
# Many-to-many relationship between formulas and ingredients
formula_ingredients = Table(
    "formula_ingredients",
    Base.metadata,
    Column("formula_id", Integer, ForeignKey("formulas.id"), primary_key=True),
    Column("ingredient_id", Integer, ForeignKey("ingredients.id"), primary_key=True),
    Column("percentage", Float, nullable=False),
    Column("order", Integer, nullable=False),
)

class SubscriptionType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    subscription_type = Column(Enum(SubscriptionType), default=SubscriptionType.FREE)
    needs_subscription = Column(Boolean, default=True)
    subscription_id = Column(String, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    formulas = relationship("Formula", back_populates="user")

class Formula(Base):
    __tablename__ = "formulas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False)  # e.g., "Serum", "Moisturizer", etc.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)
    total_weight = Column(Float, default=100.0)  # Total weight in grams
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="formulas")
    ingredients = relationship(
        "Ingredient", 
        secondary=formula_ingredients, 
        backref="formulas"
    )
    steps = relationship("FormulaStep", back_populates="formula", order_by="FormulaStep.order")

class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    inci_name = Column(String, nullable=False, index=True)  # International Nomenclature of Cosmetic Ingredients
    description = Column(Text, nullable=True)
    recommended_max_percentage = Column(Float, nullable=True)
    solubility = Column(String, nullable=True)  # e.g., "Water-soluble", "Oil-soluble"
    phase = Column(String, nullable=True)  # e.g., "Water phase", "Oil phase", "Cool down phase"
    function = Column(String, nullable=True)  # e.g., "Emollient", "Humectant", "Preservative"
    is_premium = Column(Boolean, default=False)
    is_professional = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FormulaStep(Base):
    __tablename__ = "formula_steps"

    id = Column(Integer, primary_key=True, index=True)
    formula_id = Column(Integer, ForeignKey("formulas.id"), nullable=False)
    description = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)
    
    # Relationship
    formula = relationship("Formula", back_populates="steps")