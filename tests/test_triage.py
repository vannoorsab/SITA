from fastapi.testclient import TestClient

from triage.app import app


client = TestClient(app)


def test_high_confidence_critical_asset_auto_remediate():
    payload = {
        "alerts": [
            {
                "severity": "HIGH",
                "category": "authentication",
                "summary": "Multiple failed logins from 10.0.0.1 detected",
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
                # Additional context consumed by triage but not part of core schema
                "asset_id": "auth-server-1",
                "confidence": 0.95,
            }
        ],
        "asset_inventory": {
            "auth-server-1": {"criticality": 1.0},
        },
        "policy": {
            "auto_block_ips": True,
            "default_required_approvals": 1,
        },
        "threat_intel_apis": {},
    }

    resp = client.post("/triage", json=payload)
    assert resp.status_code == 200

    decisions = resp.json()
    assert len(decisions) == 1

    decision = decisions[0]
    assert decision["escalation"] == "AUTO_REMEDIATE"
    assert decision["priority_score"] >= 80
    assert "block_ip" in decision["auto_actions"]
    assert decision["required_approvals"] == 0


def test_low_confidence_creates_incident_not_auto_remediate():
    payload = {
        "alerts": [
            {
                "severity": "LOW",
                "category": "authentication",
                "summary": "Single failed login from 192.168.1.5",
                "root_cause": "User typo in password.",
                "remediation": [
                    "Advise user to verify credentials.",
                ],
                "enrichment": {
                    "ips": [
                        {
                            "ip": "192.168.1.5",
                            "abuse_score": 5,
                            "is_malicious": False,
                            "reason": "Test data",
                        }
                    ],
                    "domains": [],
                },
                "asset_id": "workstation-1",
                "confidence": 0.1,
            }
        ],
        "asset_inventory": {
            "workstation-1": {"criticality": 0.2},
        },
        "policy": {
            "auto_block_ips": True,
            "default_required_approvals": 1,
        },
        "threat_intel_apis": {},
    }

    resp = client.post("/triage", json=payload)
    assert resp.status_code == 200

    decisions = resp.json()
    assert len(decisions) == 1

    decision = decisions[0]
    assert decision["escalation"] == "CREATE_INCIDENT"
    assert decision["priority_score"] < 50
    # Should not auto-remediate; block_ip may still be suggested only if
    # escalation rules allow, but for CREATE_INCIDENT we keep it incident-focused.
    assert "block_ip" not in decision["auto_actions"]
