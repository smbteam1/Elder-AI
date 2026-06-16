"""GET /call-results/{batch_id} and /call-results/{batch_id}/{call_record_id}."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Batch, CallRecord
from app.db.session import get_db
from app.schemas import BatchResultsResponse, CallResultItem

logger = logging.getLogger("elder_ai.results")

router = APIRouter()


def _to_item(record: CallRecord) -> CallResultItem:
    return CallResultItem(
        call_record_id=record.id,
        csv_row_id=record.csv_row_id,
        phone_number=record.phone_number,
        status=record.status,
        retell_call_id=record.retell_call_id,
        trigger_error=record.trigger_error,
        call_successful=record.call_successful,
        user_sentiment=record.user_sentiment,
        call_status=record.call_status,
        disconnection_reason=record.disconnection_reason,
        summary=record.summary,
        transcript=record.transcript,
        duration_seconds=record.duration_seconds,
    )


@router.get("/call-results/{batch_id}", response_model=BatchResultsResponse)
async def get_batch_results(batch_id: str, db: Session = Depends(get_db)) -> BatchResultsResponse:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")

    records = (
        db.query(CallRecord)
        .filter(CallRecord.batch_id == batch_id)
        .order_by(CallRecord.created_at)
        .all()
    )
    return BatchResultsResponse(
        batch_id=batch.id,
        total=batch.total_count,
        results=[_to_item(r) for r in records],
    )


@router.get("/call-results/{batch_id}/{call_record_id}", response_model=CallResultItem)
async def get_single_result(
    batch_id: str, call_record_id: str, db: Session = Depends(get_db)
) -> CallResultItem:
    record = (
        db.query(CallRecord)
        .filter(CallRecord.id == call_record_id, CallRecord.batch_id == batch_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Call record not found in this batch.")
    return _to_item(record)
