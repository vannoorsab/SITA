from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AnalyzerEvent(BaseModel):
    """Single normalized event provided to the analyzer.

    `raw` is the raw log snippet or normalized message.
    `metadata` can contain any additional fields (host, service, ids, etc.).
    """

    raw: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalyzerRequest(BaseModel):
    """Request body for /agent/analyze."""

    task_id: str
    events: List[AnalyzerEvent]
    requested_outputs: List[str] = Field(default_factory=list)


class IPEnrichment(BaseModel):
    ip: str
    abuse_score: int
    is_malicious: bool
    reason: str


class DomainEnrichment(BaseModel):
    domain: str
    registrar: str
    country: str
    is_suspicious: bool


class Enrichment(BaseModel):
    """Deterministic enrichment information for indicators in an event."""

    ips: List[IPEnrichment] = Field(default_factory=list)
    domains: List[DomainEnrichment] = Field(default_factory=list)


class AnalyzerAlert(BaseModel):
    """Structured alert output produced by the analyzer LLM + enrichments."""

    severity: str
    category: str
    summary: str
    root_cause: str
    remediation: List[str]
    enrichment: Enrichment = Field(default_factory=Enrichment)
