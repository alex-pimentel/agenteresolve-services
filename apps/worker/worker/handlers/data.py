"""DataChat: natural-language questions over CSV/XLSX with a sandboxed pandas step."""

from __future__ import annotations

import json
import uuid
from typing import Any

from common.jsonutil import json_bytes, parse_json_object
from common.providers.base import ProviderUnavailable
from common.storage import get_bytes_or_none

from worker.handlers.base import HandlerContext, HandlerResult

_PLAN_SYSTEM = (
    "You translate a question about a pandas DataFrame into a SINGLE safe python expression "
    "that computes the answer. You may only use pandas operations on a variable named `df` "
    "and builtins. Do NOT import anything, access files, network or os. Return ONLY JSON: "
    '{"code": string, "explanation": string, "chart": {"type": "bar"|"line"|"none", '
    '"x": string, "y": string}}.'
)

_FORBIDDEN = ("import", "open(", "exec", "eval", "__", "os.", "sys.", "subprocess", "socket")

# A small, explicit set of side-effect-free builtins so LLM-generated expressions can use
# len/sum/min/... Everything else (imports, open, getattr, dunders) stays unavailable.
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def load_dataframe(data: bytes, filename: str) -> Any:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ProviderUnavailable(
            "datachat requires 'pandas'. Install it in the text worker image."
        ) from exc

    import io

    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    return pd.read_csv(io.BytesIO(data))


def dataframe_schema(frame: Any) -> dict[str, Any]:
    return {
        "columns": [str(column) for column in frame.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "rows": int(len(frame)),
        "head": frame.head(5).astype(str).to_dict(orient="records"),
    }


def run_sandboxed(frame: Any, code: str) -> Any:
    if any(token in code for token in _FORBIDDEN):
        raise ValueError("Generated code contained a forbidden operation")
    # The expression runs with only ``df`` and ``pd`` in scope; builtins are stripped and
    # the token blocklist above rejects imports/attribute access into dangerous modules.
    import pandas as pd

    scope: dict[str, Any] = {"df": frame, "pd": pd}
    # Restricted eval over a fixed, validated expression in a stripped scope.
    return eval(code, {"__builtins__": _SAFE_BUILTINS}, scope)  # noqa: S307  # nosec B307


def _serialize(value: Any) -> Any:
    import pandas as pd

    if isinstance(value, pd.DataFrame):
        return {
            "table": value.reset_index().astype(str).to_dict(orient="records"),
            "columns": [str(c) for c in value.reset_index().columns],
        }
    if isinstance(value, pd.Series):
        return {"table": value.reset_index().astype(str).to_dict(orient="records")}
    if isinstance(value, (int, float, str, bool)) or value is None:
        return {"value": value}
    return {"value": str(value)}


def _data_key(session_id: str) -> str:
    return f"sessions/datachat/{session_id}/data.bin"


def _meta_key(session_id: str) -> str:
    return f"sessions/datachat/{session_id}/meta.json"


def _stored_filename(ctx: HandlerContext, session_id: str) -> str:
    raw = get_bytes_or_none(ctx.object_store, _meta_key(session_id))
    if raw is None:
        return "data.csv"
    try:
        return str(json.loads(raw).get("filename") or "data.csv")
    except (ValueError, AttributeError):
        return "data.csv"


def handle_datachat(ctx: HandlerContext) -> HandlerResult:
    if ctx.llm is None:
        raise ProviderUnavailable("datachat requires an LLM provider")

    filename = str(ctx.params.get("filename") or "data.csv")
    question = str(ctx.params.get("question") or "").strip()
    session_id = str(ctx.params.get("session_id") or "")

    if question:
        # Follow-up turn: reload the dataset from object storage so any worker process
        # (and any replica) can answer, not just the one that indexed it in memory.
        if not session_id:
            raise ValueError("Unknown or expired session")
        stored = get_bytes_or_none(ctx.object_store, _data_key(session_id))
        if stored is None:
            raise ValueError("Unknown or expired session")
        filename = _stored_filename(ctx, session_id)
        frame = load_dataframe(stored, filename)
        schema = dataframe_schema(frame)
    else:
        raw = ctx.object_store.get_bytes(ctx.input_key)
        frame = load_dataframe(raw, filename)
        schema = dataframe_schema(frame)
        session_id = session_id or uuid.uuid4().hex
        ctx.object_store.put_bytes(_data_key(session_id), raw, "application/octet-stream")
        ctx.object_store.put_bytes(
            _meta_key(session_id), json_bytes({"filename": filename}), "application/json"
        )

    result: dict[str, Any]
    if question:
        prompt = (
            f"DataFrame columns/dtypes: {json.dumps(schema)}\n"
            f"Sample rows: {json.dumps(schema['head'])}\n"
            f"Question: {question}"
        )
        plan = parse_json_object(ctx.llm.complete(prompt, system=_PLAN_SYSTEM))
        code = str(plan.get("code") or "")
        try:
            value = run_sandboxed(frame, code)
            result = {**_serialize(value), "code": code, "explanation": plan.get("explanation", "")}
        except Exception as exc:  # noqa: BLE001 - reported to the user
            result = {"error": f"{type(exc).__name__}: {exc}", "code": code}
        result["chart"] = plan.get("chart", {"type": "none"})
    else:
        result = {"schema": schema}

    payload = {"session_id": session_id, "question": question, **result}
    key = f"results/datachat/{ctx.task_id}/result.json"
    return HandlerResult(key=key, data=json_bytes(payload), content_type="application/json")
