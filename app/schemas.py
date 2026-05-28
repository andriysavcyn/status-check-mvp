from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from app.models import StatusEnum

class CommitmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    project: str
    executor_name: str
    deadline: datetime
    status: StatusEnum = Field(default=StatusEnum.to_check, alias="status")

    model_config = ConfigDict(populate_by_name=True)

class CommitmentCreate(CommitmentBase):
    author_id: int
    checker_id: int

class CommitmentOut(CommitmentBase):
    id: int
    created_at: int
    author_id: int
    checker_id: int

    model_config = ConfigDict(from_attributes=True)