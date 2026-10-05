"""Tests for scripts.ingest_parliament.seed_postcode_seats (migration 054 loader)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.ingest_parliament.seed_postcode_seats import normalise_code, read_rows, upload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("P121", "P121"), ("p121", "P121"), ("P.121", "P121"), (" P 001 ", "P001"),
     ("P222", "P222"), ("P223", None), ("P000", None), ("N.28", None), ("121", None), ("", None)],
)
def test_normalise_code(raw, expected):
    assert normalise_code(raw) == expected


def test_read_rows_validates_dedups_and_restores_leading_zero(tmp_path: Path):
    csv_path = tmp_path / "seats.csv"
    csv_path.write_text(
        "postcode,constituency_code\n"
        "50450,P121\n"
        "50450,P122\n"
        "50450,P121\n"      # duplicate
        "1000,P001\n"       # leading zero lost by a spreadsheet -> 01000
        "5045X,P121\n"      # bad postcode
        "50450,N.28\n",     # state seat, not parliamentary
        encoding="utf-8",
    )
    rows, rejected = read_rows(csv_path, "test-source v1")

    assert rejected == 2
    assert sorted((r["postcode"], r["constituency_code"]) for r in rows) == [
        ("01000", "P001"), ("50450", "P121"), ("50450", "P122"),
    ]
    assert all(r["source"] == "test-source v1" for r in rows)


def test_read_rows_requires_columns(tmp_path: Path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("zip,seat\n50450,P121\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        read_rows(csv_path, "s")


def test_upload_batches_and_replaces_by_source():
    sb = MagicMock()
    rows = [{"postcode": f"{i:05d}", "constituency_code": "P001", "source": "s"} for i in range(1200)]

    assert upload(sb, rows, "s", replace=True) == 1200
    table = sb.table.return_value
    table.delete.return_value.eq.assert_called_once_with("source", "s")
    assert [len(c.args[0]) for c in table.upsert.call_args_list] == [500, 500, 200]
