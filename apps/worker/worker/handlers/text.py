"""Text/LLM tool handlers.

Each handler reads its input from the ephemeral object store, calls the injected LLM (and
OCR where needed) provider, and returns a result written to R2 ``tmp``. No user content is
persisted outside the object store.
"""

from __future__ import annotations

from typing import Any

from common.jsonutil import json_bytes, parse_json_object
from common.providers.base import ProviderUnavailable
from common.text import extract_document_text

from worker.handlers.base import HandlerContext, HandlerResult

# --- docuextract -----------------------------------------------------------------

_DOCUEXTRACT_SCHEMAS: dict[str, str] = {
    "invoice": (
        '{"vendor": string, "invoice_number": string, "date": string, "currency": string, '
        '"line_items": [{"description": string, "quantity": number, "unit_price": number, '
        '"total": number}], "subtotal": number, "tax": number, "total": number}'
    ),
    "contract": (
        '{"parties": [string], "effective_date": string, "term": string, '
        '"obligations": [string], "termination": string, "value": string}'
    ),
    "receipt": (
        '{"merchant": string, "date": string, "items": [{"name": string, "price": number}], '
        '"total": number, "payment_method": string}'
    ),
    "auto": ('{"title": string, "summary": string, "fields": {string: any}, "entities": [string]}'),
}

_DOCUEXTRACT_SYSTEM = (
    "You extract structured data from documents. Return ONLY a valid JSON object that "
    "matches the requested schema, with no prose or markdown fences."
)


def handle_docuextract(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("docuextract requires an LLM provider")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "application/pdf")
    schema_name = str(ctx.params.get("schema") or "auto")
    if schema_name not in _DOCUEXTRACT_SCHEMAS:
        schema_name = "auto"

    text, used_ocr = extract_document_text(
        raw, content_type=content_type, ocr=ctx.ocr, lang=ctx.params.get("lang")
    )
    if not text.strip():
        raise ValueError("No text could be extracted from the document")

    schema = _DOCUEXTRACT_SCHEMAS[schema_name]
    prompt = (
        f"Schema name: {schema_name}\nJSON schema: {schema}\n\n"
        f"Document text:\n{text}\n\nReturn the JSON object."
    )
    response = ctx.llm.complete(prompt, system=_DOCUEXTRACT_SYSTEM, temperature=0.0)
    try:
        data = parse_json_object(response)
    except ValueError:
        repair = (
            f"Your previous answer was not valid JSON:\n{response}\n\n"
            f"Return ONLY valid JSON matching this schema: {schema}"
        )
        data = parse_json_object(ctx.llm.complete(repair, system=_DOCUEXTRACT_SYSTEM))

    payload = {
        "schema": schema_name,
        "used_ocr": used_ocr,
        "confidence": 0.9 if not used_ocr else 0.7,
        "text": text,
        "data": data,
    }
    key = f"results/docuextract/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


# --- feedback --------------------------------------------------------------------


def _feedback_items(raw_text: str, params: dict[str, Any]) -> list[dict[str, str]]:
    items_param = params.get("items")
    if isinstance(items_param, str) and items_param.strip():
        import json

        loaded = json.loads(items_param)
        if not isinstance(loaded, list):
            raise ValueError("'items' must be a JSON array")
        return [{"id": str(item.get("id", i)), "text": str(item)} for i, item in enumerate(loaded)]

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return [{"id": str(index), "text": line} for index, line in enumerate(lines)]


_FEEDBACK_SYSTEM = (
    "You classify customer feedback. Return ONLY a JSON object with keys: "
    '{"items": [{"id": string, "sentiment": "positive"|"negative"|"neutral", '
    '"topics": [string], "urgency": "low"|"medium"|"high"}], "summary": string}. '
    "One entry in items per input item, preserving ids."
)


def handle_feedback(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("feedback requires an LLM provider")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    text = raw.decode("utf-8", errors="replace")
    items = _feedback_items(text, ctx.params)
    if not items:
        raise ValueError("No feedback items provided")
    if len(items) > 1000:
        raise ValueError("Too many feedback items (max 1000)")

    lines = "\n".join(f"{item['id']}: {item['text']}" for item in items)
    prompt = f"Classify each of these feedback items:\n{lines}"
    data = parse_json_object(ctx.llm.complete(prompt, system=_FEEDBACK_SYSTEM))

    classified = data.get("items", [])
    counts: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}
    for item in classified:
        sentiment = str(item.get("sentiment", "neutral"))
        if sentiment in counts:
            counts[sentiment] += 1

    payload = {
        "items": classified,
        "summary": data.get("summary", ""),
        "sentiment_counts": counts,
        "total": len(classified),
    }
    key = f"results/feedback/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")


# --- seo -------------------------------------------------------------------------


_SEO_SYSTEM = (
    "You are an SEO strategist. Return ONLY a JSON object with keys: "
    '{"title": string, "meta_description": string, "outline": [string], '
    '"body": string, "social": {"twitter": string, "linkedin": string, "instagram": string}, '
    '"keywords": [string]}.'
)


def _ssrf_safe_fetch(url: str, timeout: float = 10.0) -> str:
    import ipaddress
    import socket
    from urllib.parse import urlparse

    import httpx
    from common.config import get_settings

    settings = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"Unsupported URL: {url!r}")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {parsed.hostname}") from exc

    if settings.ssrf_block_private:
        for info in addresses:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("URL resolves to a private/internal address (blocked)")

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def handle_seo(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("seo requires an LLM provider")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    topic = raw.decode("utf-8", errors="replace").strip()
    url = str(ctx.params.get("url") or "").strip()
    if url:
        from common.config import get_settings

        topic = _ssrf_safe_fetch(url, timeout=get_settings().fetch_timeout)
    elif not topic:
        raise ValueError("Either 'text'/'topic' or 'url' is required")

    lang = str(ctx.params.get("lang") or "pt")
    tone = str(ctx.params.get("tone") or "neutral")
    keyword = str(ctx.params.get("keyword") or "")

    prompt = (
        f"Language: {lang}\nTone: {tone}\nPrimary keyword: {keyword}\n\n"
        f"Source material:\n{topic}\n\nProduce the full SEO package."
    )
    data = parse_json_object(ctx.llm.complete(prompt, system=_SEO_SYSTEM))
    data["lang"] = lang
    data["keyword"] = keyword

    key = f"results/seo/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(data), content_type="application/json")


# --- contracts -------------------------------------------------------------------


_CONTRACTS_SYSTEM = (
    "You review contracts to surface risks, relevant clauses and obligations. Return ONLY "
    'a JSON object: {"risks": [{"type": string, "severity": "low"|"medium"|"high", '
    '"clause": string, "excerpt": string, "note": string}], "summary": string}. '
    "Each finding must quote a short excerpt from the contract."
)


def handle_contracts(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("contracts requires an LLM provider")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    content_type = str(ctx.params.get("content_type") or "application/pdf")
    text, used_ocr = extract_document_text(
        raw, content_type=content_type, ocr=ctx.ocr, lang=ctx.params.get("lang")
    )
    if not text.strip():
        raise ValueError("No text could be extracted from the contract")

    prompt = f"Contract text:\n{text}\n\nList the risks, clauses and obligations."
    data = parse_json_object(ctx.llm.complete(prompt, system=_CONTRACTS_SYSTEM))

    payload = {
        "disclaimer": "Apoio à decisão. Não é aconselhamento jurídico.",
        "used_ocr": used_ocr,
        "risks": data.get("risks", []),
        "summary": data.get("summary", ""),
    }
    key = f"results/contracts/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")
