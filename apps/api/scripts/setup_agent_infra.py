"""Idempotent agent infrastructure checks (storage bucket) on API startup."""
from __future__ import annotations

from typing import Any

import structlog

from core.config import settings

log = structlog.get_logger(__name__)


def ensure_storage_bucket(supabase_client: Any | None) -> None:
    """Create the generated-documents bucket when missing (migration 012 is preferred)."""
    if supabase_client is None:
        return

    bucket = settings.supabase_storage_bucket.strip()
    if not bucket:
        return

    try:
        existing = supabase_client.storage.list_buckets()
        names = {b.name for b in existing}
        if bucket in names:
            log.info("storage_bucket_ok", bucket=bucket)
            return
    except Exception as exc:
        log.warning("storage_bucket_list_failed", error=str(exc))

    try:
        supabase_client.storage.create_bucket(
            bucket,
            options={
                "public": False,
                "file_size_limit": 52_428_800,
                "allowed_mime_types": ["application/pdf"],
            },
        )
        log.info("storage_bucket_created", bucket=bucket)
    except Exception as exc:
        log.warning("storage_bucket_create_failed", bucket=bucket, error=str(exc))
