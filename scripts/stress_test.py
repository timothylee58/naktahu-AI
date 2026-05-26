"""
Stress test for the NakTahu AI LLM API.

Tests the /api/v1/query SSE endpoint under concurrent load.

Usage:
    python scripts/stress_test.py [--url URL] [--concurrency N] [--total N] [--timeout S]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

BASE_URL = "http://localhost:8000"

QUERIES = [
    {"query": "Berapa kadar cukai pendapatan individu di Malaysia?", "language": "bm", "domain": "tax"},
    {"query": "What is the EPF contribution rate for employees?", "language": "en", "domain": "epf"},
    {"query": "Bagaimana cara mendaftarkan syarikat Sdn Bhd?", "language": "bm", "domain": "business"},
    {"query": "What are the SPM compulsory subjects?", "language": "en", "domain": "education"},
    {"query": "Di mana saya boleh dapatkan rawatan percuma?", "language": "bm", "domain": "health"},
    {"query": "How do I renew my Malaysian passport?", "language": "en", "domain": "immigration"},
    {"query": "Apakah kadar RPGT untuk hartanah?", "language": "bm", "domain": "tax"},
    {"query": "What is the MM2H programme requirements?", "language": "en", "domain": "immigration"},
]


@dataclass
class RequestResult:
    query: str
    success: bool
    duration_ms: float
    status_code: Optional[int] = None
    token_count: int = 0
    got_done: bool = False
    error: Optional[str] = None


@dataclass
class Stats:
    results: list[RequestResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def successes(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failures(self) -> int:
        return self.total - self.successes

    @property
    def success_rate(self) -> float:
        return self.successes / self.total * 100 if self.total else 0

    @property
    def durations(self) -> list[float]:
        return [r.duration_ms for r in self.results if r.success]

    def percentile(self, p: float) -> float:
        d = sorted(self.durations)
        if not d:
            return 0
        idx = int(len(d) * p / 100)
        return d[min(idx, len(d) - 1)]

    def print_report(self) -> None:
        d = self.durations
        print("\n" + "=" * 60)
        print("STRESS TEST RESULTS")
        print("=" * 60)
        print(f"  Total requests  : {self.total}")
        print(f"  Successes       : {self.successes} ({self.success_rate:.1f}%)")
        print(f"  Failures        : {self.failures}")
        if d:
            print(f"\n  Latency (ms) — successful requests only:")
            print(f"    Min     : {min(d):.0f}")
            print(f"    Median  : {statistics.median(d):.0f}")
            print(f"    Mean    : {statistics.mean(d):.0f}")
            print(f"    p90     : {self.percentile(90):.0f}")
            print(f"    p99     : {self.percentile(99):.0f}")
            print(f"    Max     : {max(d):.0f}")
            avg_tokens = statistics.mean(r.token_count for r in self.results if r.success)
            print(f"    Avg tokens/response: {avg_tokens:.0f}")
        if self.failures:
            print(f"\n  Failure breakdown:")
            errors: dict[str, int] = {}
            for r in self.results:
                if not r.success:
                    key = r.error or f"HTTP {r.status_code}"
                    errors[key] = errors.get(key, 0) + 1
            for err, count in sorted(errors.items(), key=lambda x: -x[1]):
                print(f"    {count}x  {err}")
        print("=" * 60)


async def make_request(
    client: httpx.AsyncClient,
    payload: dict,
    timeout: float,
) -> RequestResult:
    start = time.perf_counter()
    token_count = 0
    got_done = False
    try:
        async with client.stream(
            "POST",
            "/api/v1/query",
            json=payload,
            timeout=timeout,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            if resp.status_code != 200:
                elapsed = (time.perf_counter() - start) * 1000
                return RequestResult(
                    query=payload["query"][:40],
                    success=False,
                    duration_ms=elapsed,
                    status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}",
                )
            async for line in resp.aiter_lines():
                if line.startswith("event: token"):
                    token_count += 1
                elif line.startswith("event: done"):
                    got_done = True
                elif line.startswith("event: error"):
                    elapsed = (time.perf_counter() - start) * 1000
                    return RequestResult(
                        query=payload["query"][:40],
                        success=False,
                        duration_ms=elapsed,
                        status_code=200,
                        error="SSE error event",
                    )

        elapsed = (time.perf_counter() - start) * 1000
        return RequestResult(
            query=payload["query"][:40],
            success=got_done,
            duration_ms=elapsed,
            status_code=200,
            token_count=token_count,
            got_done=got_done,
            error=None if got_done else "Stream ended without done event",
        )
    except httpx.TimeoutException:
        elapsed = (time.perf_counter() - start) * 1000
        return RequestResult(
            query=payload["query"][:40],
            success=False,
            duration_ms=elapsed,
            error=f"Timeout after {timeout}s",
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return RequestResult(
            query=payload["query"][:40],
            success=False,
            duration_ms=elapsed,
            error=str(exc)[:80],
        )


async def run_stress_test(
    base_url: str,
    concurrency: int,
    total: int,
    timeout: float,
) -> Stats:
    stats = Stats()
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0

    async def bounded_request(payload: dict) -> RequestResult:
        nonlocal completed
        async with semaphore:
            result = await make_request(client, payload, timeout)
            completed += 1
            status = "✓" if result.success else "✗"
            print(
                f"  [{completed:>3}/{total}] {status} {result.duration_ms:>6.0f}ms  {result.query}…"
            )
            return result

    # Round-robin queries up to `total`
    payloads = [QUERIES[i % len(QUERIES)] for i in range(total)]

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Warmup ping
        try:
            r = await client.get("/health", timeout=5)
            print(f"  API health: {r.status_code}")
        except Exception:
            print("  ⚠  /health not reachable — proceeding anyway")

        print(f"\nSending {total} requests (concurrency={concurrency}, timeout={timeout}s)\n")
        wall_start = time.perf_counter()
        tasks = [bounded_request(p) for p in payloads]
        results = await asyncio.gather(*tasks)
        wall_elapsed = time.perf_counter() - wall_start

    stats.results = list(results)
    print(f"\n  Wall time: {wall_elapsed:.1f}s  ({total / wall_elapsed:.1f} req/s throughput)")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress test the NakTahu /api/v1/query endpoint")
    parser.add_argument("--url", default=BASE_URL, help="API base URL")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--total", type=int, default=20, help="Total requests to send")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (s)")
    args = parser.parse_args()

    stats = asyncio.run(
        run_stress_test(
            base_url=args.url,
            concurrency=args.concurrency,
            total=args.total,
            timeout=args.timeout,
        )
    )
    stats.print_report()


if __name__ == "__main__":
    main()
