"""Auth request and response schemas."""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
import uuid


# --- Requests ---

class RegisterRequest(BaseModel):
    """Request body for user registration."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Request body for user login."""
    email: EmailStr
    password: str


# --- Responses ---

class UserResponse(BaseModel):
    """Response body for user data."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str = "user"
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsersListResponse(BaseModel):
    """Response body for list of users."""
    users: list[UserResponse]
    total: int


class TokenResponse(BaseModel):
    """Response body for authentication tokens."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class MessageResponse(BaseModel):
    """Response body for simple messages."""
    message: str


class LoginSessionResponse(BaseModel):
    """Response body for login session data."""
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: Optional[str] = None
    login_at: datetime
    logout_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class LoginSessionsListResponse(BaseModel):
    """Response body for list of login sessions."""
    sessions: list[LoginSessionResponse]
    total: int
    active_count: int
