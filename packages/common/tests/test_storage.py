import pytest
from common.storage import InMemoryObjectStore


def test_put_and_get_roundtrip() -> None:
    store = InMemoryObjectStore()
    store.put_bytes("a/b.txt", b"hello", content_type="text/plain")
    assert store.get_bytes("a/b.txt") == b"hello"


def test_get_missing_raises() -> None:
    store = InMemoryObjectStore()
    with pytest.raises(KeyError):
        store.get_bytes("nope")


def test_presigned_url_contains_key() -> None:
    store = InMemoryObjectStore()
    store.put_bytes("results/x.txt", b"x")
    url = store.presigned_get_url("results/x.txt", expires_in=60)
    assert isinstance(url, str)
    assert "results/x.txt" in url
