from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from .database import Base

class StatusEnum(enum.Enum):
    to_check = "to check"
    expired = "expired"
    done = "done"
    not_actual = "not actual"
    ideas_backlog = "ideas backlog"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

    commitments_authored = relationship("Commitment", foreign_keys='Commitment.author_id', back_populates="author")
    commitments_to_check = relationship("Commitment", foreign_keys='Commitment.checker_id', back_populates="checker")

class Commitment(Base):
    __tablename__ = "commitments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    project = Column(String, index=True)
    executor_name = Column(String)  # Відповідальний виконавець
    deadline = Column(DateTime, index=True)
    status_ = Column("status", Enum(StatusEnum), default=StatusEnum.to_check) # Використовуємо status_, щоб уникнути тінізації

    author_id = Column(Integer, ForeignKey("users.id"))
    checker_id = Column(Integer, ForeignKey("users.id"))

    author = relationship("User", foreign_keys=[author_id], back_populates="commitments_authored")
    checker = relationship("User", foreign_keys=[checker_id], back_populates="commitments_to_check")