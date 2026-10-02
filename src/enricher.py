"""Enrich proxy URIs with country flag/ISO code using an offline GeoIP DB.

On first run, downloads a free DB-IP Lite country database (~6 MB).
Subsequent runs are fully offline.

Usage:
    python src/enricher.py <input.txt> <output.txt>
"""
from __future__ import annotations

import gzip
import ipaddress
import logging
import os
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from typing import Optional

import geoip2.database
import geoip2.errors

# local modules
try:
    import parsers  # type: ignore
    import settings  # type: ignore
except ImportError:  # allow running from repo root
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import parsers  # type: ignore
    import settings  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Country DB download / management
# ---------------------------------------------------------------------------

_DBIP_URL_TEMPLATE = "https://download.db-ip.com/free/dbip-country-lite-{ym}.mmdb.gz"


def _current_and_prev_month() -> list[str]:
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    return [f"{y:04d}-{m:02d}", f"{prev_y:04d}-{prev_m:02d}"]


def download_geoip_db(dest_path: str, force: bool = False) -> str:
    """Download the DB-IP Lite country MMDB to `dest_path` if missing."""
    if os.path.exists(dest_path) and not force:
        log.info(f"geoip db already present: {dest_path}")
        return dest_path

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

    last_err: Optional[Exception] = None
    for ym in _current_and_prev_month():
        url = _DBIP_URL_TEMPLATE.format(ym=ym)
        log.info(f"downloading geoip db: {url}")
        try:
            req = urllib.request.Request(url, headers=settings.HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} for {url}")
                gz_bytes = resp.read()

            mmdb_bytes = gzip.decompress(gz_bytes)

            fd, tmp_path = tempfile.mkstemp(
                prefix="geoip-", suffix=".mmdb", dir=os.path.dirname(dest_path) or "."
            )
            with os.fdopen(fd, "wb") as f:
                f.write(mmdb_bytes)

            with geoip2.database.Reader(tmp_path) as _r:
                _r.country("8.8.8.8")  # sanity check

            shutil.move(tmp_path, dest_path)
            log.info(f"saved geoip db -> {dest_path} ({len(mmdb_bytes)} bytes)")
            return dest_path
        except Exception as e:
            last_err = e
            log.warning(f"failed to fetch {url}: {e}")
            continue

    raise RuntimeError(f"could not download geoip db: {last_err}")


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def code_to_flag(code: str) -> str:
    if not code or len(code) != 2 or not code.isalpha():
        return "🏳️"
    try:
        return "".join(chr(0x1F1E6 + ord(c.upper()) - ord("A")) for c in code)
    except Exception:
        return "🏳️"


# ---------------------------------------------------------------------------
# GeoIP reader (opened once)
# ---------------------------------------------------------------------------

_reader: Optional[geoip2.database.Reader] = None


def get_reader() -> geoip2.database.Reader:
    global _reader
    if _reader is None:
        _reader = geoip2.database.Reader(settings.GEOIP_DB_PATH)
    return _reader


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_location(ip: str) -> tuple[str, str]:
    """Look up an IP address. Returns (flag, code)."""
    code = ""
    try:
        resp = get_reader().country(ip)
        code = (resp.country.iso_code or "").upper()
    except geoip2.errors.AddressNotFoundError:
        code = ""
    except Exception as e:
        log.debug(f"geoip lookup failed for {ip}: {e}")
        code = ""

    if code and len(code) == 2:
        return code_to_flag(code), code

    return "🏳️", "XX"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    input_file, output_file = settings.MERGED_FILE, settings.MERGED_FILE

    # 1. make sure we have an offline DB
    try:
        download_geoip_db(settings.GEOIP_DB_PATH)
    except Exception as e:
        log.error(f"cannot proceed without geoip db: {e}")
        sys.exit(2)

    # 2. read input lines
    try:
        with open(input_file, encoding="utf-8") as f:
            lines = [l.strip() for l in f]
    except FileNotFoundError:
        log.error(f"{input_file} not found")
        return

    # 3. process lines: skip empty, skip lines with no IP in the URI
    results: list[str] = []
    total = len(lines)
    log.info(f"{total} lines to process")

    try:
        for i, line in enumerate(lines, 1):
            if not line:
                continue

            address = parsers.extract_address(line)
            if not address:
                continue

            # only accept literal IPs; skip hostnames
            try:
                ipaddress.ip_address(address)
            except ValueError:
                continue

            flag, code = get_location(address)
            results.append(f"{flag} {line} [{code}]")

            if i % 25 == 0 or i == total:
                log.info(f"  {i}/{total}")
    finally:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for line in results:
                f.write(line + "\n")
        log.info(f"saved {len(results)} entries -> {output_file}")

        if _reader is not None:
            _reader.close()


if __name__ == "__main__":
    main()
