# File: routers/authors.py
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, or_, select

from app.database import Author, get_session
from app.schema import (
    AuthorCreateSchema,
    AuthorReadSchema,
    AuthorReadWithBooks,
    AuthorSearchParamsSchema,
    AuthorUpdateSchema,
)

router = APIRouter()


@router.post("/", response_model=AuthorReadSchema)
def create_author(
    author_data: AuthorCreateSchema, session: Session = Depends(get_session)
):
    """
    Create a new author
    """
    db_author = Author(**author_data.model_dump())
    session.add(db_author)
    session.commit()
    session.refresh(db_author)
    return db_author


@router.get("/{author_id}", response_model=AuthorReadWithBooks)
def get_author(author_id: int, session: Session = Depends(get_session)):
    """
    Get a specific author with their books
    """
    author = session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    return author


@router.get("/", response_model=List[AuthorReadSchema])
def list_authors(
    search_params: AuthorSearchParamsSchema = Depends(),
    session: Session = Depends(get_session),
):
    """
    Get list of authors with optional search and pagination
    """
    query = select(Author)

    # Apply search filters
    if search_params.name:
        query = query.where(Author.name.ilike(f"%{search_params.name}%"))

    # Add ordering
    query = query.order_by(Author.name)

    # Add pagination
    query = query.offset(search_params.offset).limit(search_params.limit)

    authors = session.exec(query).all()
    return authors


@router.put("/{author_id}", response_model=AuthorReadSchema)
def update_author(
    author_id: int,
    author_update: AuthorUpdateSchema,
    session: Session = Depends(get_session),
):
    """
    Update an author
    """
    author = session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    # Update only provided fields
    update_data = author_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(author, field, value)

    author.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(author)
    return author


@router.patch("/{author_id}", response_model=AuthorReadSchema)
def patch_author(
    author_id: int,
    author_update: AuthorUpdateSchema,
    session: Session = Depends(get_session),
):
    """
    Partially update an author
    """
    return update_author(author_id, author_update, session)


@router.delete("/{author_id}")
def delete_author(author_id: int, session: Session = Depends(get_session)):
    """
    Delete an author
    """
    author = session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    # Check if author has books
    if author.books:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete author with associated books. Remove books first.",
        )

    session.delete(author)
    session.commit()
    return {"message": "Author deleted successfully"}


@router.get("/search/", response_model=List[AuthorReadSchema])
def search_authors(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """
    Search authors by name, nationality, or biography
    """
    query = (
        select(Author)
        .where(
            or_(
                Author.name.ilike(f"%{q}%"),
                Author.nationality.ilike(f"%{q}%"),
                Author.biography.ilike(f"%{q}%"),
            )
        )
        .order_by(Author.name)
        .offset(offset)
        .limit(limit)
    )

    authors = session.exec(query).all()
    return authors


@router.get("/{author_id}/books", response_model=List[dict])
def get_author_books(author_id: int, session: Session = Depends(get_session)):
    """
    Get all books by a specific author
    """
    author = session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    return [
        {
            "id": book.id,
            "title": book.title,
            "isbn": book.isbn,
            "genre": book.genre,
            "status": book.status,
            "publication_date": book.publication_date,
        }
        for book in author.books
    ]


@router.get("/stats/", response_model=dict)
def get_authors_stats(session: Session = Depends(get_session)):
    """
    Get author statistics
    """
    total_authors = session.exec(select(func.count(Author.id))).first()

    # Authors by nationality
    nationality_stats = session.exec(
        select(Author.nationality, func.count(Author.id))
        .where(Author.nationality.isnot(None))
        .group_by(Author.nationality)
        .order_by(func.count(Author.id).desc())
    ).all()

    # Authors with most books
    authors_with_book_count = session.exec(
        select(Author.name, func.count(Author.books))
        .join(Author.books)
        .group_by(Author.id, Author.name)
        .order_by(func.count(Author.books).desc())
        .limit(10)
    ).all()

    return {
        "total_authors": total_authors,
        "by_nationality": [
            {"nationality": nat, "count": count} for nat, count in nationality_stats
        ],
        "most_prolific": [
            {"author": name, "book_count": count}
            for name, count in authors_with_book_count
        ],
    }
