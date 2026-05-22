"""Pydantic schemas for user CRUD and credentials endpoints."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.user


class UserCreate(UserBase):
    """Admin-side create — password is auto-generated and emailed/printed."""

    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdate(BaseModel):
    is_active: bool | None = None
    role: UserRole | None = None
    # Admin-only: assign / move / unaffiliate. Use the explicit
    # ``set_university`` field rather than relying on a ``UUID | None`` value
    # because Pydantic's exclude_unset can't tell "set to null" from "omitted".
    set_university: bool = False
    university_id: UUID | None = None


class UserSelfUpdate(BaseModel):
    email: EmailStr | None = None
    backup_email: EmailStr | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    backup_email: EmailStr | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None
    force_password_change: bool
    has_google_key: bool = False
    has_engine_id: bool = False
    has_webhook_key: bool = False
    university_id: UUID | None = None
    university_name: str | None = None


class AdminCreateUserResponse(BaseModel):
    user: UserOut
    initial_password: str = Field(
        description="Generated initial password — shown ONCE; user must change on first login."
    )
    email_sent: bool = False


class DuplicateUserRequest(BaseModel):
    email: EmailStr


class CredentialsUpdate(BaseModel):
    google_api_key: str = Field(min_length=1)
    search_engine_id: str = Field(min_length=1)


class CredentialsStatus(BaseModel):
    has_google_key: bool
    has_engine_id: bool


class WebhookKeyResponse(BaseModel):
    api_key: str = Field(description="Raw key — shown ONCE. Store immediately.")
