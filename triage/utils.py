from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from schemas import AnalyzerAlert

from .models import AssetContext, Policy


IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def extract_ip_indicators(alert: AnalyzerAlert) -> List[str]:
    """Extract IP indicators from an AnalyzerAlert using simple regex.

    We scan the summary, root_cause, and remediation text for IPv4
    addresses. In a fuller implementation we would also inspect any
    enrichment fields.
    """

    text_parts: List[str] = [alert.summary, alert.root_cause]
    text_parts.extend(alert.remediation)

    ips: List[str] = []
    for part in text_parts:
        ips.extend(IP_REGEX.findall(part))

    # Preserve order while removing duplicates.
    seen = set()
    unique_ips: List[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)
    return unique_ips


def intel_score_for_ip(ip: str) -> float:
    """Deterministic threat-intel score for an IP address in [0, 1].

    Rule of thumb: any IP whose last octet is "1" is considered
    high-risk (score 1.0); other IPs are low but non-zero risk (0.3).
    """

    try:
        last_octet = ip.split(".")[-1]
    except Exception:  # pragma: no cover - defensive
        return 0.0

    if last_octet == "1":
        return 1.0
    return 0.3


def compute_intel_score(ips: Iterable[str]) -> float:
    """Aggregate intel score across a set of IPs, range [0, 1]."""

    scores = [intel_score_for_ip(ip) for ip in ips]
    return max(scores) if scores else 0.0


SEVERITY_CONFIDENCE_MAP: Dict[str, float] = {
    "CRITICAL": 1.0,
    "HIGH": 0.9,
    "MEDIUM": 0.6,
    "LOW": 0.3,
}


def get_effective_confidence(raw_alert: Dict[str, Any], alert: AnalyzerAlert) -> float:
    """Return the confidence value for an alert in [0, 1].

    Preference order:
    1. Explicit `confidence` field on the incoming alert payload
    2. Derived from severity using SEVERITY_CONFIDENCE_MAP
    3. Default 0.5
    """

    if "confidence" in raw_alert:
        try:
            val = float(raw_alert["confidence"])
        except (TypeError, ValueError):  # pragma: no cover - defensive
            val = 0.5
        return max(0.0, min(val, 1.0))

    sev = (alert.severity or "").upper()
    return SEVERITY_CONFIDENCE_MAP.get(sev, 0.5)


def get_asset_criticality(asset_inventory: Dict[str, AssetContext], asset_id: str | None) -> float:
    """Return normalized asset criticality [0,1] for the given asset id.

    If asset_id is missing or unknown, fall back to an entry named
    "default" if present; otherwise return the AssetContext default.
    """

    if asset_id and asset_id in asset_inventory:
        return asset_inventory[asset_id].criticality

    if "default" in asset_inventory:
        return asset_inventory["default"].criticality

    return AssetContext().criticality


def compute_priority_score(confidence: float, asset_criticality: float, intel_score: float) -> float:
    """Compute normalized priority score in [0, 100].

    Formula (weights sum to 100):
        (confidence * 60) + (asset_criticality * 30) + (intel_score * 10)
    """

    score = (confidence * 60.0) + (asset_criticality * 30.0) + (intel_score * 10.0)
    return max(0.0, min(score, 100.0))


def decide_escalation(
    score: float,
    has_ip_indicator: bool,
    policy: Policy,
) -> str:
    """Determine escalation decision based on score and policy."""

    if score >= 80.0 and policy.auto_block_ips and has_ip_indicator:
        return "AUTO_REMEDIATE"
    if 50.0 <= score < 80.0:
        return "REQUEST_APPROVAL"
    return "CREATE_INCIDENT"
