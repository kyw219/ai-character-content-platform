from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_audit_event(
    *,
    job_id: str,
    character_id: str,
    prompt: str,
    workflow: dict[str, Any],
    seed: int | None,
    lora_strength: float,
) -> dict[str, Any]:
    return {
        "time": datetime.now(UTC).isoformat(),
        "job_id": job_id,
        "character_id": character_id,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "workflow_sha256": hashlib.sha256(json.dumps(workflow, sort_keys=True).encode()).hexdigest(),
        "seed": seed,
        "lora_strength": lora_strength,
        "policy": "synthetic-character-only",
    }


def append_audit(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=True) + "\n")
