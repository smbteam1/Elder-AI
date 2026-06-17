"""GET /call-results/{batch_id} and /call-results/{batch_id}/{call_record_id}."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Batch, CallRecord
from app.db.session import get_db
from app.schemas import BatchResultsResponse, CallResultItem
from app.services import retell_client
from app.services.call_sync import update_record_from_call

logger = logging.getLogger("elder_ai.results")

router = APIRouter()


def _backfill_if_pending(record: CallRecord, db: Session) -> None:
    """If a record hasn't been analyzed yet but has a Retell call_id, pull the
    latest state from Retell directly. Makes results resilient to missed webhooks.
    Never raises — a fetch failure just leaves the record as-is.
    """
    if record.status == "analyzed" or not record.retell_call_id:
        return
    try:
        call = retell_client.get_call(record.retell_call_id)
        if update_record_from_call(record, call):
            db.commit()
            logger.info("Backfilled call_record %s from Retell -> analyzed", record.id)
    except Exception:
        logger.exception("Backfill from Retell failed for record %s", record.id)


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
    # Pull fresh data from Retell for any record still awaiting analysis.
    for record in records:
        _backfill_if_pending(record, db)

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
    _backfill_if_pending(record, db)
    return _to_item(record)
