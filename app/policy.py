"""Conservative request checks that complement human review."""

from __future__ import annotations

import re


class PolicyViolation(ValueError):
    """Raised when a request is outside the supported safety boundary."""


BLOCKED_TERMS = (
    "minor",
    "underage",
    "child",
    "schoolgirl",
    "young-looking",
    "real person",
    "celebrity",
    "public figure",
    "deepfake",
    "face swap",
    "未成年",
    "儿童",
    "真人",
    "明星",
    "公众人物",
    "换脸",
)


def validate_request(
    prompt: str,
    character_id: str,
    synthetic_character_confirmed: bool,
    rights_confirmed: bool,
) -> None:
    if not synthetic_character_confirmed:
        raise PolicyViolation("synthetic character confirmation is required")
    if not rights_confirmed:
        raise PolicyViolation("rights confirmation is required")
    if not 12 <= len(prompt.strip()) <= 1500:
        raise PolicyViolation("prompt must be between 12 and 1500 characters")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", character_id):
        raise PolicyViolation("invalid character_id")
    normalized = prompt.casefold()
    if any(term.casefold() in normalized for term in BLOCKED_TERMS):
        raise PolicyViolation("request rejected by safety policy")
