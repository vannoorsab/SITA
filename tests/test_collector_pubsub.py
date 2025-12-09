import base64
import json

import pytest
from fastapi.testclient import TestClient

from collector.app import DEDUP_INDEX, EVENT_BUFFER, app
from collector.config import SIMULATION_MODE


@pytest.fixture(autouse=True)
def clear_in_memory_state():
    """Clear global collector state before and after each test."""

    EVENT_BUFFER.clear()
    DEDUP_INDEX.clear()
    yield
    EVENT_BUFFER.clear()
    DEDUP_INDEX.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _build_gcp_like_payload(entries):
    wrapped = {"entries": entries}
    data = base64.b64encode(json.dumps(wrapped).encode("utf-8")).decode("utf-8")
    return {
        "message": {
            "data": data,
            "messageId": "1",
            "publishTime": "2025-01-01T00:00:00Z",
        },
        "subscription": "projects/demo/subscriptions/test",
    }


def test_pubsub_push_accepts_gcp_like_payload(client: TestClient):
    entries = [
        {
            "timestamp": "2025-01-01T00:00:00Z",
            "logName": "projects/demo/logs/test-log",
            "resource": {"type": "gce_instance", "labels": {"instance_id": "123"}},
            "textPayload": "Failed login attempt",
            "jsonPayload": {"user": "alice", "ip": "1.2.3.4"},
        },
        {
            "timestamp": "2025-01-01T00:01:00Z",
            "logName": "projects/demo/logs/test-log",
            "resource": {"type": "gce_instance", "labels": {"instance_id": "456"}},
            "textPayload": "Successful login",
            "jsonPayload": {"user": "bob", "ip": "5.6.7.8"},
        },
    ]

    payload = _build_gcp_like_payload(entries)

    resp = client.post("/pubsub/push", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["accepted_count"] == 2
    assert body["deduped_count"] == 0

    # In-memory buffer should now contain the 2 normalized events.
    assert len(EVENT_BUFFER) == 2


def test_pubsub_push_deduplicates_by_raw_snippet_hash(client: TestClient):
    entry = {
        "timestamp": "2025-01-01T00:00:00Z",
        "logName": "projects/demo/logs/test-log",
        "resource": {"type": "gce_instance", "labels": {"instance_id": "123"}},
        "textPayload": "Repeated login failure",
        "jsonPayload": {"user": "alice", "ip": "1.2.3.4"},
    }

    payload = _build_gcp_like_payload([entry])

    # First push: one accepted, zero deduped.
    resp1 = client.post("/pubsub/push", json=payload)
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["accepted_count"] == 1
    assert body1["deduped_count"] == 0

    # Second push with the same underlying log entry: should be deduplicated.
    resp2 = client.post("/pubsub/push", json=payload)
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["accepted_count"] == 0
    assert body2["deduped_count"] == 1

    # Buffer still only has one event.
    assert len(EVENT_BUFFER) == 1


def test_collect_flush_simulation_mode_structure(client: TestClient):
    assert SIMULATION_MODE, "Tests expect collector to run in SIMULATION_MODE"

    # Seed some events via the simplified array format for convenience.
    simple_entries = [
        {
            "timestamp": "2025-01-01T00:00:00Z",
            "host": "host-1",
            "service": "auth-service",
            "message": "Failed login",
            "jsonPayload": {"user": "alice"},
        },
        {
            "timestamp": "2025-01-01T00:05:00Z",
            "host": "host-2",
            "service": "auth-service",
            "message": "Successful login",
            "jsonPayload": {"user": "bob"},
        },
    ]

    # Use the simplified array payload path.
    resp_ingest = client.post("/pubsub/push", json=simple_entries)
    assert resp_ingest.status_code == 200
    assert resp_ingest.json()["accepted_count"] == 2

    # Now flush and verify the response structure in simulation mode.
    resp_flush = client.post("/collect/flush")
    assert resp_flush.status_code == 200

    body = resp_flush.json()
    assert body["simulation"] is True
    assert isinstance(body["target_url"], str)
    assert body["event_count"] == 2

    events = body["events"]
    assert isinstance(events, list)
    assert len(events) == 2

    for ev in events:
        # All normalized event fields should be present.
        assert set(ev.keys()) == {
            "event_id",
            "timestamp",
            "host",
            "service",
            "message",
            "json_payload",
            "raw_snippet",
        }

    # After a successful flush the in-memory buffer should be empty.
    assert len(EVENT_BUFFER) == 0
    assert len(DEDUP_INDEX) == 0
