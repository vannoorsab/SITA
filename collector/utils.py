from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import NormalizedEvent, RawPubSubPayload


def compute_sha256(raw: str) -> str:
    """Return the hex-encoded SHA-256 digest for the given string."""

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def signature_verify_stub(signature_header: Optional[str], body: bytes) -> bool:
    """Placeholder for verifying signed Pub/Sub push requests.

    In a production deployment this function should validate a JWT / HMAC
    signature from GCP (for example, `X-Goog-Channel-Token` or a custom
    HMAC header) using a shared secret or Google-signed certificate.

    TODO: Implement real Pub/Sub authentication / signature verification.
    """

    # For now we always accept the request so tests can run without
    # external key material.
    return True


def _parse_pubsub_entries(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Decode a GCP-like Pub/Sub push payload into a list of log entries.

    The push body is expected to follow the generic shape:

        {"message": {"data": base64(JSON) }, "subscription": "..."}

    where the decoded JSON is either:
        * {"entries": [...]} (Logging router style), or
        * a bare list of entries, or
        * a single entry object.
    """

    raw_model = RawPubSubPayload.model_validate(payload)
    decoded_bytes = base64.b64decode(raw_model.message.data)

    try:
        decoded = json.loads(decoded_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        # Treat the decoded string as a single opaque entry.
        return [
            {
                "timestamp": raw_model.message.publish_time,
                "textPayload": decoded_bytes.decode("utf-8", errors="replace"),
            }
        ]

    if isinstance(decoded, dict) and "entries" in decoded:
        entries = decoded["entries"]
    elif isinstance(decoded, list):
        entries = decoded
    else:
        entries = [decoded]

    if not isinstance(entries, list):  # type: ignore[unreachable]
        raise ValueError("Decoded Pub/Sub payload is not a list of entries")

    return entries  # type: ignore[return-value]


def extract_entries_from_payload(payload: Any) -> List[Dict[str, Any]]:
    """Extract a list of raw log entry dictionaries from an incoming body.

    Supports:
    * GCP-like Pub/Sub push payloads
    * Simplified format: a JSON array of log objects
    * Simplified format: {"entries": [...]} wrapper
    """

    if isinstance(payload, dict) and "message" in payload:
        return _parse_pubsub_entries(payload)

    if isinstance(payload, dict) and "entries" in payload:
        entries = payload["entries"]
        if not isinstance(entries, list):
            raise ValueError("entries field must be a list")
        return entries

    if isinstance(payload, list):
        return payload

    raise ValueError("Unsupported payload structure for log collection")


def _parse_timestamp(value: Any) -> datetime:
    """Best-effort parser for timestamps into timezone-aware datetimes."""

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if not value:
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        # Unix seconds
        return datetime.fromtimestamp(float(value), tz=timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        # Normalize trailing Z to +00:00 for fromisoformat
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return datetime.now(timezone.utc)

    return datetime.now(timezone.utc)


def normalize_log_entry(entry: Dict[str, Any]) -> NormalizedEvent:
    """Convert a raw log entry dict into a NormalizedEvent instance."""

    timestamp = _parse_timestamp(
        entry.get("timestamp") or entry.get("receiveTimestamp") or entry.get("time")
    )

    resource = entry.get("resource") or {}
    resource_labels = resource.get("labels") or {}

    host: Optional[str] = (
        entry.get("host")
        or entry.get("hostname")
        or resource_labels.get("host")
        or resource_labels.get("instance_id")
    )

    service: Optional[str] = (
        entry.get("service")
        or entry.get("logger")
        or entry.get("logName")
        or resource.get("type")
    )

    json_payload: Optional[Dict[str, Any]] = entry.get("jsonPayload")

    message: Optional[str] = (
        entry.get("textPayload")
        or entry.get("message")
        or entry.get("log")
    )

    if not message and json_payload is not None:
        message = json.dumps(json_payload, sort_keys=True, default=str)

    # Fallback: use the whole entry as the message
    raw_snippet = json.dumps(entry, sort_keys=True, default=str)
    if not message:
        message = raw_snippet

    return NormalizedEvent(
        event_id=str(uuid.uuid4()),
        timestamp=timestamp,
        host=host,
        service=service,
        message=message,
        json_payload=json_payload,
        raw_snippet=raw_snippet,
    )
