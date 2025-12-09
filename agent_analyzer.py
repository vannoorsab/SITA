from __future__ import annotations

import json
import re
import hashlib
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI, HTTPException

from gemini_wrapper import call_gemini
from prompts import build_analyzer_prompt, build_json_fix_prompt
from schemas import AnalyzerAlert, AnalyzerRequest, DomainEnrichment, Enrichment, IPEnrichment


app = FastAPI(title="SITA Analyzer Agent")


IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_REGEX = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")


def lookup_abuseipdb(ip: str) -> IPEnrichment:
    """Deterministic fake AbuseIPDB-style lookup.

    Uses a hash of the IP to generate a stable score and flags.
    """

    h = int(hashlib.sha256(ip.encode("utf-8")).hexdigest(), 16)
    score = h % 100
    is_malicious = score >= 70
    reason = "Simulated high-risk IP" if is_malicious else "Simulated low-risk IP"
    return IPEnrichment(ip=ip, abuse_score=score, is_malicious=is_malicious, reason=reason)


def whois_lookup(domain: str) -> DomainEnrichment:
    """Deterministic fake WHOIS lookup for a domain."""

    h = int(hashlib.sha256(domain.encode("utf-8")).hexdigest(), 16)
    countries = ["US", "DE", "IN", "SG", "NL"]
    country = countries[h % len(countries)]
    registrar = f"ExampleRegistrar-{h % 1000}"
    is_suspicious = bool(h % 2 == 0)
    return DomainEnrichment(
        domain=domain,
        registrar=registrar,
        country=country,
        is_suspicious=is_suspicious,
    )


def build_enrichment_for_text(raw: str) -> Enrichment:
    """Extract indicators from raw text and attach deterministic enrichment."""

    ips = sorted(set(IP_REGEX.findall(raw)))
    domains = sorted(set(DOMAIN_REGEX.findall(raw)))

    ip_enrichments = [lookup_abuseipdb(ip) for ip in ips]
    domain_enrichments = [whois_lookup(d) for d in domains]

    return Enrichment(ips=ip_enrichments, domains=domain_enrichments)


def _parse_llm_json_with_retries(prompt: str, max_attempts: int = 3) -> Tuple[Dict[str, Any], int, List[str]]:
    """Call the LLM and parse JSON, retrying with a repair prompt if needed."""

    warnings: List[str] = []
    attempts = 0
    last_output: str | None = None

    for attempt in range(max_attempts):
        attempts += 1
        if attempt == 0:
            current_prompt = prompt
        else:
            current_prompt = build_json_fix_prompt(last_output or "")

        raw_output = call_gemini(current_prompt)
        last_output = raw_output

        try:
            parsed = json.loads(raw_output)
            return parsed, attempts, warnings
        except json.JSONDecodeError:
            warnings.append(f"Attempt {attempts}: failed to parse LLM output as JSON.")
            continue

    # If we reach here, parsing failed after all attempts.
    raise HTTPException(
        status_code=502,
        detail="Failed to parse analyzer LLM output as JSON after multiple attempts.",
    )


@app.post("/agent/analyze")
async def analyze(request: AnalyzerRequest) -> Dict[str, Any]:
    """Analyze one or more normalized events using the Analyzer Agent.

    The agent builds a structured prompt for the LLM, enforces strict
    JSON output, retries once with a JSON-fix prompt on parse failure,
    and enriches indicators deterministically.
    """

    if not request.events:
        raise HTTPException(status_code=400, detail="events list must not be empty")

    analysis_prompt = build_analyzer_prompt(request)

    parsed, attempts, warnings = _parse_llm_json_with_retries(analysis_prompt)

    alerts_data = parsed.get("alerts")
    if alerts_data is None:
        raise HTTPException(status_code=502, detail="LLM JSON did not contain 'alerts' array")

    if not isinstance(alerts_data, list):
        alerts_data = [alerts_data]

    alerts: List[AnalyzerAlert] = []
    for item in alerts_data:
        try:
            alert = AnalyzerAlert.model_validate(item)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=502, detail=f"Invalid alert structure from LLM: {exc}")
        alerts.append(alert)

    # Attach enrichment per corresponding event where possible.
    for idx, alert in enumerate(alerts):
        if idx < len(request.events):
            raw_text = request.events[idx].raw
        else:
            raw_text = "".join(ev.raw for ev in request.events)
        alert.enrichment = build_enrichment_for_text(raw_text)

    return {
        "task_id": request.task_id,
        "alerts": [a.model_dump() for a in alerts],
        "parsing_attempts": attempts,
        "warnings": warnings,
    }
