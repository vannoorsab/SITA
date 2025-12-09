from __future__ import annotations

import json
from textwrap import dedent

from schemas import AnalyzerRequest


ANALYZER_JSON_SCHEMA_DESCRIPTION = dedent(
    """
    Return a single JSON object with the following structure (and no extra fields):
    {
      "alerts": [
        {
          "severity": "one of: LOW, MEDIUM, HIGH, CRITICAL",
          "category": "short category string (e.g. authentication, network, access)",
          "summary": "1-2 sentence human-readable summary of the incident",
          "root_cause": "1-2 sentence explanation of the likely root cause",
          "remediation": [
            "short actionable remediation step 1",
            "short actionable remediation step 2"
          ]
        }
      ]
    }
    """
)


FEW_SHOT_EXAMPLES = dedent(
    """
    EXAMPLE 1
    =========
    INPUT EVENTS:
    - "2025-11-18 07:58:01 ERROR Failed login attempt from IP 1.2.3.4 for user alice"

    OUTPUT JSON:
    {"alerts": [{
      "severity": "HIGH",
      "category": "authentication",
      "summary": "Multiple failed login attempts detected from a single IP.",
      "root_cause": "Possible credential stuffing or brute-force attack from IP 1.2.3.4.",
      "remediation": [
        "Temporarily block IP 1.2.3.4 at the firewall or WAF.",
        "Enforce multi-factor authentication for user alice."
      ]
    }]}

    EXAMPLE 2
    =========
    INPUT EVENTS:
    - "Firewall denied inbound connection from 5.6.7.8 to port 22 (SSH)"

    OUTPUT JSON:
    {"alerts": [{
      "severity": "MEDIUM",
      "category": "network",
      "summary": "Blocked inbound SSH connection from external IP.",
      "root_cause": "Untrusted external host attempted to establish SSH access.",
      "remediation": [
        "Verify that SSH is not exposed to the public internet where unnecessary.",
        "Review firewall rules for least-privilege access."
      ]
    }]}
    """
)


def build_analyzer_prompt(req: AnalyzerRequest) -> str:
    """Construct the main analysis prompt for the LLM.

    The prompt is written to encourage deterministic behavior (temperature
    in the 0.0–0.2 range) and to enforce a strict JSON output format.
    """

    events_lines = []
    for idx, event in enumerate(req.events, start=1):
        meta_json = json.dumps(event.metadata, sort_keys=True, default=str)
        events_lines.append(f"{idx}. RAW: {event.raw}\n   METADATA: {meta_json}")

    requested = req.requested_outputs or [
        "severity",
        "category",
        "summary",
        "root_cause",
        "remediation",
    ]

    prompt = f"""
    You are SITA Analyzer, a deterministic cybersecurity incident triage agent.

    - You analyze normalized security log events.
    - You MUST respond using ONLY a single JSON object.
    - DO NOT include any markdown, comments, explanations, or prose outside JSON.
    - Assume your sampling temperature is 0.1 (very low randomness).

    REQUIRED JSON OUTPUT SCHEMA:
    {ANALYZER_JSON_SCHEMA_DESCRIPTION}

    The client has specifically requested the following output fields:
    {", ".join(requested)}

    FEW-SHOT EXAMPLES (follow the same style and structure):
    {FEW_SHOT_EXAMPLES}

    Now analyze the following request and produce a single JSON object:

    TASK_ID: {req.task_id}
    EVENTS:
    {chr(10).join(events_lines)}

    Remember:
    - Output must be valid JSON.
    - Do not wrap JSON in backticks.
    - Do not add any additional top-level properties beyond what the schema allows.
    """

    return dedent(prompt).strip()


def build_json_fix_prompt(bad_output: str) -> str:
    """Prompt asking the LLM to repair malformed JSON into valid schema.

    The model must return ONLY valid JSON following the analyzer_alert
    schema described earlier, without any extra text.
    """

    prompt = f"""
    You are a JSON repair assistant for SITA Analyzer.

    The previous model response was supposed to be a JSON object following
    this schema:
    {ANALYZER_JSON_SCHEMA_DESCRIPTION}

    However, the response was not valid JSON. Your task is to fix it.

    PREVIOUS INVALID RESPONSE:
    <<START>>
    {bad_output}
    <<END>>

    Return ONLY valid JSON that best preserves the original intent of the
    response while strictly following the schema above. Do not include any
    extra commentary or markdown.
    """

    return dedent(prompt).strip()
