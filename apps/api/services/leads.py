"""Managed-leads capture — backs POST /api/v1/leads, the /perniagaan-terurus
landing page's lead-capture form (045_managed_leads.sql). Pure insert; no
read/list surface exposed to any client — internal status tracking for the
first managed-service pilot clients happens directly in the Supabase table
editor, not through a UI (see the migration's docstring)."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from supabase import Client


async def create_lead(
    supabase_client: Client,
    *,
    name: str,
    company: Optional[str],
    contact_email: Optional[str],
    contact_phone: Optional[str],
    message: Optional[str],
    referral_source: Optional[str],
) -> dict[str, Any]:
    def _insert() -> dict[str, Any]:
        res = (
            supabase_client.table("managed_leads")
            .insert(
                {
                    "name": name,
                    "company": company,
                    "contact_email": contact_email,
                    "contact_phone": contact_phone,
                    "message": message,
                    "referral_source": referral_source,
                }
            )
            .execute()
        )
        return res.data[0] if res.data else {}

    return await asyncio.to_thread(_insert)
