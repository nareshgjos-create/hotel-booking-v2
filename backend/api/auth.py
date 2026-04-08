from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt

from backend.db.database import get_db
from backend.db.auth_models import User
from backend.config import settings
from backend.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ───────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_name: str
    user_email: str


# ── Helpers ───────────────────────────────────────

def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ── Routes ────────────────────────────────────────

@router.post("/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == request.email).first():
        logger.warning(f"⚠️ Register failed — email already exists: {request.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=request.name,
        email=request.email,
        hashed_password=_hash_password(request.password),
    )
    db.add(user)
    db.commit()
    logger.info(f"✅ New user registered: {request.email}")
    return {"message": "Registration successful. You can now log in."}


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not _verify_password(request.password, user.hashed_password):
        logger.warning(f"❌ Failed login attempt: {request.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = _create_access_token({"sub": user.email, "name": user.name})
    logger.info(f"✅ User logged in: {request.email}")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_name=user.name,
        user_email=user.email,
    )
