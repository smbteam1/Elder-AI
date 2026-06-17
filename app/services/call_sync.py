"""Shared logic for mapping a Retell call object onto a CallRecord.

Used by BOTH the webhook handler (push) and the results endpoints (pull/backfill),
so the field mapping lives in exactly one place.
"""
import logging
from datetime import datetime, timezone

from app.db.models import CallRecord

logger = logging.getLogger("elder_ai.sync")


def _duration_seconds(call: dict) -> float | None:
    # Prefer Retell's own duration_ms (present on retrieve); fall back to timestamps.
    dur_ms = call.get("duration_ms")
    if dur_ms is None:
        start, end = call.get("start_timestamp"), call.get("end_timestamp")
        if start is not None and end is not None:
            dur_ms = end - start
    if dur_ms is None:
        return None
    try:
        return round(dur_ms / 1000.0, 2)
    except (TypeError, ValueError):
        return None


def update_record_from_call(record: CallRecord, call: dict) -> bool:
    """Copy analysis fields from a Retell call dict onto the record.

    Returns True if the record was marked `analyzed` (i.e. analysis was present).
    Works for both the webhook payload's `call` object and a retrieve() result
    converted with model_dump() — both share the same field names.
    """
    analysis = call.get("call_analysis") or {}

    record.call_status = call.get("call_status")
    record.disconnection_reason = call.get("disconnection_reason")
    record.transcript = call.get("transcript")
    record.duration_seconds = _duration_seconds(call)

    if analysis:
        record.call_successful = analysis.get("call_successful")
        record.user_sentiment = analysis.get("user_sentiment")
        record.summary = analysis.get("call_summary")

    record.updated_at = datetime.now(timezone.utc)

    # Only consider it "analyzed" once Retell has produced analysis content.
    has_analysis = bool(analysis) and (
        analysis.get("call_summary") is not None
        or analysis.get("call_successful") is not None
        or analysis.get("user_sentiment") is not None
    )
    if has_analysis:
        record.status = "analyzed"
    return has_analysis
