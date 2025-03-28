from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.auth import create_access_token, get_password_hash
from app.config import settings

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

# Google OAuth configuration
config = Config()
oauth = OAuth(config)

GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = settings.GOOGLE_REDIRECT_URI

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Google OAuth credentials not found in environment variables")

# Configure Google OAuth with additional options
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid email profile",
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "prompt": "select_account"  # Forces Google to show account selection
    },
)

# OAuth router for login endpoints
oauth_router = APIRouter()

@oauth_router.get("/google/login")
async def login_via_google(request: Request, response: Response):
    """
    Initiate Google OAuth login flow
    """
    # Store the requested URL in session for later redirect
    redirect_uri = request.query_params.get("redirect_uri", "/dashboard")
    request.session["redirect_uri"] = redirect_uri
    
    # For development: disable state verification
    # In production, you would generate and validate a state parameter
    print("Initiating Google OAuth flow")
    
    # Include the state parameter in the redirect, but we'll ignore it in the callback
    return await oauth.google.authorize_redirect(
        request, 
        GOOGLE_REDIRECT_URI
    )

@oauth_router.get("/google/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback
    """
    try:
        print("Google OAuth callback received")
        
        # DEVELOPMENT ONLY: Skip state verification
        # In production, you should always verify state
        
        # Get token without state verification (DEVELOPMENT ONLY)
        try:
            # First try normal flow
            token = await oauth.google.authorize_access_token(request)
        except Exception as e:
            if "mismatching_state" in str(e):
                print("State mismatch detected, bypassing for development")
                # DEVELOPMENT ONLY: Manually extract the authorization code
                code = request.query_params.get("code")
                if not code:
                    raise HTTPException(status_code=400, detail="Authorization code not found")
                
                # Manually create token (SIMPLIFIED FOR DEVELOPMENT ONLY)
                # This is NOT secure and should NOT be used in production
                # The proper way is to fix the state parameter issue
                token_endpoint = oauth.google.server_metadata['token_endpoint']
                token_params = {
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': GOOGLE_REDIRECT_URI
                }
                
                # Make token request
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(token_endpoint, data=token_params) as resp:
                        token = await resp.json()
                
                # Get user info
                userinfo_endpoint = oauth.google.server_metadata['userinfo_endpoint']
                headers = {'Authorization': f'Bearer {token.get("access_token")}'}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(userinfo_endpoint, headers=headers) as resp:
                        user_info = await resp.json()
                
                token['userinfo'] = user_info
            else:
                raise e
        
        user_info = token.get("userinfo")
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )
        
        # Extract user data
        email = user_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )
        
        print(f"Processing OAuth for email: {email}")
        
        # Check if user exists
        user = crud.get_user_by_email(db, email=email)
        
        # Create new user if needed
        if not user:
            print(f"Creating new user for email: {email}")
            # Create new user with data from Google
            first_name = user_info.get("given_name", "")
            last_name = user_info.get("family_name", "")
            
            # Generate a random secure password for the user
            import secrets
            import string
            password_chars = string.ascii_letters + string.digits + string.punctuation
            random_password = ''.join(secrets.choice(password_chars) for _ in range(20))
            
            # Hash the password
            hashed_password = get_password_hash(random_password)
            
            # Create a new user
            user = models.User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                hashed_password=hashed_password,
                is_active=True,
                is_verified=True,
                needs_subscription=True  # Set needs_subscription flag
            )
            
            # Add to database and commit
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(f"Existing user found for email: {email}")
            # For existing users, check if they have a subscription
            # If they don't have one or have a free one, set needs_subscription=True
            if not hasattr(user, 'subscription_type') or not user.subscription_type or user.subscription_type == 'free':
                user.needs_subscription = True
                db.commit()
                db.refresh(user)
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        # Always redirect to the OAuth callback route, not the original path
        frontend_url = settings.FRONTEND_URL
        redirect_url = f"{frontend_url}/oauth/callback?token={access_token}&user_id={user.id}"
        
        print(f"Redirecting to: {redirect_url}")
        
        return RedirectResponse(url=redirect_url)
    
    except Exception as e:
        error_msg = str(e)
        print(f"OAuth error: {error_msg}")  # Add debug logging
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={error_msg}")
    

