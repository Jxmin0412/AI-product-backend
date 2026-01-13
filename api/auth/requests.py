"""Auth API request body schemas."""
from pydantic import BaseModel, EmailStr, Field


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


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
