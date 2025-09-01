"""
Authentication endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ....models.user import UserCreate, UserLogin, UserResponse, Token, UserUpdate
from ....services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Get current user from JWT token"""
    auth_service = AuthService()
    payload = auth_service.verify_token(credentials.credentials)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register a new user"""
    auth_service = AuthService()
    user = await auth_service.create_user(user_data)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        preferences=user.preferences,
        reading_preferences=user.reading_preferences,
        progress=user.progress,
        is_active=user.is_active
    )


@router.post("/login", response_model=Token)
async def login(user_login: UserLogin):
    """User login"""
    auth_service = AuthService()
    token = await auth_service.login(user_login.email, user_login.password)
    return token


@router.post("/logout")
async def logout(current_user_id: str = Depends(get_current_user)):
    """User logout (client-side token removal)"""
    return {"message": "Successfully logged out"}


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user_id: str = Depends(get_current_user)):
    """Get current user profile"""
    auth_service = AuthService()
    user = await auth_service.get_user_by_id(current_user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        preferences=user.preferences,
        reading_preferences=user.reading_preferences,
        progress=user.progress,
        is_active=user.is_active
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    user_update: UserUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """Update user profile"""
    auth_service = AuthService()
    user = await auth_service.update_user(current_user_id, user_update)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        preferences=user.preferences,
        reading_preferences=user.reading_preferences,
        progress=user.progress,
        is_active=user.is_active
    )
