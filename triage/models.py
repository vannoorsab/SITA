from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from schemas import AnalyzerAlert


class AssetContext(BaseModel):
    """Context for an asset used during triage.

    criticality is normalized to the range [0.0, 1.0].
    """

    criticality: float = Field(0.5, ge=0.0, le=1.0)


class Policy(BaseModel):
    """Triage policy controlling safe automation behavior."""

    auto_block_ips: bool = True
    default_required_approvals: int = Field(1, ge=0)


class TriageRequest(BaseModel):
    """Request body for /triage.

    alerts: list of AnalyzerAlert-like dicts; they may contain additional
    context fields such as `asset_id` and `confidence` which are consumed
    by the triage logic but not part of the core AnalyzerAlert schema.
    """

    alerts: List[Dict[str, Any]]
    asset_inventory: Dict[str, AssetContext] = Field(default_factory=dict)
    policy: Policy
    threat_intel_apis: Dict[str, Any] = Field(default_factory=dict)


class TriageDecision(BaseModel):
    """Outcome of triaging a single analyzer alert."""

    alert: AnalyzerAlert
    priority_score: float = Field(ge=0.0, le=100.0)
    escalation: str  # AUTO_REMEDIATE | REQUEST_APPROVAL | CREATE_INCIDENT
    auto_actions: List[str] = Field(default_factory=list)
    required_approvals: int = 0
