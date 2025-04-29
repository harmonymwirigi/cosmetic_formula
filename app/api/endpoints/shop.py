# backend/app/api/endpoints/shop.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime
class OrderCreate(BaseModel):
    shipping_address_id: int
    payment_method: str
    notes: Optional[str] = None
router = APIRouter()

# Pydantic schemas for request/response (add to schemas.py)
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: float
    sale_price: Optional[float] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    stock_quantity: int = 0
    sku: Optional[str] = None
    is_featured: bool = False
    is_active: bool = True

class ProductResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    short_description: Optional[str]
    price: float
    sale_price: Optional[float]
    image_url: Optional[str]
    category_id: Optional[int]
    stock_quantity: int
    sku: Optional[str]
    is_featured: bool
    is_active: bool
    
    class Config:
        from_attributes = True

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductResponse
    
    class Config:
        from_attributes = True
class ShoppingCartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse]
    subtotal: float
    
    class Config:
        from_attributes = True

# Product Endpoints
@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    is_featured: Optional[bool] = None
):
    """Get products with filtering and pagination"""
    query = db.query(models.Product).filter(models.Product.is_active == True)
    
    # Apply filters
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    
    if search:
        query = query.filter(
            models.Product.name.ilike(f"%{search}%") | 
            models.Product.description.ilike(f"%{search}%")
        )
    
    if is_featured is not None:
        query = query.filter(models.Product.is_featured == is_featured)
    
    # Apply sorting
    if sort:
        if sort == "price_asc":
            query = query.order_by(models.Product.price.asc())
        elif sort == "price_desc":
            query = query.order_by(models.Product.price.desc())
        elif sort == "newest":
            query = query.order_by(models.Product.created_at.desc())
        elif sort == "name_asc":
            query = query.order_by(models.Product.name.asc())
    else:
        # Default sort by newest
        query = query.order_by(models.Product.created_at.desc())
    
    # Apply pagination
    products = query.offset(skip).limit(limit).all()
    
    return products

@router.get("/products/{slug}", response_model=ProductResponse)
async def get_product(
    slug: str,
    db: Session = Depends(get_db)
):
    """Get a single product by slug"""
    product = db.query(models.Product).filter(
        models.Product.slug == slug,
        models.Product.is_active == True
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return product

@router.get("/categories", response_model=List[dict])
async def get_product_categories(
    db: Session = Depends(get_db),
    parent_id: Optional[int] = None
):
    """Get all product categories, optionally filtered by parent"""
    query = db.query(models.ProductCategory)
    if parent_id is not None:
        query = query.filter(models.ProductCategory.parent_id == parent_id)
    
    categories = query.all()
    
    # Format response with product counts
    result = []
    for category in categories:
        product_count = db.query(models.Product).filter(
            models.Product.category_id == category.id,
            models.Product.is_active == True
        ).count()
        
        result.append({
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "image_url": category.image_url,
            "parent_id": category.parent_id,
            "product_count": product_count
        })
    
    return result
# Shopping Cart Endpoints
@router.get("/cart", response_model=ShoppingCartResponse)
async def get_cart(
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Get the current user's shopping cart"""
   # Get or create cart
   cart = db.query(models.ShoppingCart).filter(
       models.ShoppingCart.user_id == current_user.id
   ).first()
   
   if not cart:
       cart = models.ShoppingCart(user_id=current_user.id)
       db.add(cart)
       db.commit()
       db.refresh(cart)
   
   # Calculate subtotal
   subtotal = 0.0
   for item in cart.items:
       # Get current product price (in case it changed since adding to cart)
       product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
       if product:
           # Use sale price if available, otherwise regular price
           price = product.sale_price if product.sale_price else product.price
           subtotal += price * item.quantity
   
   # Create response
   response = {
       "id": cart.id,
       "user_id": cart.user_id,
       "items": cart.items,
       "subtotal": round(subtotal, 2)
   }
   
   return response

@router.post("/cart/items", response_model=CartItemResponse)
async def add_to_cart(
   item: CartItemCreate,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Add an item to the shopping cart"""
   # Validate product exists and is active
   product = db.query(models.Product).filter(
       models.Product.id == item.product_id,
       models.Product.is_active == True
   ).first()
   
   if not product:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Product not found or inactive"
       )
   
   # Check stock availability
   if product.stock_quantity < item.quantity:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail=f"Not enough stock available. Only {product.stock_quantity} items remaining."
       )
   
   # Get or create cart
   cart = db.query(models.ShoppingCart).filter(
       models.ShoppingCart.user_id == current_user.id
   ).first()
   
   if not cart:
       cart = models.ShoppingCart(user_id=current_user.id)
       db.add(cart)
       db.commit()
       db.refresh(cart)
   
   # Check if product already in cart
   cart_item = db.query(models.CartItem).filter(
       models.CartItem.cart_id == cart.id,
       models.CartItem.product_id == item.product_id
   ).first()
   
   if cart_item:
       # Update quantity
       cart_item.quantity += item.quantity
       
       # Validate against available stock
       if cart_item.quantity > product.stock_quantity:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail=f"Not enough stock available. Only {product.stock_quantity} items remaining."
           )
   else:
       # Create new cart item
       cart_item = models.CartItem(
           cart_id=cart.id,
           product_id=item.product_id,
           quantity=item.quantity
       )
       db.add(cart_item)
   
   db.commit()
   db.refresh(cart_item)
   
   # Set product reference for the response
   cart_item.product = product
   
   return cart_item

@router.put("/cart/items/{item_id}", response_model=CartItemResponse)
async def update_cart_item(
   item_id: int,
   update_data: CartItemCreate,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Update a cart item quantity"""
   # Get cart
   cart = db.query(models.ShoppingCart).filter(
       models.ShoppingCart.user_id == current_user.id
   ).first()
   
   if not cart:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Shopping cart not found"
       )
   
   # Get cart item
   cart_item = db.query(models.CartItem).filter(
       models.CartItem.id == item_id,
       models.CartItem.cart_id == cart.id
   ).first()
   
   if not cart_item:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Cart item not found"
       )
   
   # Validate product exists and is active
   product = db.query(models.Product).filter(
       models.Product.id == update_data.product_id,
       models.Product.is_active == True
   ).first()
   
   if not product:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Product not found or inactive"
       )
   
   # Check stock availability
   if product.stock_quantity < update_data.quantity:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail=f"Not enough stock available. Only {product.stock_quantity} items remaining."
       )
   
   # Update cart item
   cart_item.quantity = update_data.quantity
   
   # If quantity is 0, remove item from cart
   if cart_item.quantity <= 0:
       db.delete(cart_item)
       db.commit()
       
       return {
           "id": item_id,
           "product_id": update_data.product_id,
           "quantity": 0,
           "product": product
       }
   
   db.commit()
   db.refresh(cart_item)
   
   # Set product reference for the response
   cart_item.product = product
   
   return cart_item

@router.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
   item_id: int,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Remove an item from the shopping cart"""
   # Get cart
   cart = db.query(models.ShoppingCart).filter(
       models.ShoppingCart.user_id == current_user.id
   ).first()
   
   if not cart:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Shopping cart not found"
       )
   
   # Get cart item
   cart_item = db.query(models.CartItem).filter(
       models.CartItem.id == item_id,
       models.CartItem.cart_id == cart.id
   ).first()
   
   if not cart_item:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Cart item not found"
       )
   
   # Remove the item
   db.delete(cart_item)
   db.commit()
   
   return None

# Order Endpoints
@router.post("/orders", response_model=dict)
async def create_order(
   order_data: OrderCreate,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Create a new order from the shopping cart"""
   # Get cart
   cart = db.query(models.ShoppingCart).filter(
       models.ShoppingCart.user_id == current_user.id
   ).first()
   
   if not cart or not cart.items:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Shopping cart is empty"
       )
   
   # Validate shipping address
   shipping_address = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.id == order_data.shipping_address_id,  # Use order_data.shipping_address_id
       models.ShippingAddress.user_id == current_user.id
   ).first()
   
   if not shipping_address:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Shipping address not found"
       )
   
   # Calculate totals
   subtotal = 0.0
   tax_rate = 0.07  # 7% tax rate (this would be configurable)
   shipping_fee = 5.99  # Flat shipping fee (this would be calculated based on address, weight, etc.)
   
   # Validate stock and calculate totals
   order_items = []
   for cart_item in cart.items:
       product = db.query(models.Product).filter(
           models.Product.id == cart_item.product_id,
           models.Product.is_active == True
       ).first()
       
       if not product:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail=f"Product id {cart_item.product_id} is no longer available"
           )
       
       if product.stock_quantity < cart_item.quantity:
           raise HTTPException(
               status_code=status.HTTP_400_BAD_REQUEST,
               detail=f"Not enough stock for {product.name}. Only {product.stock_quantity} available."
           )
       
       # Use sale price if available, otherwise regular price
       price = product.sale_price if product.sale_price else product.price
       line_total = price * cart_item.quantity
       subtotal += line_total
       
       # Create order item (not yet added to DB)
       order_items.append({
           "product_id": product.id,
           "quantity": cart_item.quantity,
           "price": price
       })
   
   # Calculate tax and total
   tax = round(subtotal * tax_rate, 2)
   total_amount = subtotal + tax + shipping_fee
   
   # Create order
   order = models.Order(
       user_id=current_user.id,
       status="pending",
       subtotal=subtotal,
       tax=tax,
       shipping_fee=shipping_fee,
       total_amount=total_amount,
       payment_method=order_data.payment_method,  # Use order_data.payment_method
       shipping_address_id=order_data.shipping_address_id,  # Use order_data.shipping_address_id
       notes=order_data.notes  # Use order_data.notes
   )
   
   db.add(order)
   db.commit()
   db.refresh(order)
   
   # Add order items
   for item_data in order_items:
       order_item = models.OrderItem(
           order_id=order.id,
           product_id=item_data["product_id"],
           quantity=item_data["quantity"],
           price=item_data["price"]
       )
       db.add(order_item)
       
       # Update product stock
       product = db.query(models.Product).filter(models.Product.id == item_data["product_id"]).first()
       product.stock_quantity -= item_data["quantity"]
   
   # Clear the cart
   db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()
   
   db.commit()
   
   # TODO: Process payment (this would integrate with payment gateway)
   # For now, just mark the order as processing
   order.status = "processing"
   db.commit()
   
   # Create a formatted response
   return {
       "id": order.id,
       "status": order.status,
       "total_amount": order.total_amount,
       "message": "Order created successfully"
   }

@router.get("/orders", response_model=List[dict])
async def get_orders(
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user),
   skip: int = 0,
   limit: int = 10
):
   """Get orders for the current user"""
   orders = db.query(models.Order).filter(
       models.Order.user_id == current_user.id
   ).order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()
   
   result = []
   for order in orders:
       # Get order items
       items = []
       for item in order.items:
           product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
           items.append({
               "id": item.id,
               "product_id": item.product_id,
               "product_name": product.name if product else "Unknown Product",
               "quantity": item.quantity,
               "price": item.price
           })
       
       # Format order data
       order_data = {
           "id": order.id,
           "status": order.status,
           "total_amount": order.total_amount,
           "created_at": order.created_at,
           "items": items,
           "tracking_number": order.tracking_number
       }
       
       result.append(order_data)
   
   return result

@router.get("/orders/{order_id}", response_model=dict)
async def get_order(
   order_id: int,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Get order details by ID"""
   order = db.query(models.Order).filter(
       models.Order.id == order_id,
       models.Order.user_id == current_user.id
   ).first()
   
   if not order:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Order not found"
       )
   
   # Get shipping address
   shipping_address = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.id == order.shipping_address_id
   ).first()
   
   # Get order items
   items = []
   for item in order.items:
       product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
       items.append({
           "id": item.id,
           "product_id": item.product_id,
           "product_name": product.name if product else "Unknown Product",
           "product_image": product.image_url if product else None,
           "quantity": item.quantity,
           "price": item.price,
           "total": item.price * item.quantity
       })
   
   # Format complete order data
   order_data = {
       "id": order.id,
       "status": order.status,
       "subtotal": order.subtotal,
       "tax": order.tax,
       "shipping_fee": order.shipping_fee,
       "total_amount": order.total_amount,
       "payment_method": order.payment_method,
       "created_at": order.created_at,
       "updated_at": order.updated_at,
       "tracking_number": order.tracking_number,
       "notes": order.notes,
       "shipping_address": {
           "first_name": shipping_address.first_name,
           "last_name": shipping_address.last_name,
           "address_line1": shipping_address.address_line1,
           "address_line2": shipping_address.address_line2,
           "city": shipping_address.city,
           "state": shipping_address.state,
           "postal_code": shipping_address.postal_code,
           "country": shipping_address.country,
           "phone_number": shipping_address.phone_number
       } if shipping_address else None,
       "items": items
   }
   
   return order_data

# Shipping Address Endpoints
@router.get("/shipping-addresses", response_model=List[dict])
async def get_shipping_addresses(
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Get shipping addresses for the current user"""
   addresses = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.user_id == current_user.id
   ).all()
   
   return addresses

@router.post("/shipping-addresses", response_model=dict)
async def create_shipping_address(
   address_data: dict,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Create a new shipping address"""
   # Set as default if it's the first address
   is_default = not db.query(models.ShippingAddress).filter(
       models.ShippingAddress.user_id == current_user.id
   ).first()
   
   # Create new address
   new_address = models.ShippingAddress(
       user_id=current_user.id,
       first_name=address_data["first_name"],
       last_name=address_data["last_name"],
       address_line1=address_data["address_line1"],
       address_line2=address_data.get("address_line2"),
       city=address_data["city"],
       state=address_data["state"],
       postal_code=address_data["postal_code"],
       country=address_data["country"],
       phone_number=address_data.get("phone_number"),
       is_default=address_data.get("is_default", is_default)
   )
   
   db.add(new_address)
   
   # If this is set as default, unset any other default addresses
   if new_address.is_default:
       db.query(models.ShippingAddress).filter(
           models.ShippingAddress.user_id == current_user.id,
           models.ShippingAddress.id != new_address.id
       ).update({"is_default": False})
   
   db.commit()
   db.refresh(new_address)
   
   # Convert the SQLAlchemy model to a dictionary
   return {
       "id": new_address.id,
       "user_id": new_address.user_id,
       "first_name": new_address.first_name,
       "last_name": new_address.last_name,
       "address_line1": new_address.address_line1,
       "address_line2": new_address.address_line2,
       "city": new_address.city,
       "state": new_address.state,
       "postal_code": new_address.postal_code,
       "country": new_address.country,
       "phone_number": new_address.phone_number,
       "is_default": new_address.is_default
   }

@router.get("/shipping-addresses", response_model=List[dict])
async def get_shipping_addresses(
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Get shipping addresses for the current user"""
   addresses = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.user_id == current_user.id
   ).all()
   
   # Convert SQLAlchemy models to dictionaries
   result = []
   for address in addresses:
       result.append({
           "id": address.id,
           "user_id": address.user_id,
           "first_name": address.first_name,
           "last_name": address.last_name,
           "address_line1": address.address_line1,
           "address_line2": address.address_line2,
           "city": address.city,
           "state": address.state,
           "postal_code": address.postal_code,
           "country": address.country,
           "phone_number": address.phone_number,
           "is_default": address.is_default
       })
   
   return result
@router.put("/shipping-addresses/{address_id}", response_model=dict)
async def update_shipping_address(
   address_id: int,
   address_data: dict,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Update a shipping address"""
   address = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.id == address_id,
       models.ShippingAddress.user_id == current_user.id
   ).first()
   
   if not address:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Shipping address not found"
       )
   
   # Update address fields
   address.first_name = address_data.get("first_name", address.first_name)
   address.last_name = address_data.get("last_name", address.last_name)
   address.address_line1 = address_data.get("address_line1", address.address_line1)
   address.address_line2 = address_data.get("address_line2", address.address_line2)
   address.city = address_data.get("city", address.city)
   address.state = address_data.get("state", address.state)
   address.postal_code = address_data.get("postal_code", address.postal_code)
   address.country = address_data.get("country", address.country)
   address.phone_number = address_data.get("phone_number", address.phone_number)
   
   # Check if setting as default
   if address_data.get("is_default") and not address.is_default:
       address.is_default = True
       # Unset any other default addresses
       db.query(models.ShippingAddress).filter(
           models.ShippingAddress.user_id == current_user.id,
           models.ShippingAddress.id != address.id
       ).update({"is_default": False})
   
   db.commit()
   db.refresh(address)
   
   return address

@router.delete("/shipping-addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipping_address(
   address_id: int,
   db: Session = Depends(get_db),
   current_user: models.User = Depends(get_current_user)
):
   """Delete a shipping address"""
   address = db.query(models.ShippingAddress).filter(
       models.ShippingAddress.id == address_id,
       models.ShippingAddress.user_id == current_user.id
   ).first()
   
   if not address:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Shipping address not found"
       )
   
   # Check if this address is used in any orders
   order_count = db.query(models.Order).filter(
       models.Order.shipping_address_id == address_id
   ).count()
   
   if order_count > 0:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Cannot delete address used in orders"
       )
   
   # If this is the default address, set another address as default
   if address.is_default:
       # Find another address to set as default
       other_address = db.query(models.ShippingAddress).filter(
           models.ShippingAddress.user_id == current_user.id,
           models.ShippingAddress.id != address_id
       ).first()
       
       if other_address:
           other_address.is_default = True
   
   # Delete the address
   db.delete(address)
   db.commit()
   
   return None