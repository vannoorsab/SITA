from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI

from schemas import AnalyzerAlert

from .models import Policy, TriageDecision, TriageRequest
from .utils import (
    compute_intel_score,
    compute_priority_score,
    decide_escalation,
    extract_ip_indicators,
    get_asset_criticality,
    get_effective_confidence,
)


app = FastAPI(title="SITA Triage Agent")


@app.post("/triage", response_model=List[TriageDecision])
async def triage(request: TriageRequest) -> List[TriageDecision]:
    """Prioritize analyzer alerts and decide escalation actions.

    The triage process is fully deterministic for a given input.
    """

    decisions: List[TriageDecision] = []

    for raw_alert in request.alerts:
        # Parse core AnalyzerAlert fields while preserving additional
        # context (asset_id, confidence, etc.) from raw_alert.
        alert = AnalyzerAlert.model_validate(raw_alert)

        asset_id = raw_alert.get("asset_id")
        confidence = get_effective_confidence(raw_alert, alert)

        asset_criticality = get_asset_criticality(request.asset_inventory, asset_id)

        ips = extract_ip_indicators(alert)
        intel_score = compute_intel_score(ips)

        score = compute_priority_score(confidence, asset_criticality, intel_score)

        escalation = decide_escalation(score, has_ip_indicator=bool(ips), policy=request.policy)

        auto_actions: List[str] = []
        required_approvals = 0

        if escalation == "AUTO_REMEDIATE":
            if ips and request.policy.auto_block_ips:
                auto_actions.append("block_ip")
            auto_actions.append("notify_soc")
        elif escalation == "REQUEST_APPROVAL":
            if ips and request.policy.auto_block_ips:
                auto_actions.append("block_ip")
            required_approvals = request.policy.default_required_approvals
        else:  # CREATE_INCIDENT
            auto_actions.append("open_incident_ticket")

        decision = TriageDecision(
            alert=alert,
            priority_score=score,
            escalation=escalation,
            auto_actions=auto_actions,
            required_approvals=required_approvals,
        )
        decisions.append(decision)

    return decisions
