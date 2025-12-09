import json

import pytest
from fastapi.testclient import TestClient

import orchestrator.app as orch_app


client = TestClient(orch_app.app)


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    @property
    def text(self) -> str:
        return json.dumps(self._payload)


@pytest.fixture
def mock_requests(monkeypatch):
    calls = []

    def fake_request(method, url, json=None, timeout=None):  # type: ignore[override]
        calls.append({"method": method, "url": url, "json": json})

        if url.endswith("/agent/analyze"):
            return DummyResponse({"alerts": [{"severity": "HIGH"}]})
        if url.endswith("/triage"):
            return DummyResponse({"decisions": [{"escalation": "AUTO_REMEDIATE"}]})
        if url.endswith("/remediation/remediate"):
            return DummyResponse({"overall_status": "all_executed"})

        return DummyResponse({})

    monkeypatch.setattr(orch_app, "requests", type("R", (), {"request": staticmethod(fake_request)}))

    return calls


def test_orchestrator_analyzer_triage_remediate_flow(mock_requests):
    # Create a plan and execute analyzer + triage; remediation requires approval.
    payload = {
        "objective": "Handle new security alert",
        "context": {"source": "unit-test"},
        "alerts": [{"id": "alert-1", "message": "Failed login"}],
    }

    resp = client.post("/orchestrate", json=payload)
    assert resp.status_code == 200

    plan = resp.json()
    plan_id = plan["id"]

    # After initial run, remediation should be awaiting approval.
    assert plan["status"] in {"awaiting_approval", "succeeded"}
    tasks = plan["tasks"]
    assert len(tasks) == 3

    # First two tasks should have succeeded.
    assert tasks[0]["status"] == "succeeded"
    assert tasks[1]["status"] == "succeeded"

    # Third task requires approval.
    remed_task = tasks[2]
    assert remed_task["requires_approval"] is True
    assert remed_task["status"] == "awaiting_approval"

    # Approve the remediation task and resume execution.
    resp2 = client.post(f"/orchestrate/{plan_id}/approve")
    assert resp2.status_code == 200

    plan2 = resp2.json()
    assert plan2["status"] == "succeeded"

    tasks2 = plan2["tasks"]
    assert tasks2[2]["status"] == "succeeded"

    # Ensure the plan trace captured execution steps.
    assert "plan_trace" in plan2
    assert isinstance(plan2["plan_trace"], list)
    assert len(plan2["plan_trace"]) > 0

    # Ensure HTTP calls were made in sequence.
    urls = [c["url"] for c in mock_requests]
    assert any(u.endswith("/agent/analyze") for u in urls)
    assert any(u.endswith("/triage") for u in urls)
    assert any(u.endswith("/remediation/remediate") for u in urls)
