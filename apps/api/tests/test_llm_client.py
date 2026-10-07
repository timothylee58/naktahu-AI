"""Tests for app.services.llm_client.extract_json_object."""
from __future__ import annotations

from app.services.llm_client import extract_json_object


def test_extract_json_object_plain() -> None:
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_object_in_markdown_fence() -> None:
    raw = '```json\n{"a": 1, "b": "two"}\n```'
    assert extract_json_object(raw) == {"a": 1, "b": "two"}


def test_extract_json_object_with_trailing_commentary_containing_brace() -> None:
    """The bug this helper replaces: a naive greedy regex (r'\\{.*\\}')
    matches from the first '{' to the LAST '}' anywhere in the string, so
    any trailing text containing a brace corrupts the match and json.loads
    fails with "Extra data" — silently discarding a correct result.
    JSONDecoder.raw_decode parses only the first balanced object and
    ignores everything after it."""
    raw = '{"harmful": false, "reason": "benign query"} Hope that helps! {smile}'
    assert extract_json_object(raw) == {"harmful": False, "reason": "benign query"}


def test_extract_json_object_no_json_present() -> None:
    assert extract_json_object("not json at all") == {}


def test_extract_json_object_malformed_json() -> None:
    assert extract_json_object("{not: valid, json}") == {}


def test_extract_json_object_top_level_array_returns_empty() -> None:
    """Only a JSON *object* is a valid classifier response — a top-level
    array (or any other JSON type) is not the shape callers expect and
    must not be silently returned as if it were a dict."""
    assert extract_json_object('["a", "b"]') == {}


def test_extract_json_object_nested_braces_in_value() -> None:
    """A JSON object whose own value happens to contain braces must still
    parse correctly — raw_decode is brace-depth-aware, unlike a regex."""
    raw = '{"domain": "government", "intent": "explain the {budget} process"}'
    assert extract_json_object(raw) == {
        "domain": "government",
        "intent": "explain the {budget} process",
    }
