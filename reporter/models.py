from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Incident(BaseModel):
    """Minimal incident representation used by the Reporter Agent."""

    id: str
    title: str
    description: str
    severity: str = Field(description="One of: LOW, MEDIUM, HIGH, CRITICAL")
    category: Optional[str] = None
    detected_at: Optional[datetime] = None
    impacted_assets: List[str] = Field(default_factory=list)
    indicators: Dict[str, Any] = Field(default_factory=dict)
    status: str = "open"


class ReporterRequest(BaseModel):
    """Request body for /report."""

    incident: Incident
    channels: List[str] = Field(
        default_factory=lambda: ["slack", "github", "pagerduty", "executive_summary"]
    )
    recipients: Dict[str, Any] = Field(default_factory=dict)
    send: bool = False


class ReporterPayload(BaseModel):
    """Aggregated channel payloads produced by the Reporter Agent."""

    incident_id: str
    channels: List[str]
    slack_message: Optional[Dict[str, Any]] = None
    github_issue: Optional[Dict[str, Any]] = None
    pagerduty_event: Optional[Dict[str, Any]] = None
    executive_summary: Optional[str] = None
    artifact_links: List[str] = Field(default_factory=list)
    send: bool = False
