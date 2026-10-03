"""Handler context and result types shared by all tool handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.providers.base import LLMProvider
from common.storage import ObjectStore


@dataclass
class HandlerResult:
    key: str
    data: bytes
    content_type: str = "application/octet-stream"


@dataclass
class HandlerContext:
    task_id: str
    slug: str
    object_store: ObjectStore
    input_key: str
    params: dict[str, Any] = field(default_factory=dict)
    llm: LLMProvider | None = None
    embeddings: Any | None = None
    ocr: Any | None = None
    vision: Any | None = None
    audio: Any | None = None
    tts: Any | None = None
