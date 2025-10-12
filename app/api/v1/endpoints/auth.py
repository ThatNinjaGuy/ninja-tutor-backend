"""
Authentication endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ....models.user import (
    UserCreate, UserLogin, UserResponse, Token, UserUpdate,
    PreferencesUpdate, ReadingPreferencesUpdate
)
from ....services.auth_service import AuthService
from ....services.firebase_storage import FirebaseStorageService
from ....core.firebase_config import get_db
from fastapi import UploadFile, File

router = APIRouter()
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Get current user from Firebase ID token"""
    auth_service = AuthService()
    decoded_token = auth_service.verify_firebase_token(credentials.credentials)
    
    if decoded_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    firebase_uid = decoded_token.get("uid")
    if firebase_uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return firebase_uid


@router.post("/sync-user", response_model=UserResponse)
async def sync_user(current_user_id: str = Depends(get_current_user)):
    """Sync Firebase user with app user data"""
    from firebase_admin import auth as firebase_auth
    
    try:
        # Get Firebase user info
        firebase_user = firebase_auth.get_user(current_user_id)
        
        # Sync with Firestore
        auth_service = AuthService()
        user = await auth_service.sync_firebase_user(
            firebase_uid=current_user_id,
            email=firebase_user.email or "",
            name=firebase_user.display_name or "User"
        )
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=getattr(user, 'avatar_url', None),
            created_at=user.created_at,
            preferences=user.preferences,
            reading_preferences=user.reading_preferences,
            progress=user.progress,
            is_active=user.is_active
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing user: {str(e)}"
        )


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
        avatar_url=getattr(user, 'avatar_url', None),
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
        avatar_url=getattr(user, 'avatar_url', None),
        created_at=user.created_at,
        preferences=user.preferences,
        reading_preferences=user.reading_preferences,
        progress=user.progress,
        is_active=user.is_active
    )


@router.put("/preferences")
async def update_preferences(
    preferences_update: PreferencesUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """Update user app preferences"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        current_prefs = user_data.get('preferences', {})
        
        # Update preferences with provided values
        update_dict = preferences_update.dict(exclude_unset=True)
        for key, value in update_dict.items():
            current_prefs[key] = value
        
        # Save back to Firestore
        db.collection('users').document(current_user_id).update({
            'preferences': current_prefs
        })
        
        return {"message": "Preferences updated successfully", "preferences": current_prefs}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating preferences: {str(e)}")


@router.put("/reading-preferences")
async def update_reading_preferences(
    reading_prefs_update: ReadingPreferencesUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """Update user reading preferences"""
    try:
        db = get_db()
        
        # Get user document
        user_doc = db.collection('users').document(current_user_id).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        current_reading_prefs = user_data.get('reading_preferences', {})
        
        # Update preferences with provided values
        update_dict = reading_prefs_update.dict(exclude_unset=True)
        for key, value in update_dict.items():
            current_reading_prefs[key] = value
        
        # Save back to Firestore
        db.collection('users').document(current_user_id).update({
            'reading_preferences': current_reading_prefs
        })
        
        return {"message": "Reading preferences updated successfully", "reading_preferences": current_reading_prefs}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating reading preferences: {str(e)}")


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user)
):
    """Upload user avatar image"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Save file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or 'avatar.jpg')[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Upload to Firebase Storage
            storage_service = FirebaseStorageService()
            avatar_url = await storage_service.upload_avatar(temp_file_path, current_user_id)
            
            # Update user document
            db = get_db()
            db.collection('users').document(current_user_id).update({
                'avatar_url': avatar_url
            })
            
            return {"message": "Avatar uploaded successfully", "avatar_url": avatar_url}
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading avatar: {str(e)}")
