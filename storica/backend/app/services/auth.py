"""Authentication service."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate, Token, TokenPayload

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(user_id: int) -> str:
        """Create an access token."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        payload = {"sub": str(user_id), "exp": expire, "type": "access"}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """Create a refresh token."""
        expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> Optional[TokenPayload]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )
            return TokenPayload(
                sub=int(payload["sub"]),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                type=payload.get("type", "access"),
            )
        except JWTError:
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            password_hash=self.hash_password(user_data.password),
            full_name=user_data.full_name,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user."""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for a user."""
        return Token(
            access_token=self.create_access_token(user.id),
            refresh_token=self.create_refresh_token(user.id),
        )
