# backend/app/auth.py
from datetime import datetime, timedelta
from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError
from sqlalchemy.orm import Session

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from . import crud, models, schemas
from .database import get_db
from .config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Custom OAuth2 bearers to support query parameter tokens and optional authentication
class OAuth2PasswordBearerWithQuery(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # First try to get the token from the Authorization header
        authorization: str = request.headers.get("Authorization")
        scheme, param = "", ""
        if authorization:
            try:
                scheme, param = authorization.split()
                if scheme.lower() == "bearer":
                    return param
            except ValueError:
                pass
        
        # If not in header, try query parameters
        token = request.query_params.get("token")
        if token:
            return token
            
        # If not found, use the parent class method which will raise an exception
        return await super().__call__(request)

class OAuth2PasswordBearerOptional(OAuth2PasswordBearerWithQuery):
    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None

# OAuth2 schemes for token authentication
oauth2_scheme = OAuth2PasswordBearerWithQuery(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearerOptional(tokenUrl="/api/auth/login")

# Router for authentication endpoints
auth_router = APIRouter()

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        token_data = schemas.TokenPayload(sub=user_id, exp=payload.get("exp"))
    except (JWTError, ValidationError):
        raise credentials_exception
    
    user = crud.get_user(db, user_id=int(token_data.sub))
    
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_user_optional(
    token: str = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Get the current user if a valid token is provided, otherwise return None.
    This is useful for endpoints that can be accessed both authenticated and anonymously.
    """
    if not token:
        return None
        
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None

# Authentication endpoints
@auth_router.post("/register", response_model=schemas.User)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if user with given email exists
    db_user = crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with hashed password
    hashed_password = get_password_hash(user_in.password)
    return crud.create_user(
        db=db, 
        user=schemas.UserCreate(
            email=user_in.email,
            password=hashed_password,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            confirm_password=hashed_password  # Not needed but required by schema
        )
    )

@auth_router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: schemas.UserLogin, 
    db: Session = Depends(get_db)
):
    # Authenticate user
    user = crud.get_user_by_email(db, email=form_data.email)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES if form_data.remember_me else 60
    )
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    # Return token and user data
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@auth_router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    Get current user data
    """
    # Add debugging logs
    logger.info(f"Auth/me endpoint called for user ID: {current_user.id}")
    
    # Return the current user immediately instead of doing any additional queries
    return current_user