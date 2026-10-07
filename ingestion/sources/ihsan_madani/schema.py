"""Pydantic schema for a single Ihsan MADANI scheme record.

Kept separate from apps/api's document_chunks / madani_scheme shapes —
this is the RAW scrape output. Mapping this into madani_scheme's DB
columns (and running it through the injection scan per CLAUDE.md's
ingestion rule) is a separate, later step, not this module's job.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "umum", "kesihatan", "makanan", "pendapatan",
    "pendidikan", "pengangkutan", "perumahan", "utiliti",
]


class MadaniScheme(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    category: Category
    # "federal" or "state:<slug>" (e.g. "state:selangor") — parsed from a
    # title prefix by scraper.py's parse_scope(), never guessed.
    scope: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=20000)
    implementing_agency: str | None = Field(default=None, max_length=300)
    source_url: str = Field(..., min_length=1, max_length=2000)
    aggregator_url: str = Field(..., min_length=1, max_length=2000)
    last_verified: date
    effective_date: date | None = None
    superseded_by: str | None = Field(default=None, max_length=2000)
