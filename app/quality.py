from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Action = Literal["accept", "revise", "manual_review"]


@dataclass(frozen=True)
class QualityResult:
    passed: bool
    issues: tuple[str, ...] = ()
    revised_prompt: str | None = None


@dataclass(frozen=True)
class QualityDecision:
    action: Action
    next_prompt: str | None
    reason: str


def decide_next_step(result: QualityResult, revision_count: int, max_revisions: int = 3) -> QualityDecision:
    if result.passed:
        return QualityDecision("accept", None, "quality gate passed")
    if revision_count >= max_revisions:
        return QualityDecision("manual_review", None, "revision limit reached")
    if not result.revised_prompt or not result.revised_prompt.strip():
        return QualityDecision("manual_review", None, "reviewer supplied no safe revision")
    return QualityDecision("revise", result.revised_prompt.strip(), "; ".join(result.issues) or "quality revision requested")
