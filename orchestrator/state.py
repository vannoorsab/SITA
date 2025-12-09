from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Dict, Optional

from .models import OrchestratorPlan


_PLANS: Dict[str, OrchestratorPlan] = {}
_LOCK = Lock()


def create_plan(plan: OrchestratorPlan) -> None:
    """Persist a new plan in the in-memory store."""

    with _LOCK:
        _PLANS[plan.id] = plan


def get_plan(plan_id: str) -> Optional[OrchestratorPlan]:
    """Retrieve a plan by id, if present."""

    with _LOCK:
        return _PLANS.get(plan_id)


def save_plan(plan: OrchestratorPlan) -> None:
    """Update an existing plan in the store and bump updated_at."""

    plan.updated_at = datetime.utcnow()
    with _LOCK:
        _PLANS[plan.id] = plan
