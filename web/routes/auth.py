"""Auth API routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
import logging

from database.connection import get_db
from auth.service import AuthService
from auth.schemas import (
    RegisterRequest, LoginRequest,
    UserResponse, UsersListResponse, TokenResponse, MessageResponse,
    LoginSessionResponse, LoginSessionsListResponse,
)
from auth.dependencies import get_current_user, get_refresh_token_from_cookie
from user_management.models import User
from user_management.rbac import require_admin
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency to get auth service instance."""
    return AuthService(db)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user."""
    if auth_service.get_user_by_email(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = auth_service.create_user(
        email=request.email,
        first_name=request.first_name,
        last_name=request.last_name,
        password=request.password
    )
    logger.info(f"New user registered: {user.email}")
    return user


@router.get("/users", response_model=UsersListResponse)
async def get_all_users(
    limit: int = 100,
    offset: int = 0,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(require_admin)  # P0 FIX: require admin
):
    """Get all users (admin only)."""
    users = auth_service.get_all_users(limit, offset)
    total = auth_service.get_users_count()
    return UsersListResponse(users=users, total=total)


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Login and get tokens."""
    user = auth_service.authenticate_user(login_request.email, login_request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token, raw_refresh_token, _ = auth_service.create_tokens(user)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    auth_service.create_login_session(user, ip_address, user_agent)

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh access token."""
    raw_token = get_refresh_token_from_cookie(request)
    user = auth_service.validate_refresh_token(raw_token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token, new_raw_token, _ = auth_service.rotate_refresh_token(raw_token, user)

    response.set_cookie(
        key="refresh_token",
        value=new_raw_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user)
):
    """Logout and revoke refresh token."""
    try:
        raw_token = get_refresh_token_from_cookie(request)
        auth_service.revoke_refresh_token(raw_token)
    except HTTPException:
        pass

    auth_service.end_login_session(str(current_user.id))

    response.delete_cookie(key="refresh_token", path="/api/auth")
    logger.info(f"User logged out: {current_user.email}")
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return current_user


def _build_session_responses(sessions, fallback_email=None):
    """Convert LoginSession ORM objects to response models."""
    return [
        LoginSessionResponse(
            id=s.id, user_id=s.user_id,
            user_email=(s.user.email if hasattr(s, 'user') and s.user else fallback_email),
            login_at=s.login_at, logout_at=s.logout_at,
            ip_address=s.ip_address, user_agent=s.user_agent, is_active=s.is_active,
        )
        for s in sessions
    ]


@router.get("/sessions", response_model=LoginSessionsListResponse)
async def get_login_sessions(
    limit: int = 50,
    offset: int = 0,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user)
):
    """Get login sessions for the current user."""
    sessions = auth_service.get_user_login_sessions(str(current_user.id), limit, offset)
    return LoginSessionsListResponse(
        sessions=_build_session_responses(sessions, fallback_email=current_user.email),
        total=auth_service.get_total_sessions_count(),
        active_count=auth_service.get_active_sessions_count(),
    )


@router.get("/sessions/all", response_model=LoginSessionsListResponse)
async def get_all_login_sessions(
    limit: int = 100,
    offset: int = 0,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(require_admin)
):
    """Get all login sessions (admin only)."""
    sessions = auth_service.get_all_login_sessions(limit, offset)
    return LoginSessionsListResponse(
        sessions=_build_session_responses(sessions),
        total=auth_service.get_total_sessions_count(),
        active_count=auth_service.get_active_sessions_count(),
    )
