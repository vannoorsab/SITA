from datetime import datetime

from fastapi.testclient import TestClient

from reporter.app import app


client = TestClient(app)


def _build_incident_payload():
    return {
        "id": "inc-123",
        "title": "Multiple failed logins from suspicious IP",
        "description": "Repeated authentication failures detected from IP 10.0.0.1 targeting auth-service.",
        "severity": "HIGH",
        "category": "authentication",
        "detected_at": datetime.utcnow().isoformat(),
        "impacted_assets": ["auth-service", "auth-db"],
        "indicators": {"ips": ["10.0.0.1"]},
        "status": "open",
    }


def test_reporter_generates_all_channel_payloads():
    payload = {
        "incident": _build_incident_payload(),
        "channels": ["slack", "github", "pagerduty", "executive_summary"],
        "recipients": {
            "slack_channel": "#sec-alerts",
            "github_repo": "sita/security-incidents",
            "pagerduty_routing_key": "PD_ROUTING_KEY_TODO",
        },
        "send": False,
    }

    resp = client.post("/report", json=payload)
    assert resp.status_code == 200

    body = resp.json()

    # Basic envelope checks
    assert body["incident_id"] == "inc-123"
    assert "slack" in body["channels"]
    assert "github" in body["channels"]
    assert "pagerduty" in body["channels"]
    assert "executive_summary" in body["channels"]

    # Slack payload
    slack = body["slack_message"]
    assert isinstance(slack, dict)
    assert slack["text"]
    assert isinstance(slack.get("attachments"), list) and slack["attachments"]
    attachment = slack["attachments"][0]
    assert "actions" in attachment and isinstance(attachment["actions"], list)
    assert any(a.get("type") == "button" for a in attachment["actions"])

    # GitHub payload
    github = body["github_issue"]
    assert isinstance(github, dict)
    assert github["title"]
    assert github["body"]
    assert isinstance(github["labels"], list) and github["labels"]

    # PagerDuty payload
    pd = body["pagerduty_event"]
    assert isinstance(pd, dict)
    assert pd["payload"]["summary"]
    assert pd["payload"]["severity"] in {"critical", "error", "warning", "info"}

    # Executive summary
    summary = body["executive_summary"]
    assert isinstance(summary, str) and summary.strip()
    # Expect at least 3 short paragraphs separated by blank lines
    parts = [p for p in summary.split("\n\n") if p.strip()]
    assert len(parts) >= 3

    # Artifact links
    artifacts = body["artifact_links"]
    assert isinstance(artifacts, list) and artifacts
    assert all(isinstance(a, str) and a for a in artifacts)

    # Ensure no outbound sending occurred (this implementation never sends).
    assert body["send"] is False
