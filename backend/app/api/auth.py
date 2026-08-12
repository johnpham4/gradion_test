from fastapi import APIRouter, HTTPException, status, Response, Request
from pydantic import BaseModel
from typing import Optional
from app.models.user import UserCreate, UserResponse
from app.repositories.storage import StorageRepository
import secrets

router = APIRouter()
storage = StorageRepository()


class SignInRequest(BaseModel):
    name: str
    email: str


class SignInResponse(BaseModel):
    user: UserResponse


# In-memory session storage (simple approach for assessment)
# In production, use proper session management with Redis/database
sessions: dict = {}  # session_token -> email


@router.post("/auth/sign-in", response_model=SignInResponse)
async def sign_in(request: SignInRequest, response: Response):
    """Sign in or create user with email + name"""
    email = request.email.lower().strip()
    name = request.name.strip()
    
    if not email or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and name are required"
        )
    
    if "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    # Get or create user
    user = storage.get_user(email)
    if user:
        # Update name if provided
        if name and user.get("name") != name:
            user["name"] = name
            storage.update_user(email, user)
    else:
        # Create new user
        user = storage.create_user(email, name)
    
    # Create session token
    session_token = secrets.token_urlsafe(32)
    sessions[session_token] = email
    
    # Set session cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    return SignInResponse(
        user=UserResponse(**user)
    )


@router.post("/auth/sign-out")
async def sign_out(response: Response, request: Request):
    """Sign out user"""
    # Get session token from cookie
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No session token provided"
        )
    
    # Remove session
    if session_token in sessions:
        del sessions[session_token]
    
    # Clear cookie
    response.delete_cookie(key="session_token")
    
    return {"message": "Signed out successfully"}


def get_current_user_email(session_token: Optional[str] = None) -> Optional[str]:
    """Get current user email from session token"""
    if not session_token:
        return None
    
    return sessions.get(session_token)