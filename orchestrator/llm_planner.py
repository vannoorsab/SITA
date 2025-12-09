from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

from .models import RetryPolicy, Task


def generate_plan(objective: str, context: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Task]:
    """Mock planner that returns a fixed analyzer -> triage -> remediate sequence.

    This function does NOT call a real LLM; it is deterministic and
    suitable for unit tests.
    """

    tasks: List[Task] = []

    tasks.append(
        Task(
            id=str(uuid4()),
            name="Analyze alerts",
            description="Use Analyzer Agent to interpret raw alerts.",
            agent="analyzer",
            method="POST",
            url="http://analyzer/agent/analyze",
            payload={
                "task_id": "analysis-1",
                "events": alerts,
                "requested_outputs": [
                    "severity",
                    "category",
                    "summary",
                    "root_cause",
                    "remediation",
                ],
            },
            timeout_seconds=5,
            retry_policy=RetryPolicy(max_retries=1),
        )
    )

    tasks.append(
        Task(
            id=str(uuid4()),
            name="Triage alerts",
            description="Prioritize alerts using Triage Agent.",
            agent="triage",
            method="POST",
            url="http://triage/triage",
            payload={
                "alerts": [],  # In a real system we would feed Analyzer output.
                "asset_inventory": {},
                "policy": {"auto_block_ips": True, "default_required_approvals": 1},
                "threat_intel_apis": {},
            },
            timeout_seconds=5,
            retry_policy=RetryPolicy(max_retries=1),
        )
    )

    tasks.append(
        Task(
            id=str(uuid4()),
            name="Run remediation playbook",
            description="Invoke Remediation Agent for high-priority alerts.",
            agent="remediation",
            method="POST",
            url="http://remediation/remediate",
            payload={
                "alert": {},
                "playbook": "block_ip_then_snapshot",
                "auto_authorization": False,
                "tool_endpoints": {},
                "policy": {"safe_auto": ["block_ip", "snapshot_vm"], "forbidden_actions": []},
                "run_mode": "simulation",
            },
            timeout_seconds=10,
            retry_policy=RetryPolicy(max_retries=1),
            requires_approval=True,
        )
    )

    return tasks
