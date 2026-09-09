from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import shutil
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    observed_at: str
    content_hash: str
    attempts: int = 1
    recovery_method: str = "urllib"
    original_url: str | None = None


class SourceFetchError(RuntimeError):
    def __init__(self, message: str, *, hard_block: bool = False, attempts: list[dict] | None = None):
        super().__init__(message)
        self.hard_block = bool(hard_block)
        self.attempt_log = attempts or []


_TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}
_HARD_BLOCK_HTTP = {401, 403, 451}


def _request(url: str) -> Request:
    # Browser-like but honest headers improve compatibility with official retail
    # sites that reject bare script user agents. No cookies/login are used.
    return Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36 PromoIntelligence/0.4",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en;q=0.7",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    })


def fetch_url(url: str, timeout: int = 12, max_bytes: int = 8_000_000, attempts: int = 2) -> FetchResult:
    """Fetch one public source within one bounded total time budget.

    A single quick retry is allowed only for transient network/server failures.
    The overall wall clock remains bounded by ``timeout`` so retries cannot
    reintroduce the P4 stall problem.
    """
    started = time.monotonic()
    deadline = started + max(1, timeout)
    last_exc: Exception | None = None
    tries = max(1, int(attempts))

    for attempt in range(1, tries + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            req = _request(url)
            with urlopen(req, timeout=max(1.0, remaining)) as resp:
                chunks: list[bytes] = []
                total = 0
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"fetch exceeded {timeout}s total budget")
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"response exceeds {max_bytes} bytes")
                    chunks.append(chunk)
                body = b"".join(chunks)
                observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                return FetchResult(
                    url=url,
                    status=getattr(resp, "status", 200),
                    content_type=resp.headers.get("Content-Type", "unknown"),
                    body=body,
                    observed_at=observed_at,
                    content_hash="sha256:" + hashlib.sha256(body).hexdigest(),
                    attempts=attempt,
                    recovery_method="urllib",
                    original_url=url,
                )
        except HTTPError as exc:
            last_exc = exc
            if exc.code not in _TRANSIENT_HTTP:
                raise
        except (URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        if attempt < tries and deadline - time.monotonic() > 0.3:
            time.sleep(min(0.2 * attempt, max(0.0, deadline - time.monotonic())))

    if last_exc is not None:
        raise last_exc
    raise TimeoutError(f"fetch exceeded {timeout}s total budget")


def _curl_fetch(url: str, timeout: int, max_bytes: int = 8_000_000) -> FetchResult:
    """Optional normal public HTTP fallback using curl when available.

    This does not use cookies, authentication, CAPTCHA solving, proxies, or any
    anti-bot bypass. It is simply a second standards-compliant HTTP client for
    public official pages whose CDN/TLS stack may reject urllib on Android.
    """
    curl = shutil.which("curl")
    if not curl:
        raise FileNotFoundError("curl is not installed")
    cmd = [
        curl, "-L", "--fail", "--silent", "--show-error", "--compressed",
        "--max-time", str(max(1, int(timeout))),
        "--connect-timeout", str(max(1, min(5, int(timeout)))),
        "-A", "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36 PromoIntelligence/0.4",
        "-H", "Accept-Language: th-TH,th;q=0.9,en;q=0.7",
        url,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(2, int(timeout) + 2))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip() or f"curl exit {proc.returncode}"
        raise RuntimeError(err)
    body = proc.stdout
    if len(body) > max_bytes:
        raise ValueError(f"response exceeds {max_bytes} bytes")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return FetchResult(
        url=url,
        status=200,
        content_type="text/html",
        body=body,
        observed_at=observed_at,
        content_hash="sha256:" + hashlib.sha256(body).hexdigest(),
        attempts=1,
        recovery_method="curl",
        original_url=url,
    )


def fetch_source(source: dict, default_timeout: int = 12, max_bytes: int = 8_000_000) -> FetchResult:
    """Fetch one configured source using bounded, policy-safe recovery.

    Recovery order is primary URL -> optional curl on the same public URL ->
    configured alternate official URLs. Remaining 401/403/451 responses after
    all configured public fallbacks are classified as external hard blocks.
    """
    primary = source["url"]
    urls = [primary] + [u for u in source.get("alternate_urls", []) if u and u != primary]
    timeout = int(source.get("timeout_seconds", default_timeout))
    budget = int(source.get("recovery_budget_seconds", max(timeout, timeout * max(1, len(urls)))))
    deadline = time.monotonic() + max(timeout, budget)
    use_curl = bool(source.get("curl_fallback", False))
    log: list[dict] = []
    hard_codes: list[int] = []

    for url in urls:
        remaining = int(max(1, deadline - time.monotonic()))
        if remaining <= 0:
            break
        per_try = min(timeout, remaining)
        try:
            result = fetch_url(url, timeout=per_try, max_bytes=max_bytes, attempts=2)
            if url != primary:
                return FetchResult(**{**result.__dict__, "recovery_method": "alternate_urllib", "original_url": primary})
            return result
        except HTTPError as exc:
            log.append({"url": url, "client": "urllib", "error_type": "HTTPError", "status": exc.code, "error": str(exc)})
            if exc.code in _HARD_BLOCK_HTTP:
                hard_codes.append(exc.code)
            elif exc.code not in _TRANSIENT_HTTP:
                # Non-transient but not access-control: still try an explicitly
                # configured alternate official URL if one exists.
                pass
        except Exception as exc:
            log.append({"url": url, "client": "urllib", "error_type": type(exc).__name__, "error": str(exc)})

        if use_curl and time.monotonic() < deadline:
            remaining = int(max(1, deadline - time.monotonic()))
            try:
                result = _curl_fetch(url, min(timeout, remaining), max_bytes=max_bytes)
                method = "curl" if url == primary else "alternate_curl"
                return FetchResult(**{**result.__dict__, "recovery_method": method, "original_url": primary})
            except Exception as exc:
                text = str(exc)
                log.append({"url": url, "client": "curl", "error_type": type(exc).__name__, "error": text})
                if "403" in text or "401" in text or "451" in text:
                    hard_codes.append(403 if "403" in text else 401 if "401" in text else 451)

    http_rows = [
        row for row in log
        if row.get("status") is not None or any(code in str(row.get("error", "")) for code in ("401", "403", "451"))
    ]
    # Client-unavailable rows (e.g. curl not installed) do not negate a clear
    # access-control result from every actual HTTP response.
    hard_block = bool(hard_codes) and bool(http_rows) and all(
        (row.get("status") in _HARD_BLOCK_HTTP) or any(code in str(row.get("error", "")) for code in ("401", "403", "451"))
        for row in http_rows
    )
    short = "; ".join(f"{x.get('client')}:{x.get('error_type')}:{x.get('status') or x.get('error','')[:80]}" for x in log[-5:])
    raise SourceFetchError(short or "all fetch strategies failed", hard_block=hard_block, attempts=log)
