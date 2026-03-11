"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth import AuthService

router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: DbSession):
    """Register a new user."""
    auth_service = AuthService(db)

    # Check if user already exists
    existing_user = await auth_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await auth_service.create_user(user_data)
    return user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: DbSession):
    """Login and get access tokens."""
    auth_service = AuthService(db)

    user = await auth_service.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_service.create_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    db: DbSession,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)
    token_data = auth_service.decode_token(credentials.credentials)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type, expected refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_user_by_id(token_data.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth_service.create_tokens(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    return current_user
