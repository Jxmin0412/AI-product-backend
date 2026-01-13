"""Auth API response body schemas."""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid


class UserResponse(BaseModel):
    """Response body for user data."""
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
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
