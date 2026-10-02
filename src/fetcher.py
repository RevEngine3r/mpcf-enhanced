"""Fetch proxy configs from settings.SOURCE_URLS -> configs/fetched.txt.

Usage:
    python src/fetcher.py
"""
import html
import logging
import os
import re
import time
from typing import Optional

import requests

import parsers
import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update(settings.HEADERS)

_TELEGRAM_RE = re.compile(r"^https://t\.me/s/")


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------

def fetch_url(url: str) -> Optional[str]:
    """GET a URL with exponential backoff. Returns response text or None."""
    backoff = 1
    for attempt in range(settings.MAX_RETRIES):
        try:
            r = _session.get(url, timeout=settings.REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if attempt == settings.MAX_RETRIES - 1:
                log.error(f"fetch failed: {url}: {e}")
                return None
            wait = min(settings.RETRY_DELAY * backoff, 60)
            log.warning(f"retry {attempt + 1}/{settings.MAX_RETRIES} in {wait}s: {url}")
            time.sleep(wait)
            backoff *= 2
    return None


# ---------------------------------------------------------------------------
# HTML -> plain text
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_CODE_BLOCK_RE = re.compile(r"<code[^>]*>(.*?)</code>", re.DOTALL | re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
# tg-emoji / emoji wrappers: drop entire element including inner media/svg
_TG_EMOJI_RE = re.compile(
    r"<tg-emoji\b[^>]*>.*?</tg-emoji>", re.DOTALL | re.IGNORECASE
)
_EMOJI_I_RE = re.compile(
    r"<i\b[^>]*class=\"[^\"]*\bemoji\b[^\"]*\"[^>]*>.*?</i>",
    re.DOTALL | re.IGNORECASE,
)


def _clean_fragment(fragment: str) -> str:
    """Clean an HTML fragment (typically a <code> block) down to plain text."""
    # Drop emoji elements entirely — they contain nested <b>, <img>, <video>,
    # svg data URIs, etc. that would otherwise leak garbage into the output.
    fragment = _TG_EMOJI_RE.sub("", fragment)
    fragment = _EMOJI_I_RE.sub("", fragment)
    # Convert <br> to newlines so configs stay line-separated
    fragment = _BR_RE.sub("\n", fragment)
    # Strip remaining tags
    fragment = _TAG_RE.sub("", fragment)
    # Unescape entities last (so &amp; -> &, &#64; -> @, etc.)
    fragment = html.unescape(fragment)
    return fragment


def html_to_text(page: str) -> str:
    """Extract proxy URIs from a Telegram preview page.

    Telegram wraps configs in <code>…</code> blocks. We only look inside
    those blocks — everything else on the page (ads, tg-emoji media with
    embedded <video src>, reaction counts, footer links) is noise that
    would otherwise be mangled into fake "configs" by naive tag stripping.
    """
    blocks = _CODE_BLOCK_RE.findall(page)
    if not blocks:
        return ""
    cleaned = [_clean_fragment(b) for b in blocks]
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Per-source strategies
# ---------------------------------------------------------------------------

def fetch_telegram(url: str) -> list[str]:
    page = fetch_url(url)
    if not page:
        return []
    text = html_to_text(page)
    if not text.strip():
        log.warning(f"no <code> blocks found in {url}")
        return []
    return parsers.split_configs(text)


def fetch_ssconf(url: str) -> list[str]:
    """ssconf:// is just https:// with the base64 wrapper removed."""
    text = fetch_url(url.replace("ssconf://", "https://", 1))
    return parsers.split_configs(text) if text else []


def fetch_plain(url: str) -> list[str]:
    text = fetch_url(url)
    return parsers.split_configs(text) if text else []


def fetch_source(url: str) -> list[str]:
    if url.startswith("ssconf://"):
        return fetch_ssconf(url)
    if _TELEGRAM_RE.match(url):
        return fetch_telegram(url)
    return fetch_plain(url)


# ---------------------------------------------------------------------------
# Normalise + filter
# ---------------------------------------------------------------------------

def normalize(uri: str) -> str:
    if uri.startswith("hy2://"):
        return "hysteria2://" + uri[6:]
    return uri


def accept(uri: str) -> bool:
    scheme = uri.split("://", 1)[0].lower()
    if not settings.is_enabled(scheme):
        return False
    return parsers.is_valid(uri)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_fetched(configs: list[str]) -> None:
    os.makedirs(os.path.dirname(settings.FETCHED_FILE) or ".", exist_ok=True)
    with open(settings.FETCHED_FILE, "w", encoding="utf-8") as f:
        f.write(settings.SUBSCRIPTION_HEADER)
        f.write("\n")
        for c in configs:
            f.write(c + "\n\n")
    log.info(f"wrote {len(configs)} configs -> {settings.FETCHED_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    all_configs: list[str] = []
    seen: set[str] = set()

    for url in settings.SOURCE_URLS:
        log.info(f"fetching {url}")
        try:
            raw = fetch_source(url)
        except Exception as e:
            log.error(f"{url}: {e}")
            continue

        new = 0
        for uri in raw:
            uri = normalize(uri)
            if uri in seen or not accept(uri):
                continue
            seen.add(uri)
            all_configs.append(uri)
            new += 1

        log.info(f"  -> {new} new (total {len(all_configs)})")
        time.sleep(1)

    write_fetched(all_configs)


if __name__ == "__main__":
    main()