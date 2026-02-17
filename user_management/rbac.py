"""Role-based access control."""
from enum import Enum

from fastapi import Depends, HTTPException, status

from auth.dependencies import get_current_user
from user_management.models import User


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that requires the current user to be an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
