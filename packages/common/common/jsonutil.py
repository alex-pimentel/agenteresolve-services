"""Helpers for coercing LLM text into JSON and rendering results."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_object(raw: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object from LLM output.

    Strips markdown fences and, failing that, extracts the outermost ``{...}`` block.
    Raises :class:`ValueError` when nothing parseable is found.
    """
    text = raw.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("LLM response did not contain a JSON object") from None
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("LLM response was not a JSON object")
    return parsed


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
