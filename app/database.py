from datetime import date, datetime
from typing import List, Optional

from sqlmodel import (
    Column,
    Field,
    Relationship,
    Session,
    SQLModel,
    String,
    create_engine,
)

from app.schema import AuthorSchema, BookSchema, BorrowRecordSchema, UserSchema

# Database setup
DATABASE_URL = "sqlite:///./data/dev.db"
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    """Create database and tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session


class User(UserSchema, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    borrow_records: List["BorrowRecord"] = Relationship(back_populates="user")


class BookAuthorLink(SQLModel, table=True):
    __tablename__ = "book_author_links"

    book_id: Optional[int] = Field(
        default=None, foreign_key="books.id", primary_key=True
    )
    author_id: Optional[int] = Field(
        default=None, foreign_key="authors.id", primary_key=True
    )


class Author(AuthorSchema, table=True):
    __tablename__ = "authors"

    id: int = Field(primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Relationships
    books: List["Book"] = Relationship(
        back_populates="authors", link_model=BookAuthorLink
    )


class Book(BookSchema, table=True):
    __tablename__ = "books"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    authors: List[Author] = Relationship(
        back_populates="books", link_model=BookAuthorLink
    )
    borrow_records: List["BorrowRecord"] = Relationship(back_populates="book")


class BorrowRecord(BorrowRecordSchema, table=True):
    __tablename__ = "borrow_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    book_id: int = Field(foreign_key="books.id", index=True)

    # Relationships
    user: Optional[User] = Relationship(back_populates="borrow_records")
    book: Optional[Book] = Relationship(back_populates="borrow_records")

    # Computed properties
    @property
    def is_overdue(self) -> bool:
        if self.returned_date:
            return False
        return date.today() > self.due_date

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days
