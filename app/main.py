import os
import json
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError
from app import models, schemas, database
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

load_dotenv()
XAI_API_KEY = os.getenv("GROQ_API_KEY")
ai_client: Optional[OpenAI] = None

try:
    ai_client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.groq.com/openai/v1")
    logger.info("AI client initialised (Groq)")
except Exception as exc:
    logger.warning(
        "AI client could not be initialised: %s. Smart-add will be unavailable.", exc
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        models.Base.metadata.create_all(bind=database.engine)
        logger.info("Database tables ensured.")
        _seed_demo_users()
    except Exception as exc:
        logger.critical("Startup failed: %s", exc)
        raise
    yield
    logger.info("Application shutting down.")


def _seed_demo_users():
    """Creates demo users if the users table is empty (dev convenience)."""
    db: Session = database.SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            demo = [
                models.User(username="andrii", password_hash=hash_password("pass123")),
                models.User(username="oksana", password_hash=hash_password("pass123")),
                models.User(username="markus", password_hash=hash_password("pass123")),
            ]
            db.add_all(demo)
            db.commit()
            logger.info("Demo users seeded: andrii, oksana, markus (password: pass123)")
    except SQLAlchemyError as exc:
        logger.error("Seeding failed: %s", exc)
        db.rollback()
    finally:
        db.close()


app = FastAPI(title="Status Check API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────── Global error handlers ───────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error. Please try again."},
    )


# ─────────────────── Auth routes ───────────────────
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter(models.User.username == user_in.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    try:
        new_user = models.User(
            username=user_in.username,
            password_hash=hash_password(user_in.password),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info("New user registered: %s", new_user.username)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Registration DB error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Registration failed due to a server error"
        )


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    if not credentials.username or not credentials.password:
        raise HTTPException(
            status_code=422, detail="Username and password are required"
        )

    user = (
        db.query(models.User)
        .filter(models.User.username == credentials.username)
        .first()
    )
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token({"sub": str(user.id)})
    logger.info("User logged in: %s", user.username)
    return schemas.TokenResponse(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
    )


@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/users/", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(database.get_db)):
    """Public endpoint — returns list of users for dropdowns (no passwords)."""
    try:
        return db.query(models.User).order_by(models.User.username).all()
    except SQLAlchemyError as exc:
        logger.error("list_users error: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch users")


# ─────────────────── AI / Smart-add ───────────────────
@app.post("/parse-text/")
def parse_text_with_ai(
    input_data: schemas.TextInput,
    _: models.User = Depends(get_current_user),
):
    if ai_client is None:
        raise HTTPException(
            status_code=503, detail="AI service is currently unavailable"
        )

    if not input_data.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    system_prompt = (
        "Ти розумний асистент, який витягує дані з тексту. "
        "Поверни ТІЛЬКИ чистий JSON без маркдауну з ключами: "
        "title (рядок), project (рядок, якщо не вказано — 'General'), "
        "executor_name (рядок), deadline (ISO 8601: YYYY-MM-DDTHH:MM). "
        "Поточний час: 2026-06-01T12:00."
    )

    try:
        response = ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_data.text},
            ],
            temperature=0.1,
            timeout=15,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if model ignored instructions
        raw = (
            raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        parsed = json.loads(raw)
        # Validate required fields are present
        for field in ("title", "project", "executor_name", "deadline"):
            if field not in parsed:
                parsed[field] = "" if field != "deadline" else "2026-01-01T12:00"
        return parsed

    except json.JSONDecodeError as exc:
        logger.warning("AI returned non-JSON: %s", exc)
        raise HTTPException(
            status_code=502, detail="AI returned invalid response. Please try again."
        )
    except APIConnectionError as exc:
        logger.error("AI connection error: %s", exc)
        raise HTTPException(
            status_code=503, detail="Cannot reach AI service. Check your connection."
        )
    except APITimeoutError:
        raise HTTPException(
            status_code=504, detail="AI request timed out. Please try again."
        )
    except APIStatusError as exc:
        logger.error("AI API status error %s: %s", exc.status_code, exc.message)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc.message}")
    except Exception as exc:
        logger.error("Unexpected AI error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unexpected error during AI processing"
        )


# ─────────────────── Commitments CRUD ───────────────────
@app.post("/commitments/", response_model=schemas.CommitmentOut, status_code=201)
def create_commitment(
    commitment: schemas.CommitmentCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Validate referenced users exist
    if not db.query(models.User).filter(models.User.id == commitment.author_id).first():
        raise HTTPException(
            status_code=404, detail=f"Author (id={commitment.author_id}) not found"
        )
    if (
        not db.query(models.User)
        .filter(models.User.id == commitment.checker_id)
        .first()
    ):
        raise HTTPException(
            status_code=404, detail=f"Checker (id={commitment.checker_id}) not found"
        )

    try:
        data = commitment.model_dump(by_alias=False)
        db_obj = models.Commitment(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        logger.info(
            "Commitment created: id=%s title=%r by user=%s",
            db_obj.id,
            db_obj.title,
            current_user.username,
        )
        return db_obj
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError as exc:
        db.rollback()
        logger.error("Integrity error creating commitment: %s", exc)
        raise HTTPException(
            status_code=409, detail="Data conflict — check foreign keys"
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("DB error creating commitment: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create commitment")


@app.get("/commitments/", response_model=List[schemas.CommitmentOut])
def read_commitments(
    skip: int = 0,
    limit: int = 200,
    project: Optional[str] = None,
    checker_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(get_current_user),
):
    if limit > 500:
        raise HTTPException(status_code=422, detail="limit cannot exceed 500")
    if skip < 0:
        raise HTTPException(status_code=422, detail="skip must be >= 0")

    try:
        query = db.query(models.Commitment)
        if project:
            query = query.filter(
                models.Commitment.project.ilike(f"%{project.strip()}%")
            )
        if checker_id:
            if checker_id < 1:
                raise HTTPException(
                    status_code=422, detail="checker_id must be positive"
                )
            query = query.filter(models.Commitment.checker_id == checker_id)
        return (
            query.order_by(models.Commitment.deadline).offset(skip).limit(limit).all()
        )
    except SQLAlchemyError as exc:
        logger.error("DB error reading commitments: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch commitments")


@app.get("/commitments/{commitment_id}", response_model=schemas.CommitmentOut)
def read_commitment(
    commitment_id: int,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(get_current_user),
):
    if commitment_id < 1:
        raise HTTPException(status_code=422, detail="commitment_id must be positive")
    obj = (
        db.query(models.Commitment)
        .filter(models.Commitment.id == commitment_id)
        .first()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return obj


@app.put("/commitments/{commitment_id}", response_model=schemas.CommitmentOut)
def update_commitment(
    commitment_id: int,
    commitment: schemas.CommitmentCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if commitment_id < 1:
        raise HTTPException(status_code=422, detail="commitment_id must be positive")

    db_obj = (
        db.query(models.Commitment)
        .filter(models.Commitment.id == commitment_id)
        .first()
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    # Validate referenced users still exist
    if (
        not db.query(models.User)
        .filter(models.User.id == commitment.checker_id)
        .first()
    ):
        raise HTTPException(
            status_code=404, detail=f"Checker (id={commitment.checker_id}) not found"
        )

    try:
        update_data = commitment.model_dump(by_alias=False)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
        db.commit()
        db.refresh(db_obj)
        logger.info(
            "Commitment updated: id=%s by user=%s", commitment_id, current_user.username
        )
        return db_obj
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError as exc:
        db.rollback()
        logger.error("Integrity error updating commitment %s: %s", commitment_id, exc)
        raise HTTPException(status_code=409, detail="Data conflict during update")
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("DB error updating commitment %s: %s", commitment_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update commitment")


@app.delete("/commitments/{commitment_id}", status_code=200)
def delete_commitment(
    commitment_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if commitment_id < 1:
        raise HTTPException(status_code=422, detail="commitment_id must be positive")

    db_obj = (
        db.query(models.Commitment)
        .filter(models.Commitment.id == commitment_id)
        .first()
    )
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Commitment not found")

    try:
        db.delete(db_obj)
        db.commit()
        logger.info(
            "Commitment deleted: id=%s by user=%s", commitment_id, current_user.username
        )
        return {"detail": "Commitment deleted successfully", "id": commitment_id}
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("DB error deleting commitment %s: %s", commitment_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete commitment")


# ─────────────────── Static files ───────────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        logger.error("index.html not found at %s", index_path)
        raise HTTPException(status_code=404, detail="Frontend not found")
    return index_path
