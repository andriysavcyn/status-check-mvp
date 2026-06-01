import enum
import logging
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship, validates
from .database import Base

logger = logging.getLogger(__name__)


class StatusEnum(str, enum.Enum):
    """
    Перелік дозволених статусів. 
    """
    to_check = "to check"
    expired = "expired"
    done = "done"
    not_actual = "not actual"
    ideas_backlog = "ideas backlog"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)

    commitments_authored = relationship(
        "Commitment", foreign_keys="Commitment.author_id", back_populates="author"
    )
    commitments_to_check = relationship(
        "Commitment", foreign_keys="Commitment.checker_id", back_populates="checker"
    )

    @validates("username")
    def validate_username(self, key, value):
        """
        Захист на рівні бази даних: не дозволяємо створювати користувачів з порожнім 
        іменем або іменем, яке складається лише з пробілів.
        """
        if not value or not value.strip():
            raise ValueError("Username cannot be empty")
        if len(value.strip()) < 2:
            raise ValueError("Username must be at least 2 characters")
        return value.strip()

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r}>"


class Commitment(Base):
    __tablename__ = "commitments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    project = Column(String(128), index=True, nullable=False)
    executor_name = Column(String(128), nullable=False)
    deadline = Column(DateTime, index=True, nullable=False)
    status_ = Column(
        "status",
        Enum(StatusEnum),
        default=StatusEnum.to_check,
        nullable=False,
    )
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    checker_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    author = relationship(
        "User", foreign_keys=[author_id], back_populates="commitments_authored"
    )
    checker = relationship(
        "User", foreign_keys=[checker_id], back_populates="commitments_to_check"
    )

    @validates("title")
    def validate_title(self, key, value):
        if not value or not value.strip():
            raise ValueError("Title cannot be empty")
        return value.strip()

    @validates("project")
    def validate_project(self, key, value):
        if not value or not value.strip():
            raise ValueError("Project cannot be empty")
        return value.strip()

    @validates("executor_name")
    def validate_executor(self, key, value):
        if not value or not value.strip():
            raise ValueError("Executor name cannot be empty")
        return value.strip()

    def __repr__(self):
        return f"<Commitment id={self.id} title={self.title!r} status={self.status_}>"
