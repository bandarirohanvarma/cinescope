from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import SessionDep
from app.models import User, UserPreferences
from app.schemas.auth import (
    PreferencesUpdate,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(tags=["auth"])


def tokens_for(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


async def load_user(session: SessionDep, **where) -> User | None:
    query = (
        select(User)
        .options(selectinload(User.preferences))
        .filter_by(**where)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(query)).scalar_one_or_none()


@router.post("/auth/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: SessionDep) -> TokenPair:
    email = body.email.lower()
    taken = await session.scalar(select(func.count()).select_from(User).where(User.email == email))
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        preferences=UserPreferences(),
    )
    session.add(user)
    await session.commit()
    return tokens_for(user)


@router.post("/auth/login", response_model=TokenPair)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> TokenPair:
    """OAuth2 password flow: `username` is the email."""
    user = await load_user(session, email=form.username.lower())
    valid = user and user.hashed_password and verify_password(form.password, user.hashed_password)
    if not valid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return tokens_for(user)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenPair:
    user_id = decode_token(body.refresh_token, "refresh")
    user = await session.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    return tokens_for(user)


@router.get("/users/me", response_model=UserOut)
async def me(user: CurrentUser, session: SessionDep) -> User:
    return await load_user(session, id=user.id)


@router.patch("/users/me/preferences", response_model=UserOut)
async def update_preferences(
    body: PreferencesUpdate, user: CurrentUser, session: SessionDep
) -> User:
    full = await load_user(session, id=user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(full.preferences, field, value.upper() if field == "region" else value)
    await session.commit()
    return await load_user(session, id=user.id)
