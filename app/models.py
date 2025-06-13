# backend/app/models.py
from sqlalchemy.orm import relationship
import enum
from sqlalchemy.sql import func
from .database import Base
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Text, DateTime, Enum, Table, JSON
# Import Pydantic's BaseModel
from pydantic import BaseModel as PydanticBaseModel
from typing import Optional, List
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
    phone_number = Column(String, unique=True, nullable=True)  # New field
    is_phone_verified = Column(Boolean, default=False)  # New field
    phone_verification_code = Column(String, nullable=True)  # New field
    phone_verification_expiry = Column(DateTime, nullable=True)  # New field
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


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Personal Info & Environment
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)  # Female/Male/Non-binary/Prefer not to say
    is_pregnant = Column(Boolean, nullable=True)
    fitzpatrick_type = Column(Integer, nullable=True)  # I-VI
    climate = Column(String, nullable=True)  # Dry/Humid/Cold/Tropical/High altitude/Mixed
    
    # Skin Characteristics
    skin_type = Column(String, nullable=True)  # Oily/Dry/Combination/Normal/Sensitive
    breakout_frequency = Column(String, nullable=True)  # Never/Occasionally/Frequently/Constant
    skin_texture = Column(JSON, nullable=True)  # Array of textures
    skin_redness = Column(String, nullable=True)  # Yes often/Only with certain products/Rarely/Rosacea-prone
    end_of_day_skin_feel = Column(String, nullable=True)  # Greasy/Dry/Balanced/Itchy
    
    # Skin Concerns & Preferences
    skin_concerns = Column(JSON, nullable=True)  # stored as JSON array
    preferred_textures = Column(JSON, nullable=True)  # stored as JSON array
    preferred_routine_length = Column(String, nullable=True)  # Simple/Balanced/Layered
    preferred_product_types = Column(JSON, nullable=True)  # stored as JSON array
    lifestyle_factors = Column(JSON, nullable=True)  # stored as JSON array
    sensitivities = Column(JSON, nullable=True)  # stored as JSON array
    ingredients_to_avoid = Column(Text, nullable=True)  # Free text field
    
    # Professional Fields (only used for professional tier)
    # Business Profile
    brand_name = Column(String, nullable=True)
    development_stage = Column(String, nullable=True)
    product_category = Column(String, nullable=True)
    target_demographic = Column(String, nullable=True)
    sales_channels = Column(JSON, nullable=True)  # stored as JSON array
    # Hair Profile
    hair_type = Column(String, nullable=True)
    hair_concerns = Column(JSON, nullable=True)
    brand_info = Column(JSON, nullable=True)
    # Product & Performance
    target_texture = Column(String, nullable=True)
    performance_goals = Column(JSON, nullable=True)  # stored as JSON array
    desired_certifications = Column(JSON, nullable=True)  # stored as JSON array
    
    # Compliance & Formulation
    regulatory_requirements = Column(String, nullable=True)
    restricted_ingredients = Column(Text, nullable=True)
    preferred_actives = Column(Text, nullable=True)
    production_scale = Column(String, nullable=True)
    
    # Branding & Positioning
    price_positioning = Column(String, nullable=True)
    competitor_brands = Column(Text, nullable=True)
    brand_voice = Column(String, nullable=True)
    product_inspirations = Column(Text, nullable=True)
    
    # Standard metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="profile")

# Add this relation to your User model
# If you already have a User model defined, you need to add this line at the end of the file
User.profile = relationship("UserProfile", back_populates="user", uselist=False)
class Formula(Base):
    __tablename__ = "formulas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False)  # e.g., "Serum", "Moisturizer", etc.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)

    # UPDATED BATCH SIZE FIELDS
    total_weight = Column(Float, default=100.0)  # Keep for backward compatibility
    batch_size = Column(Float, default=100.0)    # Preferred batch size
    batch_unit = Column(String, default='g')     # Unit: 'g', 'oz', 'kg', 'lb'
    total_weight = Column(Float, default=100.0)  # Total weight in grams
    msds = Column(Text, nullable=True)  # Material Safety Data Sheet
    sop = Column(Text, nullable=True)  # Standard Operating Procedure
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

    cost_per_gram = Column(Float, nullable=True)  # Standardized cost per gram in USD
    cost_per_oz = Column(Float, nullable=True)   # Standardized cost per ounce in USD
    purchase_cost = Column(Float, nullable=True)  # Total cost paid for purchase
    purchase_quantity = Column(Float, nullable=True)  # Quantity purchased
    purchase_unit = Column(String, nullable=True)  # Unit: 'g', 'oz', 'kg', 'lb', 'ml', 'l'
    currency = Column(String, default='USD')  # Currency code
    supplier_name = Column(String, nullable=True)  # Supplier information
    supplier_sku = Column(String, nullable=True)  # Supplier SKU/product code
    last_updated_cost = Column(DateTime(timezone=True), nullable=True)
    shipping_cost = Column(Float, nullable=True)  # Additional shipping cost for this item
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# NEW MODEL for Currency Management
class Currency(Base):
    __tablename__ = "currencies"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), unique=True, nullable=False, index=True)  # USD, EUR, GBP, etc.
    name = Column(String, nullable=False)  # US Dollar, Euro, British Pound
    symbol = Column(String(5), nullable=False)  # $, €, £
    exchange_rate_to_usd = Column(Float, nullable=False)  # Rate to convert to USD
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# NEW MODEL for Cost History (optional - for tracking cost changes)
class IngredientCostHistory(Base):
    __tablename__ = "ingredient_cost_history"
    
    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    cost_per_gram = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    purchase_cost = Column(Float, nullable=True)
    purchase_quantity = Column(Float, nullable=True)
    purchase_unit = Column(String, nullable=True)
    supplier_name = Column(String, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    ingredient = relationship("Ingredient", backref="cost_history")

class FormulaStep(Base):
    __tablename__ = "formula_steps"

    id = Column(Integer, primary_key=True, index=True)
    formula_id = Column(Integer, ForeignKey("formulas.id"), nullable=False)
    description = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)
    
    # Relationship
    formula = relationship("Formula", back_populates="steps")

# Add to models.py
class ContentCategory(Base):
    __tablename__ = "content_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("content_categories.id"), nullable=True)
    is_premium = Column(Boolean, default=False)
    is_professional = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Self-referential relationship for hierarchical categories
    parent = relationship("ContentCategory", remote_side=[id], backref="subcategories")
    articles = relationship("KnowledgeArticle", back_populates="category")

class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    content = Column(Text, nullable=False)
    excerpt = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("content_categories.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    featured_image = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False)
    is_professional = Column(Boolean, default=False)
    is_published = Column(Boolean, default=True)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("ContentCategory", back_populates="articles")
    author = relationship("User")
    tags = relationship("ArticleTag", secondary="article_tags", back_populates="articles")
    comments = relationship("ArticleComment", back_populates="article")
    resources = relationship("ArticleResource", back_populates="article")

class ArticleTag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    
    # Relationship
    articles = relationship("KnowledgeArticle", secondary="article_tags", back_populates="tags")

class ArticleTags(Base):
    __tablename__ = "article_tags"
    
    article_id = Column(Integer, ForeignKey("knowledge_articles.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

class ArticleComment(Base):
    __tablename__ = "article_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("knowledge_articles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    article = relationship("KnowledgeArticle", back_populates="comments")
    user = relationship("User")

class ArticleResource(Base):
    __tablename__ = "article_resources"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("knowledge_articles.id"), nullable=False)
    title = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)  # "video", "pdf", "link", etc.
    url = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationship
    article = relationship("KnowledgeArticle", back_populates="resources")

class Tutorial(Base):
    __tablename__ = "tutorials"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_premium = Column(Boolean, default=False)
    is_professional = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    steps = relationship("TutorialStep", back_populates="tutorial", order_by="TutorialStep.order")
    completions = relationship("UserTutorialProgress", back_populates="tutorial")

class TutorialStep(Base):
    __tablename__ = "tutorial_steps"
    
    id = Column(Integer, primary_key=True, index=True)
    tutorial_id = Column(Integer, ForeignKey("tutorials.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)
    
    # Relationship
    tutorial = relationship("Tutorial", back_populates="steps")

class UserTutorialProgress(Base):
    __tablename__ = "user_tutorial_progress"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    tutorial_id = Column(Integer, ForeignKey("tutorials.id"), primary_key=True)
    current_step = Column(Integer, default=1)
    is_completed = Column(Boolean, default=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tutorial = relationship("Tutorial", back_populates="completions")
    user = relationship("User")

# Add to models.py
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    short_description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    sale_price = Column(Float, nullable=True)
    image_url = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    stock_quantity = Column(Integer, default=0)
    sku = Column(String, nullable=True)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("ProductCategory", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    parent_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    
    # Self-referential relationship
    parent = relationship("ProductCategory", remote_side=[id], backref="subcategories")
    # Products in this category
    products = relationship("Product", back_populates="category")

class ShoppingCart(Base):
    __tablename__ = "shopping_carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("shopping_carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    
    # Relationships
    cart = relationship("ShoppingCart", back_populates="items")
    product = relationship("Product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending, processing, shipped, delivered, cancelled
    total_amount = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False, default=0.0)
    shipping_fee = Column(Float, nullable=False, default=0.0)
    payment_method = Column(String, nullable=True)  # credit_card, paypal, etc.
    payment_id = Column(String, nullable=True)  # Payment provider transaction ID
    shipping_address_id = Column(Integer, ForeignKey("shipping_addresses.id"), nullable=True)
    tracking_number = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    items = relationship("OrderItem", back_populates="order")
    shipping_address = relationship("ShippingAddress")



class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)  # Price at time of purchase
    
    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

class ShippingAddress(Base):
    __tablename__ = "shipping_addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    address_line1 = Column(String, nullable=False)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    
    # Relationship
    user = relationship("User")

class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, unique=True)
    quantity = Column(Integer, default=0)
    reserved_quantity = Column(Integer, default=0)  # Reserved for pending orders
    reorder_level = Column(Integer, default=5)  # Level at which to reorder
    last_restock_date = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    product = relationship("Product")

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationship
    products = relationship("SupplierProduct", back_populates="supplier")

class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    supplier_sku = Column(String, nullable=True)
    cost_price = Column(Float, nullable=False)
    lead_time_days = Column(Integer, nullable=True)  # Typical lead time in days
    minimum_order_quantity = Column(Integer, default=1)
    is_preferred_supplier = Column(Boolean, default=False)
    
    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    product = relationship("Product")

# Add to models.py
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)  # 'system', 'order', 'formula', 'subscription', etc.
    reference_id = Column(Integer, nullable=True)  # ID of the related object (order, formula, etc.)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    notification_type = Column(String, primary_key=True)  # 'system', 'order', 'formula', 'subscription', etc.
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)
    push_enabled = Column(Boolean, default=True)
    
    # Relationship
    user = relationship("User")

class NotionIntegration(Base):
    __tablename__ = "notion_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(String, nullable=False)
    workspace_id = Column(String, nullable=True)
    formulas_db_id = Column(String, nullable=True)
    docs_db_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="notion_integration")

# Add this relationship to User model
User.notion_integration = relationship("NotionIntegration", back_populates="user", uselist=False)

class NotionSync(Base):
    __tablename__ = "notion_syncs"

    id = Column(Integer, primary_key=True, index=True)
    formula_id = Column(Integer, ForeignKey("formulas.id"), nullable=False)
    notion_page_id = Column(String, nullable=False)
    last_synced = Column(DateTime(timezone=True), nullable=False)
    
    # Relationship
    formula = relationship("Formula", back_populates="notion_sync")

# Add this relationship to Formula model
Formula.notion_sync = relationship("NotionSync", back_populates="formula", uselist=False)