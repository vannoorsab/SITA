from __future__ import annotations

import uuid
from typing import Any, Dict, List

from .models import RemediationAction, RemediationPolicy, RemediationRequest, RemediationResult, ToolCallResult


# In a more complete implementation these would be loaded from YAML
# definitions in remediation/playbooks/*.yml. For this kata we keep a
# hard-coded mapping in sync with those files.
PLAYBOOK_ACTION_TYPES: Dict[str, List[str]] = {
    "block_ip": ["block_ip"],
    "block_ip_then_snapshot": ["block_ip", "snapshot_vm"],
}


def _resolve_primary_ip(alert: Dict[str, Any]) -> str | None:
    enrichment = alert.get("enrichment") or {}
    ips = enrichment.get("ips") or []
    if isinstance(ips, list) and ips:
        first = ips[0]
        if isinstance(first, dict):
            ip = first.get("ip")
            if isinstance(ip, str):
                return ip
    # Fallback: indicator_ip field if present
    ip = alert.get("indicator_ip")
    return ip if isinstance(ip, str) else None


def _resolve_vm_id(alert: Dict[str, Any]) -> str | None:
    if isinstance(alert.get("asset_id"), str):
        return alert["asset_id"]
    metadata = alert.get("metadata") or {}
    vm_id = metadata.get("asset_id") or metadata.get("vm_id")
    return vm_id if isinstance(vm_id, str) else None


def _build_actions_from_playbook(req: RemediationRequest) -> List[Dict[str, Any]]:
    types = PLAYBOOK_ACTION_TYPES.get(req.playbook)
    if not types:
        raise ValueError(f"Unknown playbook: {req.playbook}")

    alert = req.alert
    ip = _resolve_primary_ip(alert)
    vm_id = _resolve_vm_id(alert)

    actions: List[Dict[str, Any]] = []
    for t in types:
        if t == "block_ip":
            actions.append(
                {
                    "name": "Block IP at firewall/WAF",
                    "type": "block_ip",
                    "parameters": {"ip": ip},
                    "rollback": {
                        "summary": f"Remove firewall rule blocking IP {ip or '<unknown>'}",
                    },
                }
            )
        elif t == "snapshot_vm":
            actions.append(
                {
                    "name": "Snapshot affected VM/instance",
                    "type": "snapshot_vm",
                    "parameters": {"vm_id": vm_id},
                    "rollback": {
                        "summary": f"Delete or revert snapshot for VM {vm_id or '<unknown>'}",
                    },
                }
            )
        else:
            actions.append(
                {
                    "name": t,
                    "type": t,
                    "parameters": {},
                    "rollback": {"summary": f"Manual rollback for action {t}"},
                }
            )
    return actions


def _simulate_tool_call(action_type: str, params: Dict[str, Any], req: RemediationRequest) -> ToolCallResult:
    """Return a deterministic simulated tool-call result for an action."""

    endpoint = None
    if isinstance(req.tool_endpoints, dict):
        endpoint = req.tool_endpoints.get(action_type)

    payload = {"action_type": action_type, "parameters": params}

    response = {
        "status": "ok",
        "detail": f"Simulated {action_type} execution in {req.run_mode} mode",
    }

    return ToolCallResult(
        tool=action_type,
        endpoint=endpoint,
        payload=payload,
        response=response,
        simulated=True,
        success=True,
    )


def execute_remediation(req: RemediationRequest) -> RemediationResult:
    """Main orchestration for running a remediation playbook.

    This function is deterministic and never performs real cloud calls; it
    only simulates tool invocations based on the requested run_mode.
    """

    raw_actions = _build_actions_from_playbook(req)

    actions: List[RemediationAction] = []
    audit_log: List[str] = []

    for idx, a in enumerate(raw_actions, start=1):
        a_type = a["type"]
        forbidden = a_type in req.policy.forbidden_actions

        action_id = str(uuid.uuid4())
        allowed = not forbidden
        status: str
        authorization: str
        tool_call: ToolCallResult | None = None
        forbidden_reason = None

        if forbidden:
            status = "skipped_forbidden"
            authorization = "not_required"
            forbidden_reason = "Action forbidden by policy.forbidden_actions"
            audit_log.append(
                f"Action #{idx} ({a_type}) skipped: forbidden by policy."
            )
        else:
            # Determine whether this action is auto-executed or requires approval.
            if req.auto_authorization and a_type in req.policy.safe_auto:
                authorization = "auto_authorized"
                # In this kata we simulate both in simulation and execute mode.
                tool_call = _simulate_tool_call(a_type, a["parameters"], req)
                status = "executed"
                audit_log.append(
                    f"Action #{idx} ({a_type}) auto-executed in {req.run_mode} mode."
                )
            else:
                authorization = "awaiting_approval"
                status = "awaiting_approval"
                audit_log.append(
                    f"Action #{idx} ({a_type}) awaiting approval (auto_authorization={req.auto_authorization})."
                )

        actions.append(
            RemediationAction(
                action_id=action_id,
                name=a["name"],
                type=a_type,
                parameters=a["parameters"],
                allowed=allowed,
                forbidden_reason=forbidden_reason,
                status=status,
                run_mode=req.run_mode,
                authorization=authorization,
                tool_call=tool_call,
                rollback=a["rollback"],
            )
        )

    # Compute overall_status
    any_awaiting = any(a.status == "awaiting_approval" for a in actions)
    any_executed = any(a.status == "executed" for a in actions)
    any_forbidden = any(a.status == "skipped_forbidden" for a in actions)

    if any_forbidden and not any_executed and not any_awaiting:
        overall_status = "failed"
    elif any_forbidden or (any_executed and any_awaiting):
        overall_status = "partial"
    elif any_awaiting:
        overall_status = "awaiting_approval"
    else:
        overall_status = "all_executed"

    return RemediationResult(
        playbook=req.playbook,
        run_mode=req.run_mode,
        overall_status=overall_status,
        actions=actions,
        audit_log=audit_log,
    )
