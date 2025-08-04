# File: routers/users.py
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, and_, or_, select

from app.auth import check_email_exists, get_password_hash
from app.database import User, get_session
from app.schema import (
    UserCreateSchema,
    UserReadSchema,
    UserRole,
    UserUpdateSchema,
)

router = APIRouter()


@router.post("/", response_model=UserReadSchema)
def create_user(user_data: UserCreateSchema, session: Session = Depends(get_session)):
    """
    Create a new user
    """
    # Check if user already exists
    if check_email_exists(session, user_data.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user_dict = user_data.model_dump(exclude={"password"})
    db_user = User(**user_dict, hashed_password=hashed_password)

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.get("/{user_id}", response_model=UserReadSchema)
def get_user(user_id: int, session: Session = Depends(get_session)):
    """
    Get a specific user
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_model=List[UserReadSchema])
def list_users(
    role: UserRole = Query(None, description="Filter by user role"),
    is_active: bool = Query(None, description="Filter by active status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """
    Get list of users with optional filtering
    """
    query = select(User)

    # Apply filters
    if role:
        query = query.where(User.role == role)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Add ordering
    query = query.order_by(User.full_name)

    # Add pagination
    query = query.offset(offset).limit(limit)

    users = session.exec(query).all()
    return users


@router.put("/{user_id}", response_model=UserReadSchema)
def update_user(
    user_id: int, user_update: UserUpdateSchema, session: Session = Depends(get_session)
):
    """
    Update a user
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update only provided fields
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserReadSchema)
def patch_user(
    user_id: int, user_update: UserUpdateSchema, session: Session = Depends(get_session)
):
    """
    Partially update a user
    """
    return update_user(user_id, user_update, session)


@router.delete("/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_session)):
    """
    Delete a user
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user has active borrow records
    active_borrows = session.exec(
        select(BorrowRecord).where(
            and_(BorrowRecord.user_id == user_id, BorrowRecord.returned_date.is_(None))
        )
    ).all()

    if active_borrows:
        raise HTTPException(
            status_code=400, detail="Cannot delete user with active borrow records"
        )

    session.delete(user)
    session.commit()
    return {"message": "User deleted successfully"}


@router.patch("/{user_id}/deactivate")
def deactivate_user(user_id: int, session: Session = Depends(get_session)):
    """
    Deactivate a user
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    user.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(user)
    return {"message": "User deactivated successfully"}


@router.patch("/{user_id}/activate")
def activate_user(user_id: int, session: Session = Depends(get_session)):
    """
    Activate a user
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(user)
    return {"message": "User activated successfully"}


@router.get("/search/", response_model=List[UserReadSchema])
def search_users(q: str = Query(..., min_length=2, description="Search query")):
    """
    Search users by name or email
    """
    query = (
        select(User)
        .where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
        .order_by(User.full_name)
    )

    users = session.exec(query).all()
    return users
