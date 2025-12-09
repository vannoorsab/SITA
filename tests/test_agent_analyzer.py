import json

import pytest
from fastapi.testclient import TestClient

import agent_analyzer
from gemini_wrapper import call_gemini_malformed_then_valid


@pytest.fixture
def client() -> TestClient:
    return TestClient(agent_analyzer.app)


def test_happy_path_returns_alert_with_enrichment(client: TestClient):
    payload = {
        "task_id": "task-123",
        "events": [
            {
                "raw": "2025-11-18 07:58:01 ERROR Failed login attempt from IP 1.2.3.4 for user alice accessing example.com",
                "metadata": {"source": "unit-test"},
            }
        ],
        "requested_outputs": [
            "severity",
            "category",
            "summary",
            "root_cause",
            "remediation",
        ],
    }

    resp = client.post("/agent/analyze", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["task_id"] == payload["task_id"]
    assert body["parsing_attempts"] == 1
    assert isinstance(body["warnings"], list)

    alerts = body["alerts"]
    assert isinstance(alerts, list)
    assert len(alerts) == 1

    alert = alerts[0]
    for field in ["severity", "category", "summary", "root_cause", "remediation", "enrichment"]:
        assert field in alert

    assert isinstance(alert["remediation"], list)

    enrichment = alert["enrichment"]
    assert "ips" in enrichment and "domains" in enrichment

    # IP and domain from the raw text should be present in enrichment.
    ips = {ip_info["ip"] for ip_info in enrichment["ips"]}
    domains = {d_info["domain"] for d_info in enrichment["domains"]}

    assert "1.2.3.4" in ips
    assert "example.com" in domains


def test_malformed_llm_output_then_fixed(client: TestClient, monkeypatch):
    calls = {"n": 0}

    def fake_call_gemini(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            # First response: clearly invalid JSON
            return "THIS IS NOT JSON"
        # Second response: valid JSON following the schema
        return json.dumps(
            {
                "alerts": [
                    {
                        "severity": "MEDIUM",
                        "category": "authentication",
                        "summary": "Login anomaly detected",
                        "root_cause": "Single failed login attempt.",
                        "remediation": ["Monitor for additional failures."],
                    }
                ]
            }
        )

    # Patch the analyzer's view of call_gemini so retries use our fake.
    monkeypatch.setattr(agent_analyzer, "call_gemini", fake_call_gemini)

    payload = {
        "task_id": "task-malformed",
        "events": [
            {
                "raw": "User bob failed to login from IP 9.9.9.9",
                "metadata": {},
            }
        ],
        "requested_outputs": [
            "severity",
            "category",
            "summary",
            "root_cause",
            "remediation",
        ],
    }

    resp = client.post("/agent/analyze", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["task_id"] == payload["task_id"]
    assert body["parsing_attempts"] == 2
    assert len(body["alerts"]) == 1

    alert = body["alerts"][0]
    assert alert["severity"] == "MEDIUM"
    assert alert["category"] == "authentication"
    assert isinstance(alert["remediation"], list)

    # Ensure our fake was actually called twice (initial + repair attempt).
    assert calls["n"] == 2

    # There should be at least one warning about the malformed output.
    assert any("failed to parse" in w for w in body["warnings"])
