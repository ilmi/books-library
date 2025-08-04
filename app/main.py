from datetime import date

from fastapi import Depends, FastAPI
from scalar_fastapi import get_scalar_api_reference
from sqlmodel import Session, and_, func, select

from app.database import Author, Book, BorrowRecord, User, get_session
from app.routes import auth, authors, books, borrow_record, users
from app.schema import BookStatus, LibraryStatsSchema
from app.settings import settings

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)



# Include routers with prefixes and tags
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

app.include_router(authors.router, prefix="/api/v1/authors", tags=["Authors"])

app.include_router(books.router, prefix="/api/v1/books", tags=["Books"])

app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

app.include_router(
    borrow_record.router, prefix="/api/v1/borrow-records", tags=["Borrow Records"]
)


@app.get("/")
def read_root():
    """
    API Health Check and Welcome Message
    """
    return {
        "message": "Welcome to Library Management System API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health": "OK",
    }


@app.get("/api/v1/health")
def health_check():
    """
    Detailed health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": date.today().isoformat(),
        "api_version": "1.0.0",
    }


@app.get("/api/v1/stats", response_model=LibraryStatsSchema)
def get_library_stats(session: Session = Depends(get_session)):
    """
    Get overall library statistics
    """
    total_books = session.exec(select(func.count(Book.id))).first()
    total_authors = session.exec(select(func.count(Author.id))).first()
    total_users = session.exec(select(func.count(User.id))).first()

    books_borrowed = session.exec(
        select(func.count(Book.id)).where(Book.status == BookStatus.BORROWED)
    ).first()

    books_available = session.exec(
        select(func.count(Book.id)).where(Book.status == BookStatus.AVAILABLE)
    ).first()

    overdue_books = session.exec(
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

    return LibraryStatsSchema(
        total_books=total_books,
        total_authors=total_authors,
        total_users=total_users,
        books_borrowed=books_borrowed,
        books_available=books_available,
        overdue_books=overdue_books,
        total_fines=float(total_fines),
    )


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)
