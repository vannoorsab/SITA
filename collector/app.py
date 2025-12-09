from __future__ import annotations

from typing import Any, Dict, List

import requests
from fastapi import FastAPI, HTTPException, Request

from .config import BUFFER_MAX_EVENTS, ORCHESTRATOR_URL, SIMULATION_MODE
from .models import CollectorResult, NormalizedEvent
from .utils import compute_sha256, extract_entries_from_payload, normalize_log_entry, signature_verify_stub


app = FastAPI(title="SITA Log Collector")

# In-memory state. This is intentionally simple for the kata and tests.
EVENT_BUFFER: List[NormalizedEvent] = []
DEDUP_INDEX: Dict[str, NormalizedEvent] = {}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/pubsub/push", response_model=CollectorResult)
async def pubsub_push(request: Request) -> CollectorResult:
    """Ingest logs from GCP Pub/Sub push or a simple JSON array.

    * Optionally verifies an HMAC/JWT signature via signature_verify_stub.
    * Normalizes logs into NormalizedEvent objects.
    * Deduplicates by sha256(raw_snippet), keeping earliest timestamp.
    * Buffers unique events in memory.
    """

    body_bytes = await request.body()

    # Optional signature header (name is arbitrary for now).
    signature_header = request.headers.get("x-sita-signature")
    if not signature_verify_stub(signature_header, body_bytes):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    try:
        raw_entries = extract_entries_from_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accepted_count = 0
    deduped_count = 0

    for entry in raw_entries:
        event = normalize_log_entry(entry)
        digest = compute_sha256(event.raw_snippet)

        existing = DEDUP_INDEX.get(digest)
        if existing is not None:
            # Duplicate: keep earliest timestamp.
            if event.timestamp < existing.timestamp:
                existing.timestamp = event.timestamp
            deduped_count += 1
            continue

        # New unique event.
        if len(EVENT_BUFFER) >= BUFFER_MAX_EVENTS:
            # Buffer full – drop additional events. In a real system we might
            # persist to disk or another queue instead.
            break

        EVENT_BUFFER.append(event)
        DEDUP_INDEX[digest] = event
        accepted_count += 1

    return CollectorResult(accepted_count=accepted_count, deduped_count=deduped_count)


@app.post("/collect/flush")
async def collect_flush() -> Dict[str, Any]:
    """Flush the in-memory buffer to the Orchestrator/Analyzer.

    When SIMULATION_MODE is True, this endpoint returns the payload that
    *would* be sent, without making any outbound HTTP calls.
    """

    global EVENT_BUFFER, DEDUP_INDEX

    events: List[NormalizedEvent] = list(EVENT_BUFFER)
    payload = [event.model_dump() for event in events]
    target_url = f"{ORCHESTRATOR_URL.rstrip('/')}/orchestrate"

    if SIMULATION_MODE:
        # Simulation: clear buffer and return the would-be request payload.
        EVENT_BUFFER = []
        DEDUP_INDEX = {}
        return {
            "simulation": True,
            "target_url": target_url,
            "event_count": len(payload),
            "events": payload,
        }

    if not payload:
        # Nothing to send.
        return {
            "simulation": False,
            "target_url": target_url,
            "event_count": 0,
            "events": [],
        }

    try:
        resp = requests.post(target_url, json=payload, timeout=5)
    except Exception as exc:  # pragma: no cover - network failure path
        raise HTTPException(status_code=502, detail=f"Failed to reach orchestrator: {exc}")

    if not (200 <= resp.status_code < 300):  # pragma: no cover - error path
        raise HTTPException(
            status_code=502,
            detail=f"Orchestrator returned unexpected status {resp.status_code}",
        )

    # Success: clear buffer and return a small status payload.
    EVENT_BUFFER = []
    DEDUP_INDEX = {}

    return {
        "simulation": False,
        "target_url": target_url,
        "event_count": len(payload),
        "events": payload,
        "orchestrator_status": resp.status_code,
    }
