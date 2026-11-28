#!/usr/bin/env python3
"""Read-only diagnostics for the .gov.my sites the policy watcher cannot read yet.

Each check answers one question from the first dry runs, using free tools only.
Nothing here writes to Supabase, calls an embedding API, or follows links beyond
the page being checked. Run it from a GitHub runner (the dev sandbox cannot reach
*.gov.my): Actions -> Scrape Probe -> tick "diagnostics".

    python -m scripts.diagnose_sites                  # every check
    python -m scripts.diagnose_sites --only mof-raw   # one check

Checks:
  mof-raw       Are the Treasury circulars' document links hiding in non-href
                attributes (onclick, data-*) or in the raw HTML as plain URLs?
  mof-render    Do links appear once the page is rendered in a browser?
  kpdn-tls      Where does the TLS handshake to www.kpdn.gov.my die, and which
                client setting lets it through?
  sabah-retry   Is the HTTP 500 from www.sabah.gov.my stable, transient, or
                specific to one hostname?
  selangor-render  What does Selangor's page show once its JavaScript has run,
                and which background (XHR/fetch) requests carry the data?
  moh-robots    What does www.moh.gov.my publish at /robots.txt?

Conduct: one request per page load, an honest user agent (no spoofing), a polite
pause between retries, and no attempt to get around an access block. The TLS check
connects and drops; the unverified variants exist only to tell a certificate
problem from a protocol problem and never carry a request.
"""
from __future__ import annotations

import argparse
import re
import socket
import ssl
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Optional

import httpx

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.probe_scrape_options import extract_links, listing_candidates  # noqa: E402

USER_AGENT = "NakTahu-Diagnose/1.0 (+https://github.com/timothylee58/naktahu-AI)"
_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
_MAX_SAMPLES = 4
_DOC_URL_RE = re.compile(r"""(?:https?://[^\s"'<>()]+|/[^\s"'<>()]+)\.(?:pdf|docx?|xlsx?|zip)\b""", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
MOF_ARCHIVE = "https://ppp.treasury.gov.my/arkib/frontend"
KPDN_HOST = "www.kpdn.gov.my"
SABAH_URLS = ("https://www.sabah.gov.my/", "https://sabah.gov.my/")
SELANGOR_URL = "https://www.selangor.gov.my/"
MOH_ROBOTS = "https://www.moh.gov.my/robots.txt"
_LEGACY_SERVER_CONNECT = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


def _flat(text: str, limit: int = 160) -> str:
    return " ".join(_TAG_RE.sub(" ", text).split())[:limit]


# ── mof-raw ──────────────────────────────────────────────────────────────────


class _AttributeScan(HTMLParser):
    """Counts attributes that could carry a document address without being an href."""

    _CARRIERS = ("onclick", "action", "src")

    def __init__(self) -> None:
        super().__init__()
        self.counts: dict[str, int] = {}
        self.samples: dict[str, list[str]] = {}
        self.dead_anchors = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        for name, value in attrs:
            value = value or ""
            if tag == "a" and name == "href" and (value.strip() in ("", "#") or value.lower().startswith("javascript")):
                self.dead_anchors += 1
            carries = name.startswith("data-") or name in self._CARRIERS
            if carries and ("/" in value or ".pdf" in value.lower() or "http" in value.lower() or "download" in value.lower()):
                key = f"{tag}[{name}]"
                self.counts[key] = self.counts.get(key, 0) + 1
                bucket = self.samples.setdefault(key, [])
                if len(bucket) < _MAX_SAMPLES and value not in bucket:
                    bucket.append(value[:140])


def scan_raw_html(html: str) -> list[str]:
    scan = _AttributeScan()
    scan.feed(html)
    docs = sorted(set(_DOC_URL_RE.findall(html)))
    lines = [
        f"{len(html)} bytes, {html.lower().count('<table')} tables, {html.lower().count('<tr')} rows",
        f"anchors with an empty, '#' or javascript: href: {scan.dead_anchors}",
        f"document-looking URLs written in the raw HTML: {len(docs)}",
    ]
    lines += [f"  doc: {doc[:150]}" for doc in docs[:_MAX_SAMPLES * 2]]
    for key, count in sorted(scan.counts.items(), key=lambda kv: -kv[1])[:8]:
        lines.append(f"attribute {key}: {count} with an address-like value")
        lines += [f"  e.g. {sample}" for sample in scan.samples[key]]
    marker = html.find("SURAT EDARAN")
    if marker >= 0:
        lines.append("row context: " + " ".join(html[max(0, marker - 320) : marker + 320].split()))
    return lines


def check_mof_raw(client: httpx.Client) -> list[str]:
    try:
        resp = client.get(MOF_ARCHIVE, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    except httpx.HTTPError as exc:
        return [f"fetch failed: {type(exc).__name__}: {str(exc)[:120]}"]
    if resp.status_code != 200:
        return [f"HTTP {resp.status_code}"]
    return scan_raw_html(resp.text)


# ── kpdn-tls ─────────────────────────────────────────────────────────────────


def tls_variants() -> list[tuple[str, Callable[[], ssl.SSLContext], bool]]:
    """(name, context factory, send SNI). Verification is on for every variant except
    the last two, which exist to separate a certificate problem from a protocol one."""

    def default() -> ssl.SSLContext:
        return ssl.create_default_context()

    def tls12() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    def legacy() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.options |= _LEGACY_SERVER_CONNECT
        return ctx

    def seclevel0() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        return ctx

    def no_verify() -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.options |= _LEGACY_SERVER_CONNECT
        return ctx

    return [
        ("default", default, True),
        ("tls1.2 only", tls12, True),
        ("legacy renegotiation allowed", legacy, True),
        ("security level 0 ciphers", seclevel0, True),
        ("no certificate check, legacy, level 0 (diagnostic only)", no_verify, True),
        ("no certificate check, no SNI (diagnostic only)", no_verify, False),
    ]


def try_handshake(host: str, name: str, factory: Callable[[], ssl.SSLContext], sni: bool) -> str:
    try:
        ctx = factory()
        with socket.create_connection((host, 443), timeout=12) as sock:
            with ctx.wrap_socket(sock, server_hostname=host if sni else None) as tls:
                cipher = tls.cipher()
                return f"{name}: OK {tls.version()} {cipher[0] if cipher else '?'}"
    except Exception as exc:  # any failure is the datum
        return f"{name}: FAIL {type(exc).__name__}: {str(exc)[:110]}"


def check_kpdn_tls() -> list[str]:
    lines: list[str] = []
    try:
        addresses = sorted({info[4][0] for info in socket.getaddrinfo(KPDN_HOST, 443, proto=socket.IPPROTO_TCP)})
        lines.append(f"{KPDN_HOST} resolves to {', '.join(addresses[:4])}")
    except OSError as exc:
        return [f"DNS failed: {exc}"]
    lines += [try_handshake(KPDN_HOST, name, factory, sni) for name, factory, sni in tls_variants()]
    try:
        out = subprocess.run(
            ["openssl", "s_client", "-connect", f"{KPDN_HOST}:443", "-servername", KPDN_HOST],
            input="", capture_output=True, text=True, timeout=20, check=False,
        )
        tail = [ln.strip() for ln in (out.stdout + out.stderr).splitlines() if ln.strip()][:14]
        lines.append("openssl s_client:")
        lines += [f"  {ln[:140]}" for ln in tail]
    except (OSError, subprocess.SubprocessError) as exc:
        lines.append(f"openssl s_client unavailable: {type(exc).__name__}")
    return lines


# ── sabah-retry ──────────────────────────────────────────────────────────────


def check_sabah(client: httpx.Client, attempts: int = 3, pause: float = 4.0, sleep: Callable[[float], None] = time.sleep) -> list[str]:
    lines: list[str] = []
    for url in SABAH_URLS:
        for attempt in range(1, attempts + 1):
            try:
                resp = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
                headers = {k: resp.headers.get(k, "-") for k in ("server", "via", "content-type")}
                lines.append(
                    f"{url} try {attempt}: HTTP {resp.status_code} final={resp.url} {headers} body={_flat(resp.text, 110)!r}"
                )
            except httpx.HTTPError as exc:
                lines.append(f"{url} try {attempt}: {type(exc).__name__}: {str(exc)[:100]}")
            if attempt < attempts:
                sleep(pause)
    return lines


# ── moh-robots ───────────────────────────────────────────────────────────────


def check_moh_robots(client: httpx.Client) -> list[str]:
    try:
        resp = client.get(MOH_ROBOTS, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    except httpx.HTTPError as exc:
        return [f"fetch failed: {type(exc).__name__}: {str(exc)[:120]}"]
    lines = [f"HTTP {resp.status_code}, server={resp.headers.get('server', '-')}, via={resp.headers.get('via', '-')}"]
    if resp.status_code == 200:
        lines += [f"  {ln[:140]}" for ln in resp.text.splitlines()[:25]]
    else:
        lines.append(f"  body: {_flat(resp.text, 200)!r}")
    return lines


# ── browser renders ──────────────────────────────────────────────────────────


def summarise_requests(requests: list[tuple[str, int, str, str]], limit: int = 12) -> list[str]:
    """Background data requests, JSON first: that is where a single-page site keeps its content."""
    ordered = sorted(requests, key=lambda r: ("json" not in r[3].lower(), r[2]))
    return [f"{kind} {status} {ctype.split(';')[0] or '-'} {url[:130]}" for kind, status, url, ctype in ordered[:limit]]


def render_page(url: str, timeout_ms: int = 35000) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ["playwright is not installed (the workflow installs it; locally: pip install playwright && playwright install chromium)"]
    requests: list[tuple[str, int, str, str]] = []
    lines: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.on(
                "response",
                lambda r: requests.append((r.request.resource_type, r.status, r.url, r.headers.get("content-type", "")))
                if r.request.resource_type in ("xhr", "fetch")
                else None,
            )
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            text = page.inner_text("body")
            links = extract_links(html, url)
            docs = sorted(set(_DOC_URL_RE.findall(html)))
            lines += [
                f"title: {page.title()[:100]!r}",
                f"visible text: {len(text)} chars; rendered HTML: {len(html)} bytes; links under *.gov.my: {len(links)}",
                f"document-looking URLs in the rendered page: {len(docs)}",
            ]
            lines += [f"  doc: {doc[:150]}" for doc in docs[: _MAX_SAMPLES * 2]]
            lines.append(f"background requests (xhr/fetch): {len(requests)}")
            lines += [f"  {row}" for row in summarise_requests(requests)]
            lines.append("listing candidates:")
            lines += [f"  {c['text'][:60]!r} -> {c['url']}" for c in listing_candidates(links, 10)]
            lines.append(f"first text: {_flat(text, 220)!r}")
        except Exception as exc:  # a timeout or crash is a result, not a failure of the diagnosis
            lines.append(f"render failed: {type(exc).__name__}: {str(exc)[:160]}")
        finally:
            browser.close()
    return lines


# ── runner ───────────────────────────────────────────────────────────────────

CHECKS = ("mof-raw", "mof-render", "kpdn-tls", "sabah-retry", "selangor-render", "moh-robots")


def run_check(name: str, client: httpx.Client) -> list[str]:
    if name == "mof-raw":
        return check_mof_raw(client)
    if name == "mof-render":
        return render_page(MOF_ARCHIVE)
    if name == "kpdn-tls":
        return check_kpdn_tls()
    if name == "sabah-retry":
        return check_sabah(client)
    if name == "selangor-render":
        return render_page(SELANGOR_URL)
    if name == "moh-robots":
        return check_moh_robots(client)
    raise ValueError(f"unknown check {name!r}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", action="append", choices=CHECKS, default=[], help="run just this check (repeatable)")
    args = parser.parse_args(argv)
    with httpx.Client(timeout=_TIMEOUT) as client:
        for name in args.only or CHECKS:
            print(f"\n=== {name} ===")
            try:
                for line in run_check(name, client):
                    print(line)
            except Exception as exc:  # one broken check must not hide the others
                print(f"check crashed: {type(exc).__name__}: {str(exc)[:160]}")
    return 0


if __name__ == "__main__":  # CLI script: print is the interface here
    sys.exit(main())
