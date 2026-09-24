from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class CatalogueRecord(Base):
    __tablename__ = "catalogues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    artisan_id: Mapped[str | None] = mapped_column(String(100), index=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    source_language: Mapped[str] = mapped_column(String(10))
    original_transcript: Mapped[str] = mapped_column(Text)
    english_translation: Mapped[str | None] = mapped_column(Text)
    hindi_translation: Mapped[str | None] = mapped_column(Text)
    catalogue: Mapped[dict] = mapped_column(JSON)
    missing_fields: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True)
    intent: Mapped[str] = mapped_column(String(32))
    audio_used: Mapped[bool] = mapped_column(default=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    catalogue_id: Mapped[str] = mapped_column(ForeignKey("catalogues.id"))
    catalogue: Mapped[CatalogueRecord] = relationship()


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
