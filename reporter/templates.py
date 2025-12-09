from __future__ import annotations

from datetime import datetime
from textwrap import dedent
from typing import Any, Dict, List

from .models import Incident


BACKEND_BASE_URL = "https://sita-backend.example.com"  # TODO: configure real backend URL


def _severity_color(severity: str) -> str:
    sev = (severity or "").upper()
    return {
        "CRITICAL": "#D00000",
        "HIGH": "#E67E22",
        "MEDIUM": "#F1C40F",
        "LOW": "#2ECC71",
    }.get(sev, "#95A5A6")


def build_slack_message(incident: Incident, recipients: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Slack message payload with approval buttons.

    No external API is called; this is just the payload that *would* be sent.
    """

    channel = recipients.get("slack_channel", "#security-incidents")
    approve_url = f"{BACKEND_BASE_URL}/approve?incident_id={incident.id}&decision=approve"
    reject_url = f"{BACKEND_BASE_URL}/approve?incident_id={incident.id}&decision=reject"

    text = f"[{incident.severity}] {incident.title}"

    attachment = {
        "fallback": text,
        "color": _severity_color(incident.severity),
        "title": incident.title,
        "text": incident.description[:500],  # avoid overly long messages
        "fields": [
            {"title": "Severity", "value": incident.severity, "short": True},
            {"title": "Category", "value": incident.category or "n/a", "short": True},
            {
                "title": "Impacted Assets",
                "value": ", ".join(incident.impacted_assets) or "n/a",
                "short": False,
            },
        ],
        "actions": [
            {
                "type": "button",
                "text": "Approve Auto-Remediation",
                "style": "primary",
                "url": approve_url,
            },
            {
                "type": "button",
                "text": "Reject",
                "style": "danger",
                "url": reject_url,
            },
        ],
    }

    return {
        "channel": channel,
        "text": text,
        "attachments": [attachment],
    }


def _map_severity_to_pagerduty(severity: str) -> str:
    sev = (severity or "").upper()
    if sev == "CRITICAL":
        return "critical"
    if sev == "HIGH":
        return "error"
    if sev == "MEDIUM":
        return "warning"
    return "info"


def build_pagerduty_event(incident: Incident, recipients: Dict[str, Any]) -> Dict[str, Any]:
    """Build a PagerDuty Events v2-style payload (simulation only)."""

    routing_key = recipients.get("pagerduty_routing_key", "PD_ROUTING_KEY_TODO")

    pd_severity = _map_severity_to_pagerduty(incident.severity)
    summary = f"{incident.severity} {incident.category or 'incident'}: {incident.title}"
    source = (incident.impacted_assets[0] if incident.impacted_assets else "sita-backend")

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": summary[:1024],
            "severity": pd_severity,
            "source": source,
            "component": "SITA-Alerts",
            "group": incident.category or "security",
            "class": incident.category or "security-incident",
            "custom_details": {
                "incident_id": incident.id,
                "status": incident.status,
            },
        },
    }

    return payload


def build_github_issue(incident: Incident, recipients: Dict[str, Any]) -> Dict[str, Any]:
    """Build a GitHub issue payload for tracking the incident."""

    repo = recipients.get("github_repo", "sita/security-incidents")

    title = f"[Security][{incident.severity}] {incident.title}"

    detected = incident.detected_at or datetime.utcnow()

    body = f"""Incident Summary
=================

**Title:** {incident.title}
**Severity:** {incident.severity}
**Category:** {incident.category or 'n/a'}
**Detected At:** {detected.isoformat()}Z
**Status:** {incident.status}

Description
-----------
{incident.description}

Impacted Assets
---------------
- """.rstrip()

    if incident.impacted_assets:
        for asset in incident.impacted_assets:
            body += f"\n- {asset}"
    else:
        body += "\n- n/a"

    body += "\n\nReproduction / Investigation Steps\n----------------------------------\n"
    body += "1. Review correlated alerts in SITA dashboard.\n"
    body += "2. Inspect authentication and network logs around the detection time.\n"
    body += "3. Validate whether any suspicious activity is ongoing.\n"

    body += "\nArtifacts\n---------\n"
    body += "- Logs: https://console.example.com/logs?incident_id={incident_id} (TODO: real link)\n".format(
        incident_id=incident.id
    )
    body += "- SITA Incident View: https://sita.example.com/incidents/{incident_id} (TODO: real link)\n".format(
        incident_id=incident.id
    )

    labels = [
        "security-incident",
        incident.severity.lower(),
    ]
    if incident.category:
        labels.append(incident.category.lower().replace(" ", "-"))

    return {
        "repository": repo,
        "title": title,
        "body": body,
        "labels": labels,
    }


def build_executive_summary(incident: Incident) -> str:
    """Generate a short, 3-paragraph executive summary using templates only."""

    detected = (incident.detected_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
    assets = ", ".join(incident.impacted_assets) if incident.impacted_assets else "key production systems"

    p1 = (
        f"On {detected}, the security monitoring platform detected a {incident.severity.lower()} "
        f"severity incident in the {incident.category or 'security'} domain titled \"{incident.title}\"."
    )

    p2 = (
        f"Preliminary analysis indicates that the incident affects {assets}. "
        f"Current status is {incident.status}, and no customer data exposure has been confirmed at this time."
    )

    p3 = (
        "The security team is continuing investigation, validating containment actions, and "
        "will provide further updates as more information becomes available. "
        "Recommended stakeholder action is to monitor for follow-up communications and avoid sharing sensitive details externally."
    )

    return "\n\n".join([p1, p2, p3])


def build_artifact_links(incident: Incident) -> List[str]:
    """Return a list of artifact links related to the incident (dummy URLs)."""

    return [
        f"https://console.example.com/logs?incident_id={incident.id}",
        f"https://sita.example.com/incidents/{incident.id}",
    ]
