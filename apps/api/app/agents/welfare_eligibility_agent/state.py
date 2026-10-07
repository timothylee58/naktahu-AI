"""Welfare Eligibility Agent state — single-shot cost-of-living / social
assistance scheme matching against madani_scheme (migration 037).

The 14-field WelfareProfile shape below was reported by a user as the
intake fields on ihsanmadani.gov.my's "Semak Bantuan Khusus" checker —
this repo's sandbox cannot reach that domain (network egress blocked, see
scripts/sources.py's docstring) so the exact field list/wording has NOT
been independently verified against the live site. It's a reasonable,
common-sense shape for a Malaysian welfare-intake form regardless (matches
the general eKasih-style pattern this kind of checker typically uses), so
it's used as the working schema — but treat the exact field set as
"reported, pending verification," not confirmed official spec. If it turns
out to be wrong in some particular once someone can verify the real page,
fixing it here is a schema-shape change, not a rewrite.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

EmploymentStatus = Literal["employed", "self_employed", "unemployed", "retired", "student"]
EducationLevel = Literal["none", "primary", "secondary", "spm", "diploma", "degree", "postgrad"]
MaritalStatus = Literal["single", "married", "divorced", "widowed"]
HousingOwnership = Literal["own", "rented", "family_owned", "no_fixed_housing"]
Gender = Literal["male", "female"]
EthnicGroup = Literal["malay", "chinese", "indian", "bumiputera_sabah_sarawak", "other"]


class WelfareProfile(TypedDict, total=False):
    # Demographics
    birth_year: int
    gender: Gender
    state: str                    # matches STATE_OPTIONS-style slugs used elsewhere in this app (kl, penang, johor, ...)
    ethnic_group: EthnicGroup
    marital_status: MaritalStatus
    # Household
    individual_monthly_income_myr: float
    household_monthly_income_myr: float
    dependents_children: int      # <=17
    dependents_elderly: int       # >=60
    dependents_oku: int           # disabled dependents
    dependents_chronic_ill: int   # bedridden/chronic-illness dependents
    # Status
    employment_status: EmploymentStatus
    education_level: EducationLevel
    is_oku: bool                  # applicant's own disability status
    housing_ownership: HousingOwnership


class MatchedScheme(TypedDict, total=False):
    scheme_name: str
    category: str
    scope: str
    description: str
    implementing_agency: str
    source_url: str
    aggregator_url: str | None
    match_reasons: list[str]


class WelfareState(TypedDict, total=False):
    session_id: str
    user_id: str | None
    language: str
    profile: WelfareProfile
    matched_schemes: list[MatchedScheme]
    no_schemes_loaded: bool       # True whenever madani_scheme has zero active rows for the matched category/scope — an honest "nothing to match against yet" signal, never fabricated results
    summary: str
    error: str | None
    # Internal, stripped from any public-facing output (see agent_runner._public_output)
    _supabase: Any
