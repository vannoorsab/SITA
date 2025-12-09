from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RemediationPolicy(BaseModel):
    """Policy controlling which actions are safe to auto-execute."""

    safe_auto: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)


class RemediationRequest(BaseModel):
    """Request body for /remediate.

    `alert` is typically an AnalyzerAlert-like structure with enrichment.
    """

    alert: Dict[str, Any]
    playbook: str
    auto_authorization: bool = False
    tool_endpoints: Dict[str, Any] = Field(default_factory=dict)
    policy: RemediationPolicy
    run_mode: str = Field("simulation", pattern="^(simulation|execute)$")


class ToolCallResult(BaseModel):
    """Simulated or real tool-call details for an action."""

    tool: str
    endpoint: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    response: Dict[str, Any] = Field(default_factory=dict)
    simulated: bool = True
    success: bool = True


class RemediationAction(BaseModel):
    """Execution status for a single remediation action."""

    action_id: str
    name: str
    type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    allowed: bool = True
    forbidden_reason: Optional[str] = None
    status: str  # executed | awaiting_approval | skipped_forbidden
    run_mode: str
    authorization: str  # auto_authorized | awaiting_approval | not_required
    tool_call: Optional[ToolCallResult] = None
    rollback: Dict[str, Any] = Field(default_factory=dict)


class RemediationResult(BaseModel):
    """Overall outcome for a remediation playbook run."""

    playbook: str
    run_mode: str
    overall_status: str  # all_executed | awaiting_approval | partial | failed
    actions: List[RemediationAction]
    audit_log: List[str] = Field(default_factory=list)
