# File: routers/borrow_records.py
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, and_, func, or_, select

from app.database import Book, BorrowRecord, User, get_session
from app.schema import (
    BookStatus,
    BorrowRecordCreateSchema,
    BorrowRecordReadSchema,
    BorrowRecordUpdateSchema,
)

router = APIRouter()


@router.post("/", response_model=BorrowRecordReadSchema)
def create_borrow_record(
    borrow_data: BorrowRecordCreateSchema, session: Session = Depends(get_session)
):
    """
    Create a new borrow record
    """
    # Verify user exists and is active
    user = session.get(User, borrow_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is not active")

    # Verify book exists and is available
    book = session.get(Book, borrow_data.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status != BookStatus.AVAILABLE:
        raise HTTPException(
            status_code=400,
            detail=f"Book is not available. Current status: {book.status}",
        )

    # Check if user has reached borrowing limit (e.g., 5 active borrows)
    active_borrows_count = session.exec(
        select(func.count(BorrowRecord.id)).where(
            and_(
                BorrowRecord.user_id == borrow_data.user_id,
                BorrowRecord.returned_date.is_(None),
            )
        )
    ).first()

    MAX_ACTIVE_BORROWS = 5
    if active_borrows_count >= MAX_ACTIVE_BORROWS:
        raise HTTPException(
            status_code=400,
            detail=f"User has reached maximum active borrows limit ({MAX_ACTIVE_BORROWS})",
        )

    # Check if user has overdue books
    overdue_books = session.exec(
        select(BorrowRecord).where(
            and_(
                BorrowRecord.user_id == borrow_data.user_id,
                BorrowRecord.returned_date.is_(None),
                BorrowRecord.due_date < date.today(),
            )
        )
    ).all()

    if overdue_books:
        raise HTTPException(
            status_code=400,
            detail="User has overdue books. Cannot borrow new books until returned.",
        )

    # Create borrow record
    db_borrow = BorrowRecord(**borrow_data.model_dump())
    session.add(db_borrow)

    # Update book status
    book.status = BookStatus.BORROWED
    book.updated_at = datetime.utcnow()

    session.commit()
    session.refresh(db_borrow)
    return db_borrow


@router.get("/{borrow_id}", response_model=BorrowRecordReadSchema)
def get_borrow_record(borrow_id: int, session: Session = Depends(get_session)):
    """
    Get a specific borrow record
    """
    borrow_record = session.get(BorrowRecord, borrow_id)
    if not borrow_record:
        raise HTTPException(status_code=404, detail="Borrow record not found")

    return borrow_record


@router.get("/", response_model=List[BorrowRecordReadSchema])
def list_borrow_records(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    book_id: Optional[int] = Query(None, description="Filter by book ID"),
    is_returned: Optional[bool] = Query(None, description="Filter by return status"),
    is_overdue: Optional[bool] = Query(None, description="Filter by overdue status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """
    Get list of borrow records with filtering
    """
    query = select(BorrowRecord)

    # Apply filters
    if user_id:
        query = query.where(BorrowRecord.user_id == user_id)

    if book_id:
        query = query.where(BorrowRecord.book_id == book_id)

    if is_returned is not None:
        if is_returned:
            query = query.where(BorrowRecord.returned_date.isnot(None))
        else:
            query = query.where(BorrowRecord.returned_date.is_(None))

    if is_overdue is not None:
        if is_overdue:
            query = query.where(
                and_(
                    BorrowRecord.returned_date.is_(None),
                    BorrowRecord.due_date < date.today(),
                )
            )
        else:
            query = query.where(
                or_(
                    BorrowRecord.returned_date.isnot(None),
                    BorrowRecord.due_date >= date.today(),
                )
            )

    # Add ordering
    query = query.order_by(BorrowRecord.borrowed_date.desc())

    # Add pagination
    query = query.offset(offset).limit(limit)

    borrow_records = session.exec(query).all()
    return borrow_records


@router.patch("/{borrow_id}/return", response_model=BorrowRecordReadSchema)
def return_book(borrow_id: int, session: Session = Depends(get_session)):
    """
    Mark a book as returned
    """
    borrow_record = session.get(BorrowRecord, borrow_id)
    if not borrow_record:
        raise HTTPException(status_code=404, detail="Borrow record not found")

    if borrow_record.returned_date:
        raise HTTPException(status_code=400, detail="Book already returned")

    # Mark as returned
    borrow_record.returned_date = datetime.utcnow()

    # Calculate fine if overdue
    if borrow_record.is_overdue:
        FINE_PER_DAY = 0.50  # $0.50 per day
        MAX_FINE = 25.00  # Maximum fine of $25
        fine_amount = min(borrow_record.days_overdue * FINE_PER_DAY, MAX_FINE)
        borrow_record.fine_amount = fine_amount

    # Update book status to available
    book = session.get(Book, borrow_record.book_id)
    book.status = BookStatus.AVAILABLE
    book.updated_at = datetime.utcnow()

    session.commit()
    session.refresh(borrow_record)
    return borrow_record


@router.patch("/{borrow_id}/extend", response_model=BorrowRecordReadSchema)
def extend_due_date(
    borrow_id: int,
    extend_days: int = Query(..., ge=1, le=30, description="Days to extend (1-30)"),
    session: Session = Depends(get_session),
):
    """
    Extend due date for a borrow record
    """
    borrow_record = session.get(BorrowRecord, borrow_id)
    if not borrow_record:
        raise HTTPException(status_code=404, detail="Borrow record not found")

    if borrow_record.returned_date:
        raise HTTPException(status_code=400, detail="Cannot extend returned book")

    # Extend due date
    borrow_record.due_date = borrow_record.due_date + timedelta(days=extend_days)
    borrow_record.notes = f"Extended by {extend_days} days on {date.today()}"

    session.commit()
    session.refresh(borrow_record)
    return borrow_record


@router.patch("/{borrow_id}", response_model=BorrowRecordReadSchema)
def update_borrow_record(
    borrow_id: int,
    borrow_update: BorrowRecordUpdateSchema,
    session: Session = Depends(get_session),
):
    """
    Update a borrow record
    """
    borrow_record = session.get(BorrowRecord, borrow_id)
    if not borrow_record:
        raise HTTPException(status_code=404, detail="Borrow record not found")

    # Update only provided fields
    update_data = borrow_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(borrow_record, field, value)

    session.commit()
    session.refresh(borrow_record)
    return borrow_record


@router.get("/overdue/", response_model=List[BorrowRecordReadSchema])
def get_overdue_records(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """
    Get all overdue borrow records
    """
    query = (
        select(BorrowRecord)
        .where(
            and_(
                BorrowRecord.returned_date.is_(None),
                BorrowRecord.due_date < date.today(),
            )
        )
        .order_by(BorrowRecord.due_date)
        .offset(offset)
        .limit(limit)
    )

    overdue_records = session.exec(query).all()
    return overdue_records


@router.get("/due-soon/", response_model=List[BorrowRecordReadSchema])
def get_due_soon_records(
    days: int = Query(3, ge=1, le=7, description="Books due within X days"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """
    Get borrow records due soon
    """
    due_date_limit = date.today() + timedelta(days=days)

    query = (
        select(BorrowRecord)
        .where(
            and_(
                BorrowRecord.returned_date.is_(None),
                BorrowRecord.due_date <= due_date_limit,
                BorrowRecord.due_date >= date.today(),
            )
        )
        .order_by(BorrowRecord.due_date)
        .offset(offset)
        .limit(limit)
    )

    due_soon_records = session.exec(query).all()
    return due_soon_records


@router.get("/stats/", response_model=dict)
def get_borrow_stats(session: Session = Depends(get_session)):
    """
    Get borrowing statistics
    """
    total_borrows = session.exec(select(func.count(BorrowRecord.id))).first()
    active_borrows = session.exec(
        select(func.count(BorrowRecord.id)).where(BorrowRecord.returned_date.is_(None))
    ).first()

    overdue_count = session.exec(
        select(func.count(BorrowRecord.id)).where(
            and_(
                BorrowRecord.returned_date.is_(None),
                BorrowRecord.due_date < date.today(),
            )
        )
    ).first()

    total_fines = session.exec(
        select(func.coalesce(func.sum(BorrowRecord.fine_amount), 0)).where(
            BorrowRecord.fine_amount.isnot(None)
        )
    ).first()

    # Average borrow duration
    avg_duration = session.exec(
        select(
            func.avg(
                func.julianday(BorrowRecord.returned_date)
                - func.julianday(BorrowRecord.borrowed_date)
            )
        ).where(BorrowRecord.returned_date.isnot(None))
    ).first()

    # Most borrowed books
    most_borrowed = session.exec(
        select(Book.title, func.count(BorrowRecord.id))
        .join(Book)
        .group_by(Book.id, Book.title)
        .order_by(func.count(BorrowRecord.id).desc())
        .limit(10)
    ).all()

    return {
        "total_borrows": total_borrows,
        "active_borrows": active_borrows,
        "returned_borrows": total_borrows - active_borrows,
        "overdue_borrows": overdue_count,
        "total_fines_collected": float(total_fines),
        "average_borrow_duration_days": round(avg_duration, 1) if avg_duration else 0,
        "most_borrowed_books": [
            {"title": title, "borrow_count": count} for title, count in most_borrowed
        ],
    }


@router.delete("/{borrow_id}")
def delete_borrow_record(borrow_id: int, session: Session = Depends(get_session)):
    """
    Delete a borrow record - Use with caution!
    """
    borrow_record = session.get(BorrowRecord, borrow_id)
    if not borrow_record:
        raise HTTPException(status_code=404, detail="Borrow record not found")

    # If the book wasn't returned, mark it as available
    if not borrow_record.returned_date:
        book = session.get(Book, borrow_record.book_id)
        book.status = BookStatus.AVAILABLE
        book.updated_at = datetime.utcnow()

    session.delete(borrow_record)
    session.commit()
    return {"message": "Borrow record deleted successfully"}
