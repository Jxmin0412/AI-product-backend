"""Authentication service — business logic and DB operations."""
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from user_management.models import User, RefreshToken, LoginSession
from auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)


class AuthService:
    """Service class for authentication operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, email: str, first_name: str, last_name: str, password: str) -> User:
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hash_password(password)
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        return self.db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    def get_users_count(self) -> int:
        return self.db.query(User).count()

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    def create_tokens(self, user: User) -> Tuple[str, str, datetime]:
        """Create access and refresh tokens. Returns: (access_token, raw_refresh_token, expires_at)"""
        access_token = create_access_token(str(user.id))
        raw_refresh_token, token_hash, expires_at = create_refresh_token(str(user.id))

        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(refresh_token_record)
        user.last_login = datetime.now(timezone.utc)
        self.db.commit()

        return access_token, raw_refresh_token, expires_at

    def validate_refresh_token(self, raw_token: str) -> Optional[User]:
        token_hash = hash_refresh_token(raw_token)
        refresh_record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        ).first()

        if not refresh_record:
            return None

        user = self.get_user_by_id(str(refresh_record.user_id))
        if not user or not user.is_active:
            return None
        return user

    def rotate_refresh_token(self, old_raw_token: str, user: User) -> Tuple[str, str, datetime]:
        old_token_hash = hash_refresh_token(old_raw_token)
        old_record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == old_token_hash
        ).first()
        if old_record:
            old_record.revoked = True

        access_token = create_access_token(str(user.id))
        raw_refresh_token, token_hash, expires_at = create_refresh_token(str(user.id))

        new_refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(new_refresh_record)
        self.db.commit()

        return access_token, raw_refresh_token, expires_at

    def revoke_refresh_token(self, raw_token: str) -> bool:
        token_hash = hash_refresh_token(raw_token)
        refresh_record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if refresh_record:
            refresh_record.revoked = True
            self.db.commit()
            return True
        return False

    # Login Session Methods
    def create_login_session(self, user: User, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> LoginSession:
        session = LoginSession(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def end_login_session(self, user_id: str) -> None:
        self.db.query(LoginSession).filter(
            LoginSession.user_id == user_id,
            LoginSession.is_active == True
        ).update({
            "is_active": False,
            "logout_at": datetime.now(timezone.utc)
        })
        self.db.commit()

    def get_user_login_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[LoginSession]:
        return self.db.query(LoginSession).filter(
            LoginSession.user_id == user_id
        ).order_by(LoginSession.login_at.desc()).offset(offset).limit(limit).all()

    def get_all_login_sessions(self, limit: int = 100, offset: int = 0) -> List[LoginSession]:
        return self.db.query(LoginSession).order_by(
            LoginSession.login_at.desc()
        ).offset(offset).limit(limit).all()

    def get_active_sessions_count(self) -> int:
        return self.db.query(LoginSession).filter(LoginSession.is_active == True).count()

    def get_total_sessions_count(self) -> int:
        return self.db.query(LoginSession).count()
