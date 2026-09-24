from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CatalogueRecord, IdempotencyRecord


class IdempotencyConflict(Exception):
    pass


class CatalogueRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, catalogue_id: str) -> CatalogueRecord | None:
        return self.db.get(CatalogueRecord, catalogue_id)

    def by_key(self, key: str) -> IdempotencyRecord | None:
        return self.db.get(IdempotencyRecord, key)

    def create(
        self, record: CatalogueRecord, key: str | None = None, fingerprint: str | None = None
    ) -> CatalogueRecord:
        try:
            self.db.add(record)
            self.db.flush()
            if key:
                self.db.add(
                    IdempotencyRecord(key=key, fingerprint=fingerprint, catalogue_id=record.id)
                )
            self.db.commit()
            self.db.refresh(record)
            return record
        except IntegrityError:
            self.db.rollback()
            if key:
                existing = self.by_key(key)
                if existing and existing.fingerprint == fingerprint:
                    return existing.catalogue
                if existing:
                    raise IdempotencyConflict from None
            raise

    def save(self, record: CatalogueRecord) -> CatalogueRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list(
        self, page: int, page_size: int, search: str | None
    ) -> tuple[list[CatalogueRecord], int]:
        stmt = select(CatalogueRecord)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    CatalogueRecord.original_transcript.ilike(pattern),
                    CatalogueRecord.artisan_id.ilike(pattern),
                    CatalogueRecord.session_id.ilike(pattern),
                    CatalogueRecord.catalogue["product_name"].as_string().ilike(pattern),
                )
            )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.db.scalars(
                stmt.order_by(CatalogueRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total
