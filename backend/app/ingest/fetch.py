"""HTTP fetch for the ingestion agent: httpx, allowlisted domains only, 1 request/sec, polite user agent."""
from __future__ import annotations
import threading
import time
from urllib.parse import urlparse

import httpx

from ..config import settings, load_sources


class FetchError(RuntimeError):
    pass


_lock = threading.Lock()
_last = 0.0


def allowed(url: str) -> bool:
    """allow_domains: [gsu.edu] matches gsu.edu and every subdomain (calendar.gsu.edu, viewbook.gsu.edu ...)."""
    host = (urlparse(url).hostname or "").lower()
    doms = [d.lower() for d in load_sources().get("allow_domains", ["gsu.edu"])]
    return any(host == d or host.endswith("." + d) for d in doms)


def _throttle() -> None:
    global _last
    rate = float(load_sources().get("rate_limit_per_sec", 1)) or 1
    with _lock:
        wait = (1.0 / rate) - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()


def fetch(url: str, timeout: float = 20.0) -> tuple[str, str, int]:
    """Returns (final_url, text, status). Raises FetchError on non-allowlisted URLs, bot walls or HTTP errors."""
    if not allowed(url):
        raise FetchError(f"blocked: {url} is not on the allowlist")
    _throttle()
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers={"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.8"}) as c:
            r = c.get(url)
    except httpx.HTTPError as e:
        raise FetchError(f"network: {type(e).__name__}: {e}") from e
    final = str(r.url)
    if not allowed(final):
        raise FetchError(f"blocked: redirected off the allowlist to {final}")
    body = r.text
    if r.status_code >= 400:
        raise FetchError(f"http {r.status_code}")
    low = body[:4000].lower()
    if "challenge-platform" in low or "awswaf" in low or "just a moment..." in low or "captcha" in low:
        raise FetchError("bot challenge (Cloudflare / AWS WAF); source needs a different URL")
    return final, body, r.status_code
