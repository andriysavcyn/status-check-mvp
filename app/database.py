import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./status_check.db")

try:
    connect_args = (
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    )
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        pass
    logger.info("Database connected: %s", DATABASE_URL)
except SQLAlchemyError as exc:
    logger.critical("Cannot connect to database: %s", exc)
    raise RuntimeError(f"Database init failed: {exc}") from exc

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Генератор сесії бази даних для FastAPI (Dependency).
    Відкриває з'єднання на початку запиту і гарантовано закриває в кінці.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        logger.error("DB session error, rolling back: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()