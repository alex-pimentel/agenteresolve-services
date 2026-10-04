"""AskYourDocs: ephemeral RAG with citations.

The index is stored as JSON in the private R2 ``tmp`` bucket (24h lifecycle) so any worker
can answer follow-up questions; nothing is written to Postgres.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from common.jsonutil import json_bytes, parse_json_object
from common.providers.base import EmbeddingsProvider, ProviderUnavailable
from common.sessions import get_session_store
from common.text import chunk_text

from worker.handlers.base import HandlerContext, HandlerResult

_SYSTEM = (
    "You answer questions strictly from the provided context. Cite the source chunk ids "
    'you used. Return ONLY JSON: {"answer": string, "citations": [{"doc": string, '
    '"chunk": number, "excerpt": string}]}. If the answer is not in the context, say so.'
)


def _records_key(session_id: str) -> str:
    return f"sessions/askyourdocs/{session_id}/records.json"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return dot / (na * nb)


def index_documents(
    embeddings: EmbeddingsProvider, documents: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Embed each document chunk and return the indexed records."""
    records: list[dict[str, Any]] = []
    for name, text in documents:
        chunks = chunk_text(text)
        if not chunks:
            continue
        vectors = embeddings.embed(chunks)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            records.append({"doc": name, "chunk": index, "text": chunk, "vector": vector})
    return records


def answer_question(
    llm: object, embeddings: EmbeddingsProvider, records: list[dict[str, Any]], question: str
) -> dict[str, Any]:
    query_vector = embeddings.embed([question])[0]
    ranked = sorted(records, key=lambda r: _cosine(query_vector, r["vector"]), reverse=True)[:5]
    context = "\n\n".join(f"[{r['doc']}#{r['chunk']}] {r['text']}" for r in ranked)
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    try:
        data = parse_json_object(llm.complete(prompt, system=_SYSTEM))  # type: ignore[attr-defined]
    except ValueError:
        data = {"answer": "", "citations": []}
    data["sources"] = [{"doc": r["doc"], "chunk": r["chunk"]} for r in ranked]
    return data


def handle_askyourdocs(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None or ctx.embeddings is None:
        raise ProviderUnavailable("askyourdocs requires LLM and embeddings providers")

    raw = ctx.object_store.get_bytes(ctx.input_key)
    text = raw.decode("utf-8", errors="replace")
    name = str(ctx.params.get("name") or "document")
    question = str(ctx.params.get("question") or "").strip()
    session_id = str(ctx.params.get("session_id") or "") or uuid.uuid4().hex

    if question:
        try:
            records = json.loads(ctx.object_store.get_bytes(_records_key(session_id)))
        except KeyError as exc:
            raise ValueError("Unknown or expired session") from exc
        answer = answer_question(ctx.llm, ctx.embeddings, records, question)
        get_session_store().create(session_id, "askyourdocs", records=len(records))
    else:
        records = index_documents(ctx.embeddings, [(name, text)])
        ctx.object_store.put_bytes(
            _records_key(session_id), json_bytes(records), "application/json"
        )
        get_session_store().create(session_id, "askyourdocs", records=len(records))
        answer = {"answer": "", "citations": [], "sources": []}

    payload = {"session_id": session_id, "chunks": len(records), **answer}
    key = f"results/askyourdocs/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")
