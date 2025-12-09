from __future__ import annotations

from typing import Dict

from fastapi import FastAPI

from .models import Incident, ReporterPayload, ReporterRequest
from .templates import (
    build_artifact_links,
    build_executive_summary,
    build_github_issue,
    build_pagerduty_event,
    build_slack_message,
)


app = FastAPI(title="SITA Reporter Agent")


@app.post("/report", response_model=ReporterPayload)
async def report(request: ReporterRequest) -> ReporterPayload:
    """Generate channel payloads for an incident.

    When send == False (default), no external APIs are called; only
    payloads are generated for inspection or later dispatch.
    """

    incident: Incident = request.incident
    recipients: Dict[str, object] = request.recipients

    slack_message = None
    github_issue = None
    pagerduty_event = None
    executive_summary = None

    if "slack" in request.channels:
        slack_message = build_slack_message(incident, recipients)

    if "github" in request.channels:
        github_issue = build_github_issue(incident, recipients)

    if "pagerduty" in request.channels:
        pagerduty_event = build_pagerduty_event(incident, recipients)

    if "executive_summary" in request.channels:
        executive_summary = build_executive_summary(incident)

    artifact_links = build_artifact_links(incident)

    # NOTE: Even if send == True, this reference implementation only
    # constructs payloads and does not perform any outbound calls. In a
    # production system this is where integrations would be invoked.

    return ReporterPayload(
        incident_id=incident.id,
        channels=request.channels,
        slack_message=slack_message,
        github_issue=github_issue,
        pagerduty_event=pagerduty_event,
        executive_summary=executive_summary,
        artifact_links=artifact_links,
        send=request.send,
    )
