from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException

from .executor import execute_remediation
from .models import RemediationRequest, RemediationResult


app = FastAPI(title="SITA Remediation Agent")


@app.post("/remediate", response_model=RemediationResult)
async def remediate(request: RemediationRequest) -> RemediationResult:
    """Run (or simulate) a remediation playbook for a given alert.

    This endpoint is deterministic and uses only simulated tool calls in
    tests; no real cloud APIs are invoked.
    """

    if request.run_mode not in {"simulation", "execute"}:
        raise HTTPException(status_code=400, detail="Invalid run_mode")

    try:
        result = execute_remediation(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
