"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    total_count: Mapped[int] = mapped_column(Integer, default=0)

    call_records: Mapped[list["CallRecord"]] = relationship(
        "CallRecord", back_populates="batch", cascade="all, delete-orphan"
    )


class CallRecord(Base):
    __tablename__ = "call_records"

    # Our internal ID, also passed to Retell metadata as call_record_id.
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String, ForeignKey("batches.id"))

    csv_row_id: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number: Mapped[str] = mapped_column(String)
    dynamic_variable_1: Mapped[str | None] = mapped_column(String, nullable=True)  # elder's name
    dynamic_variable_2: Mapped[str | None] = mapped_column(String, nullable=True)  # caller/family name

    retell_call_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # pending | triggered | analyzed | failed
    status: Mapped[str] = mapped_column(String, default="pending")
    trigger_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Populated from the call_analyzed webhook.
    call_successful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    user_sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    call_status: Mapped[str | None] = mapped_column(String, nullable=True)
    disconnection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch: Mapped["Batch"] = relationship("Batch", back_populates="call_records")
