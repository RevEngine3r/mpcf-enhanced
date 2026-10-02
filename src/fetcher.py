"""Fetch proxy configs from settings.SOURCE_URLS -> configs/fetched.txt.

Usage:
    python src/fetcher.py
"""
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

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
# Per-source strategies
# ---------------------------------------------------------------------------

def fetch_telegram(url: str) -> list[str]:
    html = fetch_url(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.MAX_CONFIG_AGE_DAYS)

    configs: list[str] = []
    for msg in soup.find_all("div", class_="tgme_widget_message_text"):
        date = _message_date(msg)
        if date and date < cutoff:
            continue
        if msg.text:
            configs.extend(parsers.split_configs(msg.text))
    return configs


def _message_date(msg) -> Optional[datetime]:
    try:
        parent = msg.find_parent("div", class_="tgme_widget_message")
        time_el = parent.find("time") if parent else None
        if time_el and time_el.get("datetime"):
            return datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
    except Exception:
        pass
    return None


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