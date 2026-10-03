"""Object storage abstraction.

Production uses Cloudflare R2 (S3-compatible, private ``tmp`` bucket with a 24h
lifecycle). Development/tests fall back to an in-memory store so no external service is
required. Results are never served publicly: the gateway hands out short-lived presigned
GET URLs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from common.config import get_settings


@runtime_checkable
class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str = ...) -> str: ...

    def get_bytes(self, key: str) -> bytes: ...

    def presigned_get_url(self, key: str, expires_in: int = ...) -> str: ...


class InMemoryObjectStore:
    """Non-persistent store used for local development and tests."""

    def __init__(self, bucket: str = "tmp") -> None:
        self.bucket = bucket
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self._objects[key] = (data, content_type)
        return key

    def get_bytes(self, key: str) -> bytes:
        if key not in self._objects:
            raise KeyError(key)
        return self._objects[key][0]

    def presigned_get_url(self, key: str, expires_in: int = 3_600) -> str:
        return f"memory://{self.bucket}/{key}?expires={expires_in}"


class R2ObjectStore:
    """Cloudflare R2 (or any S3-compatible endpoint) store."""

    def __init__(
        self,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str = "tmp",
        region: str = "auto",
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    def presigned_get_url(self, key: str, expires_in: int = 3_600) -> str:
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url


def build_object_store() -> ObjectStore:
    settings = get_settings()
    if settings.r2_endpoint and settings.r2_access_key_id and settings.r2_secret_access_key:
        return R2ObjectStore(
            endpoint=settings.r2_endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            region=settings.r2_region,
        )
    return InMemoryObjectStore(bucket=settings.r2_bucket)


_object_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _object_store
    if _object_store is None:
        _object_store = build_object_store()
    return _object_store


def set_object_store(store: ObjectStore) -> None:
    global _object_store
    _object_store = store


def reset_object_store() -> None:
    global _object_store
    _object_store = None
