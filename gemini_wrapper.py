from __future__ import annotations

import json
from typing import Any


def call_gemini(prompt: str) -> str:
    """Stubbed Gemini wrapper returning deterministic JSON.

    This function is intentionally simple and fully synchronous so that
    tests can monkeypatch it to simulate various behaviors (including
    malformed outputs).

    TODO: Replace this stub with a real Gemini API call using your
    GEMINI_API_KEY and appropriate SDK / HTTP client. When doing so,
    ensure you set temperature in the 0.0–0.2 range for deterministic
    behavior.
    """

    # Very small, deterministic example payload. In real usage the model
    # would tailor the fields to the specific events and requested_outputs
    # encoded in the prompt.
    example_alert: dict[str, Any] = {
        "severity": "HIGH",
        "category": "authentication",
        "summary": "Suspicious failed login activity detected",
        "root_cause": "Multiple failed logins from a single IP address.",
        "remediation": [
            "Block the offending IP at the firewall or WAF.",
            "Enable multi-factor authentication for the affected accounts.",
        ],
    }

    return json.dumps({"alerts": [example_alert]})


def call_gemini_malformed_then_valid(prompt: str, _state: dict | None = None) -> str:
    """Helper used in tests to simulate malformed JSON then valid JSON.

    The first call returns clearly invalid JSON; the second and subsequent
    calls return a valid JSON object following the analyzer_alert schema.

    Example usage in tests::

        import agent_analyzer
        from gemini_wrapper import call_gemini_malformed_then_valid

        monkeypatch.setattr(agent_analyzer, "call_gemini", call_gemini_malformed_then_valid)
    """

    if _state is None:
        # Mutable default-like state container shared across invocations.
        _state = call_gemini_malformed_then_valid.__dict__.setdefault("state", {"calls": 0})

    _state["calls"] += 1
    if _state["calls"] == 1:
        # Deliberately malformed output (not JSON at all).
        return "SEVERITY: HIGH; this is not JSON!"

    # After the first call, fall back to the normal stub.
    return call_gemini(prompt)
