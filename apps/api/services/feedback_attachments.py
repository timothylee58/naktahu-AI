"""Private-bucket storage for verified feedback screenshots (migration 058)."""
from __future__ import annotations

import asyncio
import re
import uuid

from supabase import Client

from services.feedback_guard import VerifiedImage

BUCKET = "feedback-attachments"

# <user uuid>/<32 hex>.<ext> — the user-id prefix is what lets a submit
# endpoint prove an attachment_path belongs to the caller without a DB read.
ATTACHMENT_PATH_PATTERN = r"^[0-9a-fA-F-]{36}/[0-9a-f]{32}\.(png|jpg|webp)$"
_PATH_RE = re.compile(ATTACHMENT_PATH_PATTERN)


def attachment_belongs_to(path: str, user_id: str) -> bool:
    return bool(_PATH_RE.match(path)) and path.split("/", 1)[0].lower() == user_id.lower()


async def store_attachment(supabase_client: Client, *, user_id: str, image: VerifiedImage) -> str:
    path = f"{user_id}/{uuid.uuid4().hex}.{image.extension}"

    def _upload() -> None:
        supabase_client.storage.from_(BUCKET).upload(
            path, image.data, {"content-type": image.content_type}
        )

    await asyncio.to_thread(_upload)
    return path
