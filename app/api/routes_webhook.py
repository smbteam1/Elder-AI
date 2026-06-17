"""POST /webhooks/retell — receive Retell call lifecycle events."""
import json
import logging

from fastapi import APIRouter, Depends, Request
from retell.lib import verify as retell_verify
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CallRecord
from app.db.session import get_db
from app.services.call_sync import update_record_from_call

logger = logging.getLogger("elder_ai.webhook")

router = APIRouter()


@router.post("/webhooks/retell")
async def retell_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-retell-signature", "")

    # 1 + 2. Verify signature (unless explicitly disabled for local simulation).
    if settings.verify_webhook_signature:
        try:
            valid = retell_verify(
                raw_body.decode("utf-8"),
                settings.retell_api_key,
                signature,
            )
        except Exception:
            logger.exception("Signature verification raised")
            valid = False
        if not valid:
            logger.warning("Rejected webhook: invalid signature")
            return _json_response({"error": "invalid signature"}, status_code=401)
    else:
        logger.info("Signature verification disabled (VERIFY_WEBHOOK_SIGNATURE=false)")

    # 3. Parse payload.
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.exception("Could not parse webhook body as JSON")
        return {"status": "ok"}  # acknowledge so Retell does not retry-storm

    event = payload.get("event")
    call = payload.get("call", {}) or {}

    # Log the raw payload during active development so field paths can be confirmed.
    logger.info("Webhook event=%s raw_payload=%s", event, json.dumps(payload))

    # 4. Only act on call_analyzed; acknowledge the others.
    if event != "call_analyzed":
        return {"status": "ok"}

    # 5. Locate our record.
    metadata = call.get("metadata", {}) or {}
    call_record_id = metadata.get("call_record_id")
    if not call_record_id:
        logger.warning("call_analyzed without call_record_id in metadata; ignoring")
        return {"status": "ok"}

    record = db.query(CallRecord).filter(CallRecord.id == call_record_id).first()
    if record is None:
        logger.warning("call_analyzed for unknown call_record_id=%s; ignoring", call_record_id)
        return {"status": "ok"}

    # 7. Idempotent: overwrite even if already analyzed (shared mapper).
    update_record_from_call(record, call)

    db.commit()
    logger.info("Updated call_record %s -> %s", call_record_id, record.status)

    # 6. Fast 200 OK.
    return {"status": "ok"}


def _json_response(content: dict, status_code: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(content=content, status_code=status_code)
