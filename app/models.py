from typing import Literal

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=12, max_length=1500)
    negative_prompt: str = Field(default="", max_length=1500)
    character_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,64}$")
    synthetic_character_confirmed: bool = False
    rights_confirmed: bool = False
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    lora_strength: float = Field(default=0.8, ge=0, le=1.5)


class GenerationResponse(BaseModel):
    job_id: str
    upstream_prompt_id: str
    status: Literal["queued"] = "queued"


class ReviewRequest(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list, max_length=12)
    revised_prompt: str | None = Field(default=None, max_length=1500)
    revision_count: int = Field(ge=0, le=10)


class ReviewDecision(BaseModel):
    action: Literal["accept", "revise", "manual_review"]
    next_prompt: str | None = None
    reason: str
