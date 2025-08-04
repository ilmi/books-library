from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, and_, select

from app.database import Book, get_session
from app.schema import (
    BookCreateSchema,
    BookReadSchema,
    BookReadWithAuthorsSchema,
    BookSearchParamsSchema,
    BookUpdateSchema,
)

router = APIRouter()


@router.get("/", response_model=List[BookReadWithAuthorsSchema])
def get_books(
    session: Session = Depends(get_session),
    search_params: BookSearchParamsSchema = Depends(),
):
    """Get all books with optional filtering"""
    query = select(Book)

    # Apply filters
    filters = []
    if search_params.title:
        filters.append(Book.title.ilike(f"%{search_params.title}%"))
    if search_params.genre:
        filters.append(Book.genre == search_params.genre)
    if search_params.status:
        filters.append(Book.status == search_params.status)
    if search_params.available_only:
        filters.append(Book.status == "available")

    if filters:
        query = query.where(and_(*filters))

    # Apply pagination
    query = query.offset(search_params.offset).limit(search_params.limit)

    books = session.exec(query).all()
    return books


@router.get("/{book_id}", response_model=BookReadWithAuthorsSchema)
def get_book(book_id: int, session: Session = Depends(get_session)):
    """Get a specific book by ID"""
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.post("/", response_model=BookReadSchema)
def create_book(
    book_data: BookCreateSchema,
    session: Session = Depends(get_session),
):
    """Create a new book"""
    book = Book(**book_data.model_dump(exclude={"author_ids"}))
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.put("/{book_id}", response_model=BookReadSchema)
def update_book(
    book_id: int,
    book_update: BookUpdateSchema,
    session: Session = Depends(get_session),
):
    """Update a book"""
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book_data = book_update.model_dump(exclude_unset=True)
    for field, value in book_data.items():
        setattr(book, field, value)

    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.delete("/{book_id}")
def delete_book(book_id: int, session: Session = Depends(get_session)):
    """Delete a book"""
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    session.delete(book)
    session.commit()
    return {"message": "Book deleted successfully"}
