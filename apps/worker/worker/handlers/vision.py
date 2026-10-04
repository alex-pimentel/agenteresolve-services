"""Vision tool handlers (OCR, anonymize, alt-text, object counting)."""

from __future__ import annotations

import io
from typing import Any

from common.jsonutil import json_bytes
from common.providers.base import Detection, ProviderUnavailable

from worker.handlers.base import HandlerContext, HandlerResult


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a[:4]
    bx1, by1, bx2, by2 = b[:4]
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def non_max_suppression(detections: list[Detection], iou_threshold: float = 0.5) -> list[Detection]:
    """Greedy NMS across all classes (labels are kept distinct)."""
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.score, reverse=True):
        if any(
            prior.label == detection.label and _iou(prior.bbox, detection.bbox) > iou_threshold
            for prior in kept
        ):
            continue
        kept.append(detection)
    return kept


# --- ocr -------------------------------------------------------------------------


def handle_ocr(ctx: HandlerContext) -> HandlerResult:
    if ctx.ocr is None:
        raise ProviderUnavailable("ocr requires an OCR provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "image/png")
    lang = ctx.params.get("lang")
    blocks = ctx.ocr.extract(raw, content_type=content_type, lang=lang)
    payload = {
        "text": "\n".join(block.text for block in blocks),
        "blocks": [
            {"text": block.text, "bbox": block.bbox, "confidence": block.confidence}
            for block in blocks
        ],
        "lang": lang,
    }
    key = f"results/ocr/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


# --- alttext ---------------------------------------------------------------------


_ALTTEXT_SYSTEM = (
    "You write concise, accessible alt-text. Return ONLY a JSON object: "
    '{"alt": string, "caption": [string], "tags": [string]}.'
)


def handle_alttext(ctx: HandlerContext) -> HandlerResult:
    if ctx.vision is None:
        raise ProviderUnavailable("alttext requires a vision provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "image/png")
    base = ctx.vision.caption(raw, content_type=content_type)

    lang = str(ctx.params.get("lang") or "pt")
    style = str(ctx.params.get("style") or "accessible")
    alt = base
    caption: list[str] = [base]
    tags: list[str] = []

    if ctx.llm is not None:
        from common.jsonutil import parse_json_object

        prompt = (
            f"Base description: {base}\nLanguage: {lang}\nStyle: {style}\n\n"
            "Write the alt-text, one or two captions and tags."
        )
        try:
            data = parse_json_object(ctx.llm.complete(prompt, system=_ALTTEXT_SYSTEM))
            alt = str(data.get("alt") or base)
            caption = [str(item) for item in data.get("caption", [])] or [base]
            tags = [str(item) for item in data.get("tags", [])]
        except ValueError:
            pass

    payload = {"alt": alt, "caption": caption, "tags": tags, "confidence": 0.8, "lang": lang}
    key = f"results/alttext/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


# --- objectcount -----------------------------------------------------------------


def handle_objectcount(ctx: HandlerContext) -> HandlerResult:
    if ctx.vision is None:
        raise ProviderUnavailable("objectcount requires a vision provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "image/png")

    classes_param = ctx.params.get("classes")
    labels = (
        [item.strip() for item in str(classes_param).split(",") if item.strip()]
        if classes_param
        else None
    )
    min_score = float(ctx.params.get("min_score") or 0.0)

    detections = ctx.vision.detect(raw, content_type=content_type, labels=labels)
    detections = non_max_suppression([d for d in detections if d.score >= min_score])

    counts: dict[str, int] = {}
    for detection in detections:
        counts[detection.label] = counts.get(detection.label, 0) + 1

    payload = {
        "counts": counts,
        "total": len(detections),
        "detections": [
            {"class": detection.label, "bbox": detection.bbox, "score": detection.score}
            for detection in detections
        ],
    }
    key = f"results/objectcount/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


# --- anonymize -------------------------------------------------------------------


def _blur_regions(data: bytes, boxes: list[list[float]], mode: str) -> bytes:
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ProviderUnavailable(
            "anonymize requires 'Pillow' to redact pixels. Install it or set VISION_URL."
        ) from exc

    image = Image.open(io.BytesIO(data)).convert("RGB")
    for box in boxes:
        region = tuple(int(round(value)) for value in box[:4])
        if region[2] <= region[0] or region[3] <= region[1]:
            continue
        crop = image.crop(region)
        if mode == "black":
            image.paste(Image.new("RGB", crop.size, (0, 0, 0)), region)
        elif mode == "pixelate":
            small = crop.resize((max(crop.width // 10, 1), max(crop.height // 10, 1)))
            image.paste(small.resize(crop.size, Image.NEAREST), region)
        else:
            image.paste(crop.filter(ImageFilter.GaussianBlur(15)), region)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


_ANONYMIZE_LABELS: dict[str, list[str]] = {
    "faces": ["face", "person"],
    "plates": ["license plate", "car"],
}


def handle_anonymize(ctx: HandlerContext) -> HandlerResult:
    if ctx.vision is None:
        raise ProviderUnavailable("anonymize requires a vision provider")
    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "image/png")
    mode = str(ctx.params.get("mode") or "blur")

    categories_param = ctx.params.get("categories")
    categories = (
        [item.strip() for item in str(categories_param).split(",") if item.strip()]
        if categories_param
        else ["faces", "plates"]
    )

    detections: list[dict[str, Any]] = []
    boxes: list[list[float]] = []
    for category in categories:
        labels = _ANONYMIZE_LABELS.get(category, [category])
        for detection in ctx.vision.detect(raw, content_type=content_type, labels=labels):
            detections.append({"category": category, "bbox": detection.bbox})
            boxes.append(detection.bbox)

    redacted = _blur_regions(raw, boxes, mode)
    key = f"results/anonymize/{ctx.task_id}/result.png"
    return HandlerResult(key=key, data=redacted, content_type="image/png")
