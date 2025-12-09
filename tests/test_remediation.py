from fastapi.testclient import TestClient

from remediation.app import app


client = TestClient(app)


def _build_base_payload(playbook: str, auto_authorization: bool):
    return {
        "alert": {
            "severity": "HIGH",
            "category": "authentication",
            "summary": "Multiple failed logins from 10.0.0.1 detected on vm-auth-1",
            "root_cause": "Brute-force attempts from 10.0.0.1",
            "remediation": [
                "Block offending IP 10.0.0.1 at firewall.",
            ],
            "enrichment": {
                "ips": [
                    {
                        "ip": "10.0.0.1",
                        "abuse_score": 90,
                        "is_malicious": True,
                        "reason": "Test data",
                    }
                ],
                "domains": [],
            },
            "asset_id": "vm-auth-1",
        },
        "playbook": playbook,
        "auto_authorization": auto_authorization,
        "tool_endpoints": {
            "block_ip": "https://example.tools/firewall/block",
            "snapshot_vm": "https://example.tools/compute/snapshot",
        },
        "policy": {
            "safe_auto": ["block_ip", "snapshot_vm"],
            "forbidden_actions": [],
        },
        "run_mode": "simulation",
    }


def test_simulation_block_ip_then_snapshot_auto_authorized():
    payload = _build_base_payload("block_ip_then_snapshot", auto_authorization=True)

    resp = client.post("/remediate", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["playbook"] == "block_ip_then_snapshot"
    assert body["run_mode"] == "simulation"

    actions = body["actions"]
    assert len(actions) == 2

    # All actions should have rollback instructions and be marked executed.
    for a in actions:
        assert a["status"] == "executed"
        assert a["rollback"]["summary"]
        assert a["tool_call"] is not None
        assert a["tool_call"]["simulated"] is True

    assert body["overall_status"] == "all_executed"


def test_simulation_block_ip_then_snapshot_requires_approval():
    payload = _build_base_payload("block_ip_then_snapshot", auto_authorization=False)

    resp = client.post("/remediate", json=payload)
    assert resp.status_code == 200

    body = resp.json()

    actions = body["actions"]
    assert len(actions) == 2

    # Without auto_authorization, all actions should be awaiting approval,
    # but still have rollback instructions ready.
    for a in actions:
        assert a["status"] == "awaiting_approval"
        assert a["rollback"]["summary"]
        # No tool_call yet because execution is pending approval.
        assert a["tool_call"] is None

    assert body["overall_status"] == "awaiting_approval"