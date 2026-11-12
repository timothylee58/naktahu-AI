"""Multiprocess metrics: /metrics must report every uvicorn worker, not just
the one that answers the scrape.

These run real separate Python processes, because the behaviour under test is
exactly what in-process unit tests cannot see: counters living in different
processes' memory. PROMETHEUS_MULTIPROC_DIR is read by prometheus_client at
import time, so the test process (which already imported it without the
variable) is never used to write or render.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.prometheus_metrics import prune_dead_gauge_files

_API_ROOT = Path(__file__).resolve().parent.parent


def _run(code: str, multiproc_dir: Path) -> str:
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(multiproc_dir)}
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_API_ROOT, env=env, capture_output=True, text=True, timeout=60, check=True,
    )
    return out.stdout


_WRITE_COUNTER = """
from app.core.prometheus_metrics import rag_queries_total
for _ in range(3):
    rag_queries_total.labels(language="en", provider="ilmu").inc()
"""

_WRITE_GAUGE = """
from app.core.prometheus_metrics import http_requests_in_progress
http_requests_in_progress.labels(method="GET").inc()
"""

_RENDER = """
from app.core.prometheus_metrics import render_metrics
print(render_metrics().decode())
"""


def _sample(text: str, prefix: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(prefix)]


def test_counters_from_two_workers_are_summed(tmp_path: Path) -> None:
    _run(_WRITE_COUNTER, tmp_path)  # worker 1
    _run(_WRITE_COUNTER, tmp_path)  # worker 2
    text = _run(_RENDER, tmp_path)  # a third process answering the scrape

    assert _sample(text, "naktahu_rag_queries_total") == [
        'naktahu_rag_queries_total{language="en",provider="ilmu"} 6.0'
    ]


def test_dead_workers_gauge_is_dropped_but_its_counters_are_kept(tmp_path: Path) -> None:
    """A worker that died mid-request must not leave "in progress" stuck above
    zero forever, while its already-served request totals stay counted."""
    _run(_WRITE_COUNTER + _WRITE_GAUGE, tmp_path)  # exits, so its pid is dead
    text = _run(_RENDER, tmp_path)

    assert _sample(text, "naktahu_http_requests_in_progress{") == []
    assert _sample(text, "naktahu_rag_queries_total")[0].endswith(" 3.0")


def test_without_the_env_var_render_is_the_plain_registry() -> None:
    from app.core.prometheus_metrics import REGISTRY, multiprocess_enabled, render_metrics

    assert not multiprocess_enabled()
    assert b"naktahu_http_requests_total" in render_metrics()
    assert REGISTRY is not None


# ── prune_dead_gauge_files ──────────────────────────────────────────────────

def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_prune_removes_only_dead_workers_live_gauge_files(tmp_path: Path) -> None:
    dead, alive = _dead_pid(), os.getpid()
    keep = [
        f"gauge_livesum_{alive}.db",  # running worker's gauge
        f"gauge_max_{dead}.db",  # not a live-mode gauge: file is meant to outlive the worker
        f"counter_{dead}.db",  # cumulative, must survive
        f"histogram_{dead}.db",
    ]
    drop = [f"gauge_livesum_{dead}.db", f"gauge_liveall_{dead}.db"]
    for name in keep + drop:
        (tmp_path / name).write_bytes(b"")

    assert prune_dead_gauge_files(str(tmp_path)) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(keep)


def test_prune_on_empty_directory_is_a_no_op(tmp_path: Path) -> None:
    assert prune_dead_gauge_files(str(tmp_path)) == 0


# ── deployment wiring ───────────────────────────────────────────────────────

def test_start_script_sets_the_dir_before_launching_workers() -> None:
    """Without this the whole change is dead code in production: the variable
    has to be exported before uvicorn imports the app."""
    script = (_API_ROOT / "start.sh").read_text()
    assert "export PROMETHEUS_MULTIPROC_DIR" in script
    assert script.index("export PROMETHEUS_MULTIPROC_DIR") < script.index("exec uvicorn")
    assert "--workers" in script


@pytest.mark.skipif(not (_API_ROOT / "start.sh").exists(), reason="start.sh missing")
def test_start_script_is_valid_posix_sh() -> None:
    subprocess.run(["sh", "-n", str(_API_ROOT / "start.sh")], check=True)
