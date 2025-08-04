# File: auth.py (Simplified Authentication utilities)
from typing import Optional

from passlib.context import CryptContext
from sqlmodel import Session, select

from app.database import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def check_email_exists(session: Session, email: str) -> bool:
    """Check if email already exists in database"""
    existing_user = session.exec(select(User).where(User.email == email)).first()
    return existing_user is not None
