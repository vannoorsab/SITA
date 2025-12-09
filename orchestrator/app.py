from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool

from .llm_planner import generate_plan
from .models import ApproveRequest, OrchestrateRequest, OrchestratorPlan, PlanStatus, Task
from .state import create_plan, get_plan, save_plan


app = FastAPI(title="SITA Orchestrator Agent")


def _run_plan(plan_id: str) -> None:
    """Execute a plan's tasks sequentially with retries and approvals.

    This function is synchronous and intended to be run in a thread pool.
    """

    plan = get_plan(plan_id)
    if plan is None:
        return

    # If the plan is already finished, do nothing.
    if plan.status in {PlanStatus.SUCCEEDED, PlanStatus.FAILED}:
        return

    plan.status = PlanStatus.RUNNING
    plan.add_trace("Plan execution started", status=plan.status.value)

    for task in plan.tasks:
        # Skip tasks that are already in a terminal state
        if task.status in {"succeeded", "failed", "skipped"}:
            continue

        # Handle approval gate
        if task.requires_approval and not task.approved:
            if task.status != "awaiting_approval":
                task.status = "awaiting_approval"
                plan.status = PlanStatus.AWAITING_APPROVAL
                plan.add_trace(
                    f"Task {task.id} requires approval before execution.",
                    task_id=task.id,
                    status=task.status,
                )
                save_plan(plan)
            return

        # Execute the task with retries
        task.status = "running"
        plan.add_trace(f"Executing task {task.id} ({task.name})", task_id=task.id, status=task.status)

        succeeded = False
        max_attempts = task.retry_policy.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            task.attempts += 1
            try:
                resp = requests.request(
                    task.method,
                    task.url,
                    json=task.payload,
                    timeout=task.timeout_seconds,
                )
                task.last_response_status = resp.status_code

                if 200 <= resp.status_code < 300:
                    try:
                        task.result = resp.json()
                    except ValueError:
                        task.result = {"raw": resp.text}
                    task.status = "succeeded"
                    plan.add_trace(
                        f"Task {task.id} succeeded (attempt {attempt}).",
                        task_id=task.id,
                        status=task.status,
                    )
                    succeeded = True
                    break

                task.error = f"HTTP {resp.status_code}"
                plan.add_trace(
                    f"Task {task.id} HTTP error {resp.status_code} on attempt {attempt}.",
                    task_id=task.id,
                    status="error",
                )

            except requests.RequestException as exc:
                task.error = str(exc)
                plan.add_trace(
                    f"Task {task.id} request exception on attempt {attempt}: {exc}",
                    task_id=task.id,
                    status="error",
                )

            if attempt < max_attempts:
                continue

        if not succeeded:
            task.status = "failed"
            plan.status = PlanStatus.FAILED
            plan.add_trace(
                f"Task {task.id} failed after {max_attempts} attempts.",
                task_id=task.id,
                status=task.status,
            )
            save_plan(plan)
            return

    # If we reach here, all tasks that can run have completed successfully.
    if all(t.status == "succeeded" for t in plan.tasks):
        plan.status = PlanStatus.SUCCEEDED
        plan.add_trace("Plan completed successfully.", status=plan.status.value)

    save_plan(plan)


@app.post("/orchestrate", response_model=OrchestratorPlan)
async def orchestrate(request: OrchestrateRequest) -> OrchestratorPlan:
    """Create a new plan from an objective and execute it immediately."""

    tasks: List[Task] = generate_plan(request.objective, request.context, request.alerts)

    now = datetime.utcnow()
    plan = OrchestratorPlan(
        id=str(uuid4()),
        objective=request.objective,
        context=request.context,
        alerts=request.alerts,
        status=PlanStatus.PENDING,
        tasks=tasks,
        created_at=now,
        updated_at=now,
    )
    plan.add_trace("Plan created.", status=plan.status.value)

    create_plan(plan)

    # Execute plan in the background (synchronously in a thread pool for tests).
    await run_in_threadpool(_run_plan, plan.id)

    # Return the latest version of the plan
    updated = get_plan(plan.id) or plan
    return updated


@app.get("/orchestrate/{plan_id}/status", response_model=OrchestratorPlan)
async def get_status(plan_id: str) -> OrchestratorPlan:
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@app.post("/orchestrate/{plan_id}/approve", response_model=OrchestratorPlan)
async def approve(plan_id: str, body: ApproveRequest | None = None) -> OrchestratorPlan:
    """Approve a pending task within a plan and resume execution."""

    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    target_task_id: Optional[str] = body.task_id if body is not None else None

    # Find the first awaiting_approval task (or by id, if provided).
    target = None
    for task in plan.tasks:
        if task.status == "awaiting_approval" and (target_task_id is None or task.id == target_task_id):
            target = task
            break

    if target is None:
        raise HTTPException(status_code=400, detail="No task awaiting approval for this plan")

    target.approved = True
    target.status = "pending"
    plan.add_trace(f"Task {target.id} approved by operator.", task_id=target.id, status=target.status)
    save_plan(plan)

    # Resume execution
    await run_in_threadpool(_run_plan, plan_id)

    updated = get_plan(plan_id) or plan
    return updated
