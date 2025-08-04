import re
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import EmailStr, Field, validator
from sqlmodel import SQLModel


class UserRole(str, Enum):
    ADMIN = "admin"
    LIBRARIAN = "librarian"
    MEMBER = "member"


class BookStatus(str, Enum):
    AVAILABLE = "available"
    BORROWED = "borrowed"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    LOST = "lost"


class Genre(str, Enum):
    FICTION = "fiction"
    NON_FICTION = "non_fiction"
    MYSTERY = "mystery"
    ROMANCE = "romance"
    SCIENCE_FICTION = "science_fiction"
    FANTASY = "fantasy"
    BIOGRAPHY = "biography"
    HISTORY = "history"
    SCIENCE = "science"
    TECHNOLOGY = "technology"
    CHILDREN = "children"
    YOUNG_ADULT = "young_adult"


class AuthorSchema(SQLModel):
    name: str = Field(..., min_length=2, max_length=100)
    nationality: Optional[str] = Field(None, max_length=50)
    biography: Optional[str] = Field(None, max_length=1000)


class AuthorCreateSchema(AuthorSchema):
    pass


class AuthorReadSchema(AuthorSchema):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]


class AuthorReadWithBooks(AuthorReadSchema):
    books: List["BookReadSchema"] = []


class AuthorUpdateSchema(SQLModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    nationality: Optional[str] = Field(None, max_length=50)
    biography: Optional[str] = None


class UserSchema(SQLModel):
    name: str = Field(..., min_length=4, max_length=100)
    email: EmailStr = Field(unique=True)
    role: UserRole = Field(default=UserRole.MEMBER)
    is_active: bool = Field(default=True)


class BookSchema(SQLModel):
    title: str = Field(..., min_length=2, max_length=100)
    pages: int = Field(gte=0, lte=10000)
    language: Optional[str] = Field(default="English", max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    genre: Optional[Genre] = Field(default=None)
    status: BookStatus = Field(default=BookStatus.AVAILABLE)


class BorrowRecordSchema(SQLModel):
    borrowed_date: datetime = Field(default_factory=datetime.utcnow)
    due_date: date
    returned_date: Optional[datetime] = None
    fine_amount: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)

    @validator("due_date")
    def validate_due_date(cls, v, values):
        if "borrowed_date" in values:
            if v <= values["borrowed_date"].date():
                raise ValueError("Due date must be after borrowed date")
        return v

    @validator("returned_date")
    def validate_returned_date(cls, v, values):
        if v and "borrowed_date" in values:
            if v < values["borrowed_date"]:
                raise ValueError("Returned date must be after borrowed date")
        return v


class BookCreateSchema(BookSchema):
    author_ids: List[int] = Field(min_items=1)


class BookUpdateSchema(SQLModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    pages: Optional[int] = Field(None, gt=0, le=10000)
    language: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = None
    genre: Optional[Genre] = None
    status: Optional[BookStatus] = None
    author_ids: Optional[List[int]] = None


class BookReadSchema(BookSchema):
    id: int
    created_at: datetime
    updated_at: datetime


class BookReadWithAuthorsSchema(BookReadSchema):
    authors: List[AuthorReadSchema] = []


class BookSummarySchema(SQLModel):
    """Lightweight book model for use in lists and relationships"""

    id: int
    title: str
    genre: Optional[Genre]
    status: BookStatus


class UserCreateSchema(UserSchema):
    password: str = Field(min_length=8)

    @validator("password")
    def validate_password(cls, v):
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdateSchema(SQLModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?[\d\s\-\(\)]{8,15}$")
    address: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class UserReadSchema(UserSchema):
    id: int
    created_at: datetime
    updated_at: datetime


class BorrowRecordCreateSchema(BorrowRecordSchema):
    user_id: int
    book_id: int


class BorrowRecordUpdateSchema(SQLModel):
    due_date: Optional[date] = None
    returned_date: Optional[datetime] = None
    fine_amount: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class BorrowRecordReadSchema(BorrowRecordSchema):
    id: int
    user_id: int
    book_id: int
    user: UserReadSchema
    book: BookSummarySchema
    is_overdue: bool
    days_overdue: int


# Authentication schemas
# class TokenSchema(SQLModel):
#     access_token: str
#     token_type: str = "bearer"


class TokenDataSchema(SQLModel):
    email: Optional[str] = None


class UserLoginSchema(SQLModel):
    email: EmailStr
    password: str


# Search and filter schemas
class BookSearchParamsSchema(SQLModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[Genre] = None
    status: Optional[BookStatus] = None
    available_only: bool = False
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


class AuthorSearchParamsSchema(SQLModel):
    name: Optional[str] = None
    nationality: Optional[str] = None
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


# Statistics schemas
class LibraryStatsSchema(SQLModel):
    total_books: int
    total_authors: int
    total_users: int
    books_borrowed: int
    books_available: int
    overdue_books: int
    total_fines: float
