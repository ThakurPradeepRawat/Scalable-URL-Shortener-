from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShortURL(Base):
    """The core mapping: short_code -> long_url.

    short_code is uniquely indexed, since it's the lookup path for
    every single redirect -- the hottest query in the whole system.
    """

    __tablename__ = "urls"

    # Deliberately NOT auto-incrementing: `id` is always explicitly set
    # by the application to the value handed out by the distributed
    # block allocator (app.core.id_allocator) -- the same integer that
    # gets Base62-encoded into short_code when no custom alias is given.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    short_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (
        Index(
            "idx_expires_at",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL"),
        ),
    )


class IdCounter(Base):
    """Single-row table backing the distributed block ID allocator.

    Seeded with exactly one row (id=1, current_value=0) via migration.
    """

    __tablename__ = "id_counter"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=1)
    current_value: Mapped[int] = mapped_column(BigInteger, default=0)
