"""Thin wrapper around the retell-sdk client.

Only outbound phone-call creation lives here. Twilio is NOT touched directly —
it is wired to Retell via custom telephony, so this code only talks to Retell.
"""
import logging

from retell import Retell

from app.core.config import settings

logger = logging.getLogger("elder_ai.retell")

# ---------------------------------------------------------------------------
# Dynamic variable name mapping.
#
# The keys on the RIGHT are the EXACT variable names referenced inside your
# Retell agent prompt. The values describe what we feed into them.
#
# Change these two strings in ONE place if your agent prompt uses different
# placeholder names (e.g. "elder_name" / "caller_name").
# ---------------------------------------------------------------------------
# IMPORTANT: these strings must match the {{...}} placeholders in the Retell
# agent prompt EXACTLY, including the space. The prompt (app/prompt.md) uses
# "{{dynamic variable1}}" / "{{dynamic variable2}}" — note the space, not an underscore.
DYNAMIC_VAR_1_NAME = "dynamic variable1"  # elder's name  -> CallRecord.dynamic_variable_1
DYNAMIC_VAR_2_NAME = "dynamic variable2"  # caller's name -> CallRecord.dynamic_variable_2


def _client() -> Retell:
    if not settings.retell_api_key:
        raise RuntimeError("RETELL_API_KEY is not set — cannot call Retell.")
    return Retell(api_key=settings.retell_api_key)


def place_call(
    *,
    to_number: str,
    dynamic_variable_1: str | None,
    dynamic_variable_2: str | None,
    batch_id: str,
    call_record_id: str,
) -> str:
    """Create one outbound phone call via Retell. Returns the Retell call_id.

    Raises on any API/network error so the caller can mark the record failed.
    """
    dynamic_variables = {
        DYNAMIC_VAR_1_NAME: dynamic_variable_1 or "",
        DYNAMIC_VAR_2_NAME: dynamic_variable_2 or "",
    }

    logger.info(
        "Placing Retell call to %s (record=%s, batch=%s) vars=%s",
        to_number,
        call_record_id,
        batch_id,
        dynamic_variables,
    )

    response = _client().call.create_phone_call(
        from_number=settings.retell_from_number,
        to_number=to_number,
        override_agent_id=settings.retell_agent_id,
        retell_llm_dynamic_variables=dynamic_variables,
        metadata={"batch_id": batch_id, "call_record_id": call_record_id},
    )

    call_id = getattr(response, "call_id", None)
    logger.info("Retell accepted call to %s -> call_id=%s", to_number, call_id)
    return call_id
