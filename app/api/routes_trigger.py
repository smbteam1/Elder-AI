"""POST /trigger-calls — accept JSON (single/list) or a CSV upload, then fire
all calls synchronously and return immediately."""
import csv
import io
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.db.models import Batch, CallRecord
from app.db.session import get_db
from app.schemas import SingleCall, TriggerResponse, TriggerResultItem
from app.services import retell_client

logger = logging.getLogger("elder_ai.trigger")

router = APIRouter()

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _valid_e164(number: str | None) -> bool:
    return bool(number) and bool(E164_RE.match(number.strip()))


def _normalize_key(key: str) -> str:
    """Normalize a CSV header into a canonical lowercase, underscore-free token."""
    return re.sub(r"[\s_]+", "", key.strip().lower())


def _row_to_call(row: dict[str, str]) -> SingleCall:
    """Map a CSV row (with messy headers) onto a SingleCall."""
    norm = {_normalize_key(k): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
    return SingleCall(
        csv_row_id=norm.get("id") or None,
        phone_number=norm.get("phonenumber") or norm.get("phone") or "",
        dynamic_variable_1=norm.get("dynamicvariable1") or None,
        dynamic_variable_2=norm.get("dynamicvariable2") or None,
    )


async def _parse_calls(request: Request, file: UploadFile | None) -> list[SingleCall]:
    """Build the list of requested calls from either a CSV upload or JSON body."""
    if file is not None:
        raw = await file.read()
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return [_row_to_call(row) for row in reader]

    # Otherwise expect JSON.
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON or a CSV file upload.")

    if isinstance(payload, dict) and "calls" in payload:
        return [SingleCall(**c) for c in payload["calls"]]
    if isinstance(payload, dict):
        return [SingleCall(**payload)]
    if isinstance(payload, list):
        return [SingleCall(**c) for c in payload]
    raise HTTPException(status_code=400, detail="Unrecognized request body shape.")


@router.post("/trigger-calls", response_model=TriggerResponse)
async def trigger_calls(
    request: Request,
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> TriggerResponse:
    calls = await _parse_calls(request, file)
    logger.info("Trigger request received: %d candidate call(s)", len(calls))

    if not calls:
        raise HTTPException(status_code=400, detail="No calls provided.")

    # One batch per request.
    batch = Batch(total_count=0)
    db.add(batch)
    db.flush()  # assign batch.id

    results: list[TriggerResultItem] = []
    valid_records: list[CallRecord] = []

    # First pass: validate + persist records (pending) or report rejection per-row.
    for entry in calls:
        phone = (entry.phone_number or "").strip()
        if not _valid_e164(phone):
            results.append(
                TriggerResultItem(
                    call_record_id="",
                    phone_number=phone,
                    status="rejected",
                    error="Invalid phone number — must be E.164 (e.g. +14155551234).",
                )
            )
            continue

        record = CallRecord(
            batch_id=batch.id,
            csv_row_id=entry.csv_row_id,
            phone_number=phone,
            dynamic_variable_1=entry.dynamic_variable_1,
            dynamic_variable_2=entry.dynamic_variable_2,
            status="pending",
        )
        db.add(record)
        valid_records.append(record)

    batch.total_count = len(valid_records)
    db.flush()  # assign record ids

    # Second pass: fire every valid call synchronously, back-to-back.
    for record in valid_records:
        try:
            call_id = retell_client.place_call(
                to_number=record.phone_number,
                dynamic_variable_1=record.dynamic_variable_1,
                dynamic_variable_2=record.dynamic_variable_2,
                batch_id=batch.id,
                call_record_id=record.id,
            )
            record.retell_call_id = call_id
            record.status = "triggered"
            record.updated_at = datetime.now(timezone.utc)
            results.append(
                TriggerResultItem(
                    call_record_id=record.id,
                    phone_number=record.phone_number,
                    status="triggered",
                    retell_call_id=call_id,
                )
            )
        except Exception as exc:  # one bad number must not stop the batch
            logger.exception("Failed to place call for record %s", record.id)
            record.status = "failed"
            record.trigger_error = str(exc)
            record.updated_at = datetime.now(timezone.utc)
            results.append(
                TriggerResultItem(
                    call_record_id=record.id,
                    phone_number=record.phone_number,
                    status="failed",
                    error=str(exc),
                )
            )

    db.commit()

    return TriggerResponse(batch_id=batch.id, total=batch.total_count, results=results)
