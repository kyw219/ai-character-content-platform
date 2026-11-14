from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowBindings:
    sampler_node: str = "3"
    positive_prompt_node: str = "6"
    negative_prompt_node: str = "7"
    lora_node: str = "10"


def build_workflow(
    template: dict[str, Any],
    *,
    prompt: str,
    negative_prompt: str = "",
    seed: int | None = None,
    lora_strength: float = 0.8,
    trigger_token: str = "character-token",
    bindings: WorkflowBindings = WorkflowBindings(),
) -> dict[str, Any]:
    workflow = copy.deepcopy(template)
    clean_prompt = prompt.strip()
    token = trigger_token.strip()
    if token and token.casefold() not in clean_prompt.casefold():
        clean_prompt = f"{token}, {clean_prompt}"

    workflow[bindings.positive_prompt_node]["inputs"]["text"] = clean_prompt
    workflow[bindings.negative_prompt_node]["inputs"]["text"] = negative_prompt.strip()
    workflow[bindings.lora_node]["inputs"]["strength_model"] = lora_strength
    workflow[bindings.lora_node]["inputs"]["strength_clip"] = lora_strength
    if seed is not None:
        workflow[bindings.sampler_node]["inputs"]["seed"] = seed
    return workflow
