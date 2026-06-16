# Elder AI — Trigger & Collect Call Service (Phase 1)

A minimal FastAPI service that triggers outbound calls via the **Retell AI** API
and collects post-call analysis results via webhook. Trigger-on-demand only —
no scheduler, no recurring jobs in this phase.

> Twilio is wired to Retell via custom telephony, so this code never talks to
> Twilio directly. There is no Celery / Redis / scheduling in this phase.

## 1. Install dependencies

```bash
python3 -m venv venv          # if you don't already have one
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure environment

Copy the template and fill in your Retell credentials:

```bash
cp .env.example .env
```

```
RETELL_API_KEY=your_retell_api_key
RETELL_AGENT_ID=your_agent_id
RETELL_FROM_NUMBER=+1XXXXXXXXXX
DATABASE_URL=sqlite:///./elder_ai.db
VERIFY_WEBHOOK_SIGNATURE=true
```

`.env` is git-ignored — never commit real credentials.

> **Dynamic variables:** the names sent to your Retell agent prompt are defined
> in one place at the top of [`app/services/retell_client.py`](app/services/retell_client.py)
> (`DYNAMIC_VAR_1_NAME` / `DYNAMIC_VAR_2_NAME`). Rename them there to match the
> exact placeholders used in your agent prompt.

## 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

The SQLite DB (`elder_ai.db`) and its tables are created automatically on startup.
Interactive API docs: http://localhost:8000/docs

## 4. Expose for real Retell calls (webhook)

Retell must be able to reach your webhook to deliver `call_analyzed` events:

```bash
ngrok http 8000
```

Copy the ngrok HTTPS URL and paste **`https://<your-ngrok-id>.ngrok.app/webhooks/retell`**
into your Retell agent's **webhook settings** before testing real calls.

## Endpoints

### `POST /trigger-calls`
Accepts any of:
- Single JSON: `{"phone_number": "+1...", "dynamic_variable_1": "Grandma", "dynamic_variable_2": "John"}`
- Batch JSON: `{"calls": [ {...}, {...} ]}`
- CSV upload (multipart, field name `file`) with columns `ID,phone_number,dynamic_variable1,dynamic_variable2`
  (header variations like `dynamic_variable_1` are normalized).

Phone numbers must be E.164 (`+` then digits). Invalid rows are rejected per-row,
not the whole batch. Returns the `batch_id` and a per-call result list immediately.

```bash
# single call
curl -X POST http://localhost:8000/trigger-calls \
  -H 'Content-Type: application/json' \
  -d '{"phone_number":"+14155551234","dynamic_variable_1":"Grandma","dynamic_variable_2":"John"}'

# CSV upload
curl -X POST http://localhost:8000/trigger-calls -F 'file=@people.csv'
```

### `POST /webhooks/retell`
Called by Retell. Verifies the `x-retell-signature` header, then on
`call_analyzed` updates the matching `CallRecord` with summary, sentiment,
transcript, disconnection reason and duration. Other events are acknowledged
with `200 OK`. Idempotent — duplicate events overwrite.

To simulate locally without a valid signature, set `VERIFY_WEBHOOK_SIGNATURE=false`.

### `GET /call-results/{batch_id}`
Returns the batch and all its call records with current status.

### `GET /call-results/{batch_id}/{call_record_id}`
Returns a single call record's result.

## Project layout

```
app/
  main.py                  # FastAPI app, table creation, router wiring
  core/config.py           # pydantic-settings, loads .env
  db/session.py            # SQLAlchemy engine/session
  db/models.py             # Batch, CallRecord ORM models
  schemas.py               # Pydantic request/response models
  services/retell_client.py# retell-sdk wrapper (place_call)
  api/routes_trigger.py    # POST /trigger-calls
  api/routes_webhook.py    # POST /webhooks/retell
  api/routes_results.py    # GET /call-results/...
```
