from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, timezone
from typing import Optional
from app.models import StatusEnum


class UserCreate(BaseModel):
    """
    Схема для РЕЄСТРАЦІЇ. 
    """
    username: str = Field(..., min_length=2, max_length=64, examples=["andrii"])
    password: str = Field(..., min_length=6, max_length=128, examples=["secret"])

    @field_validator("username")
    @classmethod
    def username_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be blank")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: str
    password: str


class CommitmentBase(BaseModel):
    """
    Базова схема задачі. 
    """
    title: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4096)
    project: str = Field(..., min_length=1, max_length=128)
    executor_name: str = Field(..., min_length=1, max_length=128)
    deadline: datetime
    status_: StatusEnum = Field(default=StatusEnum.to_check, alias="status")

    @field_validator("title", "project", "executor_name")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be blank")
        return v.strip()

    @field_validator("deadline")
    @classmethod
    def deadline_must_have_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            # Assume UTC when no tz provided
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = ConfigDict(populate_by_name=True)


class CommitmentCreate(CommitmentBase):
    author_id: int = Field(..., gt=0)
    checker_id: int = Field(..., gt=0)


class CommitmentOut(CommitmentBase):
    id: int
    created_at: datetime
    author_id: int
    checker_id: int

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class TextInput(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut