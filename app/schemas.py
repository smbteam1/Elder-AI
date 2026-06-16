"""Pydantic request / response models."""
from pydantic import BaseModel, Field


# ---------- Trigger request models ----------

class SingleCall(BaseModel):
    phone_number: str
    dynamic_variable_1: str | None = None  # elder's name
    dynamic_variable_2: str | None = None  # caller / family member's name
    # Optional id carried through from a CSV "ID" column.
    csv_row_id: str | None = None


class BatchCallRequest(BaseModel):
    """JSON body shape: {"calls": [ {...}, {...} ]}."""
    calls: list[SingleCall] = Field(default_factory=list)


# ---------- Trigger response models ----------

class TriggerResultItem(BaseModel):
    call_record_id: str
    phone_number: str
    status: str
    retell_call_id: str | None = None
    error: str | None = None


class TriggerResponse(BaseModel):
    batch_id: str
    total: int
    results: list[TriggerResultItem]


# ---------- Results response models ----------

class CallResultItem(BaseModel):
    call_record_id: str
    csv_row_id: str | None = None
    phone_number: str
    status: str
    retell_call_id: str | None = None
    trigger_error: str | None = None
    call_successful: bool | None = None
    user_sentiment: str | None = None
    call_status: str | None = None
    disconnection_reason: str | None = None
    summary: str | None = None
    transcript: str | None = None
    duration_seconds: float | None = None


class BatchResultsResponse(BaseModel):
    batch_id: str
    total: int
    results: list[CallResultItem]
