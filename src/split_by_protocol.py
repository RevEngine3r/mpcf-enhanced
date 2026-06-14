#!/usr/bin/env python3
"""
split_by_protocol.py
~~~~~~~~~~~~~~~~~~~~
Reads configs/google_200.txt and writes one file per detected
V2Ray/Xray protocol into configs/google_200_<protocol>.txt.

Supported protocols
-------------------
vmess      vmess://...
vless      vless://...
trojan     trojan://...
shadowsocks ss://...
shadowsocksr ssr://...
hy2 / hysteria2  hy2://... or hysteria2://...
hysteria   hysteria://...
tuic       tuic://...
wireguard  wireguard://...
socks      socks://... or socks5://...
naive      naive://...

Lines that don't match any prefix are written to
configs/google_200_unknown.txt (so nothing is silently dropped).
"""

import os
import re
from collections import defaultdict

# ── input / output paths ─────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.dirname(SCRIPT_DIR)
CONFIGS_DIR  = os.path.join(REPO_ROOT, "configs")
INPUT_FILE   = os.path.join(CONFIGS_DIR, "google_200.txt")

# ── protocol → canonical name mapping ────────────────────────────────────────
# Each entry: (regex_pattern, canonical_name)
# Patterns are matched against the beginning of the stripped line (case-insensitive).
PROTOCOL_PATTERNS = [
    (r"vmess://",       "vmess"),
    (r"vless://",       "vless"),
    (r"trojan://",      "trojan"),
    (r"ssr://",         "shadowsocksr"),   # must come BEFORE ss://
    (r"ss://",          "shadowsocks"),
    (r"hy2://",         "hysteria2"),
    (r"hysteria2://",   "hysteria2"),
    (r"hysteria://",    "hysteria"),
    (r"tuic://",        "tuic"),
    (r"wireguard://",   "wireguard"),
    (r"wg://",          "wireguard"),
    (r"socks5://",      "socks"),
    (r"socks://",       "socks"),
    (r"naive\+https://","naive"),
    (r"naive://",       "naive"),
]

# Pre-compile for speed
_COMPILED = [(re.compile(pat, re.IGNORECASE), name) for pat, name in PROTOCOL_PATTERNS]


def detect_protocol(line: str) -> str:
    """Return canonical protocol name, or 'unknown'."""
    for pattern, name in _COMPILED:
        if pattern.match(line):
            return name
    return "unknown"


def split_google_200() -> None:
    if not os.path.isfile(INPUT_FILE):
        print(f"[split_by_protocol] ⚠  Input not found: {INPUT_FILE}")
        return

    buckets: defaultdict[str, list[str]] = defaultdict(list)
    total = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            # Skip blank lines and comments; preserve them nowhere
            if not stripped or stripped.startswith("#"):
                continue

            proto = detect_protocol(stripped)
            buckets[proto].append(line)
            total += 1

    if total == 0:
        print("[split_by_protocol] ⚠  google_200.txt is empty or has no proxy lines.")
        return

    os.makedirs(CONFIGS_DIR, exist_ok=True)

    for proto, lines in sorted(buckets.items()):
        out_path = os.path.join(CONFIGS_DIR, f"google_200_{proto}.txt")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[split_by_protocol] ✓  {proto:15s}  {len(lines):>5} proxies  →  configs/google_200_{proto}.txt")

    print(f"[split_by_protocol] ✓  Total {total} proxies split into {len(buckets)} protocol file(s).")


if __name__ == "__main__":
    split_google_200()
