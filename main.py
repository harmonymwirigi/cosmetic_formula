# backend/main.py
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
import time
from app import models, schemas, crud
from app.database import engine, get_db
from app.auth import auth_router, get_current_user
from app.config import settings
from datetime import datetime
import os
# Create database tables
models.Base.metadata.create_all(bind=engine)
# Initialize Notion settings from environment variables
settings.NOTION_API_KEY = os.getenv("NOTION_API_KEY", settings.NOTION_API_KEY)

def format_notion_id(notion_id):
    """Format a Notion ID with correct hyphen positions if needed."""
    if not notion_id:
        return notion_id
    
    # Remove any existing hyphens
    notion_id = notion_id.replace("-", "")
    
    # Check if it's the correct length
    if len(notion_id) != 32:
        return notion_id
    
    # Format with hyphens: 8-4-4-4-12
    return f"{notion_id[0:8]}-{notion_id[8:12]}-{notion_id[12:16]}-{notion_id[16:20]}-{notion_id[20:]}"
settings.NOTION_FORMULAS_DB_ID = os.getenv("NOTION_FORMULAS_DB_ID", settings.NOTION_FORMULAS_DB_ID)
settings.NOTION_DOCS_DB_ID = os.getenv("NOTION_DOCS_DB_ID", settings.NOTION_DOCS_DB_ID)

# Log settings for debugging
print(f"Notion API Key: {'*'*(len(settings.NOTION_API_KEY)-4)}{settings.NOTION_API_KEY[-4:] if settings.NOTION_API_KEY else 'Not set'}")
print(f"Notion Formulas DB ID: {settings.NOTION_FORMULAS_DB_ID or 'Not set'}")
print(f"Notion Docs DB ID: {settings.NOTION_DOCS_DB_ID or 'Not set'}")
app = FastAPI(title="Cosmetic Formula Lab API")

# Add session middleware for OAuth
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    max_age=3600  # Session lifetime in seconds
)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"Incoming request: {request.method} {request.url}")
    print(f"Headers: {request.headers.get('authorization', 'No Auth header')}")
    
    # Try to log the request body for debugging
    try:
        body = await request.body()
        if body:
            body_str = body.decode()
            if len(body_str) < 500:  # Only log if not too large
                print(f"Request body: {body_str}")
    except Exception as e:
        print(f"Could not log request body: {e}")
    
    # Proceed with the request
    start_time = time.time()  # Now this will work correctly
    response = await call_next(request)
    process_time = time.time() - start_time
    
    print(f"Response status: {response.status_code}")
    print(f"Processed in {process_time:.4f} seconds")
    
    return response
# Configure CORS with more permissive 
#Configure CORS with specific origins (not wildcards)
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://192.168.1.1:5173",
    "https://cosmetic-formula-frontend.vercel.app",
    "https://www.beautycrafthq.com",
    "https://beautycrafthq.com",
    "https://cosmetic-formula-git-main-beautycraft.vercel.app",
    "https://cosmetic-formula-frontend-git-main-beautycraft.vercel.app",
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)
# Include authentication router
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
# In main.py, add this to your router inclusion section
try:
    from app.auth_google import oauth_router  # Update this line to use auth_google.py
    app.include_router(oauth_router, prefix="/api/auth", tags=["authentication"])
    print("Successfully registered OAuth router")
except ImportError as e:
    print(f"Warning: OAuth router not found, error: {e}")
except ImportError as e:
    print(f"Warning: OAuth router not found, error: {e}")
# Try to include additional auth endpoints
try:
    from app.api.endpoints import auth as auth_endpoints
    # Make sure to import the router directly from the module
    app.include_router(auth_endpoints.router, prefix="/api", tags=["authentication"])
except ImportError as e:
    print(f"Warning: Auth endpoints not found, skipping... Error: {e}")
try:
    from app.api.endpoints import auth as auth_endpoints
    app.include_router(auth_endpoints.router, prefix="/api/auth", tags=["authentication"])
except ImportError:
    print("Warning: Auth endpoints not found, skipping...")
try:
    from app.api.endpoints import user_profile
    app.include_router(user_profile.router, prefix="/api/user", tags=["user"])
except ImportError:
    print("Warning: User profile endpoints not found, skipping...")
# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the Cosmetic Formula Lab API"}

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}
@app.get("/api/test-connection")
async def test_connection():
    return {"status": "success", "message": "Backend connection successful", "timestamp": datetime.now().isoformat()}
# Add a test endpoint for debugging
@app.get("/api/test")
def test_endpoint():
    return {"message": "API is working", "status": "success"}

# Add a debugging endpoint for CORS
@app.options("/{path:path}")
async def options_route(request: Request, path: str):
    return {"status": "ok"}
try:
    from app.api.endpoints import notion
    app.include_router(notion.router, prefix="/api/notion", tags=["notion"])
except ImportError:
    print("Warning: Notion endpoints not found, skipping...")
# Try to import and include API endpoints
try:
    from app.api.endpoints import formulas
    app.include_router(formulas.router, prefix="/api/formulas", tags=["formulas"])
except ImportError:
    print("Warning: Formulas endpoints not found, skipping...")
try:
    from app.api.endpoints import export
    app.include_router(export.router, prefix="/api/formulas", tags=["export"])
    print("Successfully registered export router")
except ImportError as e:
    print(f"Warning: Export endpoints not found, error: {e}")

try:
    from app.api.endpoints import notifications
    app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
except ImportError:
    print("Warning: Notification endpoints not found, skipping...")
try:
    from app.api.endpoints import knowledge_base
    app.include_router(
            knowledge_base.router,
            prefix="/api/knowledge",
            tags=["knowledge_base"]
        )
except ImportError:
    print("Warning: knowledge base endpoint not found, skipping ...")

try:
    from app.api.endpoints import shop
    app.include_router(
        shop.router,
        prefix="/api/shop",
        tags=["shop"]
    )
except ImportError:
    print("Warning: shop endpoint not found, skipping ...")


try:
    from app.api.endpoints import ingredients
    app.include_router(ingredients.router, prefix="/api/ingredients", tags=["ingredients"])
except ImportError:
    print("Warning: Ingredients endpoints not found, skipping...")

try:
    from app.api.endpoints import users
    app.include_router(users.router, prefix="/api/users", tags=["users"])
except ImportError:
    print("Warning: Users endpoints not found, skipping...")

try:
    from app.api.endpoints import costs
    app.include_router(costs.router, prefix="/api/costs", tags=["costs"])
    print("Successfully registered cost management router")
except ImportError as e:
    print(f"Warning: Cost endpoints not found, error: {e}")

try:
    from app.api.endpoints import ai_formula
    print("Successfully imported AI formula router")
    print(f"Router routes: {[route for route in ai_formula.router.routes]}")
    app.include_router(ai_formula.router, prefix="/api/ai-formula", tags=["ai-formula"])
    print("Successfully registered AI formula router")
except ImportError as e:
    print(f"Warning: AI Formula endpoints not found, error: {e}")

# Include payment endpoints
try:
    from app.api.endpoints import payments
    app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
except ImportError:
    print("Warning: Payment endpoints not found, skipping...")

# For debugging - print all available routes
@app.get("/api/routes", include_in_schema=False)
def get_routes():
    """Get all available API routes - for debugging only"""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name
            })
    return {"routes": routes}
@app.get("/api/auth/test-token")
async def test_token(current_user: models.User = Depends(get_current_user)):
    """Test endpoint to verify token authentication"""
    return {
        "message": "Token is valid",
        "user_id": current_user.id,
        "email": current_user.email
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


app = app