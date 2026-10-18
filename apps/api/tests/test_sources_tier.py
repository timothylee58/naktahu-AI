"""Registry guard: the Official/Community badge is only as honest as the
`tier` on each Source, so keep it consistent with what the registry itself says."""
from __future__ import annotations

from urllib.parse import urlparse

from scripts.sources import SOURCES


def test_every_source_has_a_valid_tier():
    assert {s.tier for s in SOURCES} <= {"official", "community"}


def test_sources_labelled_not_government_are_community():
    flagged = [s for s in SOURCES if "not a government body" in s.ministry.lower()]
    assert flagged, "expected at least one explicitly non-government source"
    assert all(s.tier == "community" for s in flagged), [s.name for s in flagged if s.tier != "community"]


def test_gov_my_hosts_are_never_community():
    wrong = [s.name for s in SOURCES if urlparse(s.url).hostname and urlparse(s.url).hostname.endswith("gov.my") and s.tier != "official"]
    assert wrong == []


def test_known_community_hosts_match_the_migration_backfill():
    """059_source_tier.sql backfills these two hosts as community; if the
    registry's community set changes, the migration's backfill must too."""
    community_hosts = {urlparse(s.url).hostname.removeprefix("www.") for s in SOURCES if s.tier == "community"}
    assert community_hosts == {"mymp.org.my", "mban.com.my"}
