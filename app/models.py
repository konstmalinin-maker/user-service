"""User API: строгий контракт и валидация входа."""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.common_models import StrictModel


class UserInput(StrictModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).casefold()


class User(StrictModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime
