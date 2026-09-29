import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region: str
    favorite_genre_ids: list[int]
    languages: list[str]
    streaming_provider_ids: list[int]
    email_reminders: bool


class PreferencesUpdate(BaseModel):
    region: str | None = Field(default=None, min_length=2, max_length=2)
    favorite_genre_ids: list[int] | None = None
    languages: list[str] | None = None
    streaming_provider_ids: list[int] | None = None
    email_reminders: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    role: str
    preferences: PreferencesOut
