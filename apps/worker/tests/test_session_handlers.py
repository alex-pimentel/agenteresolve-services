"""Handler unit tests for session tools: AskYourDocs, DataChat and VoiceChat."""

from __future__ import annotations

import json

import pytest
from common.jsonutil import json_bytes
from common.providers.base import ProviderUnavailable, Transcription, TranscriptSegment
from common.providers.llm import FakeLLM
from common.sessions import SessionStore, set_session_store
from worker.handlers.base import HandlerContext
from worker.handlers.rag import answer_question, handle_askyourdocs, index_documents


class _Store:
    def __init__(self, data: bytes = b"") -> None:
        self._data = data
        self.puts: dict[str, bytes] = {}

    def get_bytes(self, key: str) -> bytes:
        return self._data

    def put_bytes(self, key: str, data: bytes, content_type: str = "") -> str:
        self.puts[key] = data
        return key


class _Embeddings:
    """Deterministic embeddings: score by token overlap."""

    is_remote = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float("apple" in t), float("banana" in t), 1.0] for t in texts]


@pytest.fixture(autouse=True)
def _sessions():
    set_session_store(SessionStore())
    yield
    set_session_store(SessionStore())


def _ctx(store: _Store, **overrides: object) -> HandlerContext:
    base: dict[str, object] = {
        "task_id": "t1",
        "slug": "askyourdocs",
        "object_store": store,
        "input_key": "in",
        "params": {},
    }
    base.update(overrides)
    return HandlerContext(**base)  # type: ignore[arg-type]


# --- askyourdocs -----------------------------------------------------------------


def test_index_documents_chunks_and_embeds() -> None:
    records = index_documents(_Embeddings(), [("doc", "apple banana " * 200)])
    assert records
    assert all("vector" in record for record in records)


def test_askyourdocs_indexes_then_answers() -> None:
    llm = FakeLLM(
        json.dumps({"answer": "42", "citations": [{"doc": "doc", "chunk": 0, "excerpt": "apple"}]})
    )

    class _PersistentStore(_Store):
        def __init__(self) -> None:
            super().__init__(b"apple banana")
            self._objects: dict[str, bytes] = {}

        def get_bytes(self, key: str) -> bytes:
            if key in self._objects:
                return self._objects[key]
            return self._data

        def put_bytes(self, key: str, data: bytes, content_type: str = "") -> str:
            self._objects[key] = data
            self.puts[key] = data
            return key

    store = _PersistentStore()
    index_ctx = _ctx(store, llm=llm, embeddings=_Embeddings(), params={"name": "doc"})
    first = json.loads(handle_askyourdocs(index_ctx).data)
    session_id = first["session_id"]

    ask_ctx = _ctx(
        store,
        task_id="t2",
        llm=llm,
        embeddings=_Embeddings(),
        params={"question": "what fruit?", "session_id": session_id},
    )
    payload = json.loads(handle_askyourdocs(ask_ctx).data)
    assert payload["answer"] == "42"
    assert payload["chunks"] >= 1


def test_askyourdocs_requires_providers() -> None:
    with pytest.raises(ProviderUnavailable):
        handle_askyourdocs(_ctx(_Store(b"x")))


def test_answer_question_ranks_sources() -> None:
    records = [
        {"doc": "d", "chunk": 0, "text": "apple", "vector": [1.0, 0.0, 1.0]},
        {"doc": "d", "chunk": 1, "text": "banana", "vector": [0.0, 1.0, 1.0]},
    ]
    llm = FakeLLM(json.dumps({"answer": "", "citations": []}))
    result = answer_question(llm, _Embeddings(), records, "apple")
    assert result["sources"][0]["chunk"] == 0


# --- datachat --------------------------------------------------------------------


def test_datachat_loads_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    from worker.handlers import data as mod

    class _Frame:
        columns = ["month", "total"]
        dtypes = {"month": "object", "total": "int64"}

        def __len__(self) -> int:
            return 2

        def head(self, n: int):
            return self

        def astype(self, _: str):
            return self

        def to_dict(self, orient: str):
            return [{"month": "jan", "total": "10"}]

    monkeypatch.setattr(mod, "load_dataframe", lambda data, filename: _Frame())
    ctx = _ctx(_Store(b"month,total\njan,10"), slug="datachat", llm=FakeLLM("{}"))
    payload = json.loads(mod.handle_datachat(ctx).data)
    assert payload["schema"]["columns"] == ["month", "total"]
    assert payload["session_id"]


def test_datachat_sandbox_blocks_forbidden_code() -> None:
    from worker.handlers import data as mod

    with pytest.raises(ValueError):
        mod.run_sandboxed(object(), "__import__('os')")


def test_datachat_requires_llm() -> None:
    from worker.handlers import data as mod

    with pytest.raises(ProviderUnavailable):
        mod.handle_datachat(_ctx(_Store(b"x"), slug="datachat"))


# --- voicechat -------------------------------------------------------------------


class _Audio:
    is_remote = True

    def transcribe(self, data: bytes, *, content_type: str, lang: str | None = None):
        return Transcription(text="hi", segments=[TranscriptSegment(0, 1, "hi")], language=lang)

    def enhance(self, data: bytes, *, content_type: str, mode: str = "denoise") -> bytes:
        return b""


class _Tts:
    is_remote = True

    def synthesize(self, text: str, **_: object) -> bytes:
        return b"AUDIO:" + text.encode()


def test_voicechat_runs_a_turn() -> None:
    from worker.handlers.voice import handle_voicechat

    store = _Store(b"audio")
    ctx = _ctx(
        store,
        slug="voicechat",
        audio=_Audio(),
        tts=_Tts(),
        llm=FakeLLM("Hello there"),
        params={"persona": "tutor", "lang": "en"},
    )
    result = handle_voicechat(ctx)
    assert result.data == b"AUDIO:Hello there"
    assert result.key == "results/voicechat/t1/reply.mp3"
    assert "results/voicechat/t1/turn.json" in store.puts


def test_voicechat_requires_all_providers() -> None:
    from worker.handlers.voice import handle_voicechat

    with pytest.raises(ProviderUnavailable):
        handle_voicechat(_ctx(_Store(b"a"), slug="voicechat"))


def test_json_bytes_roundtrip() -> None:
    assert json.loads(json_bytes({"x": 1})) == {"x": 1}
