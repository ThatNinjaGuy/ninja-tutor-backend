"""
Authentication and user management service
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status

from ..core.config import settings
from ..core.firebase_config import get_db
from ..models.user import User, UserCreate, UserUpdate, UserResponse, Token


class AuthService:
    """Service for user authentication and management"""
    
    def __init__(self):
        self.db = get_db()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Create user
            user_id = str(uuid.uuid4())
            password_hash = self.get_password_hash(user_data.password)
            
            user = User(
                id=user_id,
                email=user_data.email,
                name=user_data.name,
                password_hash=password_hash,
                created_at=datetime.now()
            )
            
            # Save to Firestore
            user_dict = user.dict()
            user_dict['created_at'] = user.created_at
            user_dict['preferences'] = user.preferences.dict()
            user_dict['reading_preferences'] = user.reading_preferences.dict()
            user_dict['progress'] = user.progress.dict()
            
            self.db.collection('users').document(user_id).set(user_dict)
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user: {str(e)}"
            )
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user login"""
        try:
            user = await self.get_user_by_email(email)
            if not user:
                return None
            
            if not self.verify_password(password, user.password_hash):
                return None
            
            return user
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error authenticating user: {str(e)}"
            )
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            users_ref = self.db.collection('users')
            query = users_ref.where('email', '==', email).limit(1)
            docs = query.stream()
            
            for doc in docs:
                user_data = doc.to_dict()
                user_data['id'] = doc.id
                return User(**user_data)
            
            return None
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching user: {str(e)}"
            )
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            doc = self.db.collection('users').document(user_id).get()
            
            if not doc.exists:
                return None
            
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return User(**user_data)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching user: {str(e)}"
            )
    
    async def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """Update user information"""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return None
            
            # Update fields
            update_data = {}
            if user_update.name is not None:
                update_data['name'] = user_update.name
            if user_update.preferences is not None:
                update_data['preferences'] = user_update.preferences.dict()
            if user_update.reading_preferences is not None:
                update_data['reading_preferences'] = user_update.reading_preferences.dict()
            
            update_data['updated_at'] = datetime.now()
            
            # Update in Firestore
            self.db.collection('users').document(user_id).update(update_data)
            
            # Return updated user
            return await self.get_user_by_id(user_id)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating user: {str(e)}"
            )
    
    async def login(self, email: str, password: str) -> Token:
        """User login"""
        user = await self.authenticate_user(email, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = self.create_access_token(data={"sub": user.id, "email": user.email})
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
