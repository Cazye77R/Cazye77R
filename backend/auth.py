import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from config import config
from database import get_session
from models import Session as DBSession
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_current_user(token: str, db: Session) -> User:
    session = db.exec(select(DBSession).where(DBSession.token == token)).first()
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _create_session(user: User, db: Session) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(minutes=config.SESSION_TIMEOUT_MINUTES)
    db_session = DBSession(token=token, user_id=user.id, expires_at=expires)
    db.add(db_session)
    db.commit()
    return token


@router.get("/setup-required")
def setup_required(db: Session = Depends(get_session)):
    users = db.exec(select(User)).all()
    return {"setup_required": len(users) == 0}


@router.post("/setup", response_model=TokenResponse)
def setup(req: SetupRequest, db: Session = Depends(get_session)):
    existing = db.exec(select(User)).all()
    if existing:
        raise HTTPException(status_code=400, detail="Setup already completed")
    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_session(user, db)
    return TokenResponse(token=token, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.username == req.username)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_session(user, db)
    return TokenResponse(token=token, username=user.username)


@router.post("/logout")
def logout(token: str, db: Session = Depends(get_session)):
    session = db.exec(select(DBSession).where(DBSession.token == token)).first()
    if session:
        db.delete(session)
        db.commit()
    return {"ok": True}


@router.get("/me")
def me(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    return {"username": user.username, "is_admin": user.is_admin}
