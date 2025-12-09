from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RawPubSubMessage(BaseModel):
    """Subset of a GCP Pub/Sub push message used by the collector.

    The real schema is more complex; this is intentionally minimal.
    """

    data: str
    message_id: Optional[str] = Field(default=None, alias="messageId")
    publish_time: Optional[str] = Field(default=None, alias="publishTime")


class RawPubSubPayload(BaseModel):
    """GCP-like Pub/Sub push wrapper.

    In production this would come directly from GCP Logging sinks.
    """

    message: RawPubSubMessage
    subscription: Optional[str] = None


class NormalizedEvent(BaseModel):
    """Internal normalized representation of a single log event.

    timestamp is stored as a Python datetime but will be serialized as
    an ISO8601 string by FastAPI / Pydantic when returned in responses.
    """

    event_id: str
    timestamp: datetime
    host: Optional[str] = None
    service: Optional[str] = None
    message: str
    json_payload: Optional[Dict[str, Any]] = None
    raw_snippet: str


class CollectorResult(BaseModel):
    """Response model for /pubsub/push summarizing ingestion results."""

    accepted_count: int
    deduped_count: int
