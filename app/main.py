"""Elder AI — Trigger & Collect Call Service (Phase 1)."""
import logging

from fastapi import FastAPI

from app.api import routes_results, routes_trigger, routes_webhook
from app.db.models import Base  # noqa: F401 — ensures models are registered
from app.db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Create tables on startup (no migrations needed for this phase).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Elder AI — Trigger & Collect Call Service", version="0.1.0")

app.include_router(routes_trigger.router, tags=["trigger"])
app.include_router(routes_webhook.router, tags=["webhook"])
app.include_router(routes_results.router, tags=["results"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
