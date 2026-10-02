"""Rewrite config fragments with country flag + protocol info.

Usage:
    python src/renamer.py <location.json> <input.txt> <output.txt>
"""
import base64
import json
import logging
import os
import sys
from typing import Optional

import parsers

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

_PROTO_NAMES = {
    "vmess": "VMess",
    "vless": "VLESS",
    "trojan": "Trojan",
    "hysteria2": "Hysteria2",
    "hy2": "Hysteria2",
    "ss": "SS",
}

# Per-protocol sequence counters, so names look like "🇺🇸 3 - US - VMess/WS/TLS - 443".
_counters: dict[str, int] = {}


def _next_index(scheme: str) -> int:
    key = _PROTO_NAMES.get(scheme, scheme.upper())
    _counters[key] = _counters.get(key, 0) + 1
    return _counters[key]


# ---------------------------------------------------------------------------
# Name construction
# ---------------------------------------------------------------------------

def build_name(index: int, flag: str, code: str, data: dict, scheme: str) -> str:
    parts = [_PROTO_NAMES.get(scheme, scheme.upper())]

    net = (data.get("net") or data.get("type") or "tcp").lower()
    if net not in ("tcp", ""):
        parts.append(net.upper())

    sec = (data.get("security") or data.get("tls") or "none").lower()
    if sec == "tls":
        parts.append("TLS")
    elif sec == "reality":
        parts.append("REALITY")
    elif sec == "xtls":
        parts.append("XTLS")

    if data.get("fp"):
        parts.append("UTLS")

    port = data.get("port", "")
    return f"{flag} {index} - {code} - {'/'.join(parts)} - {port}"


# ---------------------------------------------------------------------------
# Per-config rename
# ---------------------------------------------------------------------------

def rename(uri: str, cache: dict) -> str:
    scheme = uri.split("://", 1)[0].lower()
    data = parsers.parse_config(uri)
    if not data:
        return uri

    address = data.get("address") or data.get("add", "")
    flag, code = cache.get(address, ["🏳️", "XX"])
    name = build_name(_next_index(scheme), flag, code, data, scheme)

    if scheme == "vmess":
        return _rename_vmess(uri, name)

    # Everything else is a URI with an optional #fragment we can swap.
    base = uri.split("#", 1)[0]
    return f"{base}#{name}"


def _rename_vmess(uri: str, name: str) -> str:
    data = parsers.parse_config(uri)
    if not data:
        return uri
    data.pop("_scheme", None)
    data["ps"] = name
    encoded = base64.b64encode(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    return f"vmess://{encoded}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python renamer.py <location.json> <input.txt> <output.txt>")
        sys.exit(1)
    location_file, input_file, output_file = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        with open(location_file, encoding="utf-8") as f:
            cache = json.load(f)
    except FileNotFoundError:
        log.error(f"{location_file} not found")
        cache = {}

    try:
        with open(input_file, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        log.error(f"{input_file} not found")
        return

    header, configs = [], []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("//"):
            header.append(line)
        else:
            configs.append(line)

    renamed = [rename(c, cache) for c in configs]

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for h in header:
            f.write(h + "\n")
        if header:
            f.write("\n")
        for c in renamed:
            f.write(c + "\n\n")

    log.info(f"renamed {len(renamed)} configs -> {output_file}")


if __name__ == "__main__":
    main()
