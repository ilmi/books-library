# File: routers/auth.py
from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlmodel import Session

from app.auth import authenticate_user, check_email_exists, get_password_hash
from app.database import User, get_session
from app.schema import UserCreateSchema, UserReadSchema

router = APIRouter()


@router.post("/login", response_model=UserReadSchema)
def login(
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Simple login - authenticate user and return user data
    """
    user = authenticate_user(session, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    return user


@router.post("/register", response_model=UserReadSchema)
def register(user_data: UserCreateSchema, session: Session = Depends(get_session)):
    """
    Register a new user
    """
    # Check if user already exists
    if check_email_exists(session, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        **user_data.model_dump(exclude={"password"}), hashed_password=hashed_password
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return db_user


@router.post("/check-email")
def check_email_availability(
    email: str = Form(...), session: Session = Depends(get_session)
):
    """
    Check if email is available for registration
    """
    is_taken = check_email_exists(session, email)
    return {
        "email": email,
        "available": not is_taken,
        "message": "Email already registered" if is_taken else "Email available",
    }
