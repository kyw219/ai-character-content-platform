from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from .audit import append_audit, build_audit_event
from .config import Settings
from .models import GenerationRequest, GenerationResponse, ReviewDecision, ReviewRequest
from .policy import PolicyViolation, validate_request
from .quality import QualityResult, decide_next_step
from .workflow import build_workflow


settings = Settings()
app = FastAPI(title="AI Character Content Platform", version="1.0.0")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(401, "invalid API key")


def load_template(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, "workflow template is unavailable") from exc


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.comfyui_url}/system_stats")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "ComfyUI is unavailable") from exc
    return {"status": "ok"}


@app.post(
    "/v1/images/generations",
    response_model=GenerationResponse,
    dependencies=[Depends(require_api_key)],
)
async def generate_image(request: GenerationRequest) -> GenerationResponse:
    try:
        validate_request(
            request.prompt,
            request.character_id,
            request.synthetic_character_confirmed,
            request.rights_confirmed,
        )
    except PolicyViolation as exc:
        raise HTTPException(422, str(exc)) from exc

    workflow = build_workflow(
        load_template(settings.workflow_path),
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        seed=request.seed,
        lora_strength=request.lora_strength,
        trigger_token=settings.trigger_token,
    )
    job_id = secrets.token_urlsafe(18)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.comfyui_url}/prompt",
                json={"prompt": workflow, "client_id": job_id},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "ComfyUI could not accept the workflow") from exc
    upstream_prompt_id = str(response.json().get("prompt_id") or "")
    if not upstream_prompt_id:
        raise HTTPException(502, "ComfyUI did not return a prompt ID")

    append_audit(
        settings.audit_log_path,
        build_audit_event(
            job_id=job_id,
            character_id=request.character_id,
            prompt=request.prompt,
            workflow=workflow,
            seed=request.seed,
            lora_strength=request.lora_strength,
        ),
    )
    return GenerationResponse(job_id=job_id, upstream_prompt_id=upstream_prompt_id)


@app.post("/v1/reviews/decision", response_model=ReviewDecision, dependencies=[Depends(require_api_key)])
async def review_decision(request: ReviewRequest) -> ReviewDecision:
    decision = decide_next_step(
        QualityResult(request.passed, tuple(request.issues), request.revised_prompt),
        request.revision_count,
        settings.max_revisions,
    )
    return ReviewDecision(action=decision.action, next_prompt=decision.next_prompt, reason=decision.reason)


@app.get("/v1/jobs/{prompt_id}", dependencies=[Depends(require_api_key)])
async def get_job(prompt_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{settings.comfyui_url}/history/{prompt_id}")
        response.raise_for_status()
    return response.json()
