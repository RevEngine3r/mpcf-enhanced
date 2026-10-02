"""Resolve hostnames -> (country flag, ISO code) and cache to JSON.

Usage:
    python src/enricher.py <input.txt> <output.json>
"""
import json
import logging
import os
import socket
import sys
from typing import Optional

import requests

import parsers
import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update(settings.HEADERS)

# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_CODE_KEYS = ("countrycode2", "countrycode", "country_code", "country_code2", "cca2", "code")
_NAME_KEYS = ("countryname", "country_name", "country", "name")


def extract_country(data: dict) -> tuple[str, str]:
    """Return (ISO2 code, country name) from a location API response."""
    if not isinstance(data, dict):
        return "", ""
    flat = {k.lower(): v for k, v in data.items() if v is not None}

    code = ""
    for k in _CODE_KEYS:
        v = flat.get(k)
        if isinstance(v, str) and len(v) == 2 and v.isalpha():
            code = v.upper()
            break

    name = ""
    for k in _NAME_KEYS:
        v = flat.get(k)
        if isinstance(v, str) and len(v) > 2 and not v.isdigit():
            name = v
            break

    return code, name


def code_to_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🏳️"
    try:
        return "".join(chr(0x1F1E6 + ord(c.upper()) - ord("A")) for c in code)
    except Exception:
        return "🏳️"


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def load_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        log.warning(f"could not read {path}: {e}")
        return {}


def save_cache(path: str, cache: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    log.info(f"saved {len(cache)} entries -> {path}")


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_location(address: str, cache: dict) -> tuple[str, str]:
    """Look up one hostname; results are cached in-place in `cache`."""
    if address in cache:
        return tuple(cache[address])  # type: ignore[return-value]

    try:
        ip = socket.gethostbyname(address)
    except socket.gaierror:
        cache[address] = ["🏳️", "XX"]
        return "🏳️", "XX"

    for template in settings.LOCATION_APIS:
        url = template.format(ip=ip)
        try:
            r = _session.get(url, timeout=3)
            if r.status_code != 200:
                continue
            code, _name = extract_country(r.json())
            if code:
                flag = code_to_flag(code)
                cache[address] = [flag, code]
                return flag, code
        except Exception:
            continue

    cache[address] = ["🏳️", "XX"]
    return "🏳️", "XX"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python enricher.py <input.txt> <output.json>")
        sys.exit(1)
    input_file, output_file = sys.argv[1], sys.argv[2]

    cache = load_cache(output_file)
    try:
        with open(input_file, encoding="utf-8") as f:
            configs = [l.strip() for l in f if l.strip() and not l.startswith("//")]
    except FileNotFoundError:
        log.error(f"{input_file} not found")
        return

    addresses = {parsers.extract_address(c) for c in configs}
    addresses.discard(None)
    addresses = sorted(addresses)  # type: ignore[arg-type]

    todo = [a for a in addresses if a not in cache]
    log.info(f"{len(addresses)} unique addresses, {len(todo)} to look up")

    for i, addr in enumerate(todo, 1):
        get_location(addr, cache)
        if i % 25 == 0 or i == len(todo):
            log.info(f"  {i}/{len(todo)}")

    save_cache(output_file, cache)


if __name__ == "__main__":
    main()
