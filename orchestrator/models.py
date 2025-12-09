from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RetryPolicy(BaseModel):
    """Simple retry policy for a task."""

    max_retries: int = 0


class Task(BaseModel):
    """Single step in an orchestration plan."""

    id: str
    name: str
    description: Optional[str] = None
    agent: str
    method: str = "POST"
    url: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 5
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    requires_approval: bool = False
    approved: bool = False

    # Runtime fields
    status: str = "pending"  # pending | running | succeeded | failed | awaiting_approval | skipped
    attempts: int = 0
    last_response_status: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TraceEntry(BaseModel):
    """Single log entry in the orchestration trace."""

    timestamp: datetime
    message: str
    task_id: Optional[str] = None
    status: Optional[str] = None


class OrchestratorPlan(BaseModel):
    """Full orchestration plan with execution state."""

    id: str
    objective: str
    context: Dict[str, Any] = Field(default_factory=dict)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    tasks: List[Task] = Field(default_factory=list)
    plan_trace: List[TraceEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    def add_trace(self, message: str, task_id: Optional[str] = None, status: Optional[str] = None) -> None:
        self.plan_trace.append(
            TraceEntry(timestamp=datetime.utcnow(), message=message, task_id=task_id, status=status)
        )


class OrchestrateRequest(BaseModel):
    """Input to POST /orchestrate."""

    objective: str
    context: Dict[str, Any] = Field(default_factory=dict)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    """Input to POST /orchestrate/{plan_id}/approve."""

    task_id: Optional[str] = None
