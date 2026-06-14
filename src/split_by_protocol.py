#!/usr/bin/env python3
"""
split_by_protocol.py
~~~~~~~~~~~~~~~~~~~~
Reads configs/google_200.txt, resolves every domain host to an IP address
(replacing it in the URI so consumers always get a bare IP), then writes
one file per detected V2Ray/Xray protocol into configs/google_200_<proto>.txt.

Resolver behaviour
------------------
- Extracts the host from the proxy URI (handles all common schemes).
- Skips resolution if the host is already an IPv4 or IPv6 literal.
- Resolves all unique domains concurrently (ThreadPoolExecutor) with a
  configurable timeout so a slow DNS server never blocks the whole run.
- Tries up to RESOLVER_RETRIES times per domain with exponential back-off.
- Falls back to the original domain if resolution fails (proxy is still kept).
- Results are cached in memory so the same domain is only looked up once.
- Uses concurrent.futures for pure stdlib — no extra dependencies.

Supported protocols
-------------------
vmess        vmess://...
vless        vless://...
trojan       trojan://...
shadowsocks  ss://...
shadowsocksr ssr://...
hy2/hysteria2 hy2://... or hysteria2://...
hysteria     hysteria://...
tuic         tuic://...
wireguard    wireguard://... or wg://...
socks        socks://... or socks5://...
naive        naive://... or naive+https://...

Lines that don't match any prefix are written to
configs/google_200_unknown.txt (so nothing is silently dropped).
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse, urlunparse

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
CONFIGS_DIR = os.path.join(REPO_ROOT, "configs")
INPUT_FILE  = os.path.join(CONFIGS_DIR, "google_200.txt")

# ── resolver settings ─────────────────────────────────────────────────────────
RESOLVER_WORKERS  = 40      # parallel DNS threads
RESOLVER_TIMEOUT  = 5.0     # seconds per attempt
RESOLVER_RETRIES  = 3       # attempts before giving up on a domain
RESOLVER_BACKOFF  = 1.5     # multiplier between retries (1.5s, 2.25s, …)

# ── protocol patterns ─────────────────────────────────────────────────────────
PROTOCOL_PATTERNS: list[tuple[str, str]] = [
    (r"vmess://",        "vmess"),
    (r"vless://",        "vless"),
    (r"trojan://",       "trojan"),
    (r"ssr://",          "shadowsocksr"),   # must come BEFORE ss://
    (r"ss://",           "shadowsocks"),
    (r"hy2://",          "hysteria2"),
    (r"hysteria2://",    "hysteria2"),
    (r"hysteria://",     "hysteria"),
    (r"tuic://",         "tuic"),
    (r"wireguard://",    "wireguard"),
    (r"wg://",           "wireguard"),
    (r"socks5://",       "socks"),
    (r"socks://",        "socks"),
    (r"naive\+https://", "naive"),
    (r"naive://",        "naive"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), n) for p, n in PROTOCOL_PATTERNS]

# vmess lines are base64 JSON — host is inside the payload, not the URI netloc.
# We parse them separately.
_VMESS_RE = re.compile(r"^vmess://", re.IGNORECASE)

# ── helpers ───────────────────────────────────────────────────────────────────

def _is_ip(host: str) -> bool:
    """Return True if host is already an IPv4 or IPv6 literal."""
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _resolve_once(domain: str) -> Optional[str]:
    """One DNS lookup attempt; returns first IPv4/IPv6 string or None."""
    try:
        results = socket.getaddrinfo(domain, None, socket.AF_UNSPEC,
                                     socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in results:
            ip = sockaddr[0]
            if family in (socket.AF_INET, socket.AF_INET6):
                return ip
    except OSError:
        pass
    return None


def resolve_domain(domain: str) -> str:
    """
    Resolve domain → IP with retries + back-off.
    Returns the IP string, or the original domain on failure.
    """
    if _is_ip(domain):
        return domain

    delay = RESOLVER_BACKOFF
    for attempt in range(RESOLVER_RETRIES):
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(RESOLVER_TIMEOUT)
        try:
            ip = _resolve_once(domain)
        finally:
            socket.setdefaulttimeout(old_timeout)

        if ip:
            return ip

        if attempt < RESOLVER_RETRIES - 1:
            time.sleep(delay)
            delay *= RESOLVER_BACKOFF

    print(f"[resolver] ✗  {domain}  — resolution failed, keeping domain")
    return domain


def _build_cache(domains: set[str]) -> dict[str, str]:
    """Resolve all unique domains concurrently, return {domain: ip_or_domain}."""
    cache: dict[str, str] = {}
    only_domains = {d for d in domains if not _is_ip(d)}

    if not only_domains:
        return {d: d for d in domains}

    print(f"[resolver] Resolving {len(only_domains)} unique domain(s) "
          f"with {RESOLVER_WORKERS} workers …")

    with ThreadPoolExecutor(max_workers=RESOLVER_WORKERS) as pool:
        future_map = {pool.submit(resolve_domain, d): d for d in only_domains}
        for fut in as_completed(future_map):
            domain = future_map[fut]
            try:
                cache[domain] = fut.result()
            except Exception:
                cache[domain] = domain

    # IPs resolve to themselves
    for d in domains - only_domains:
        cache[d] = d

    resolved = sum(1 for d, ip in cache.items() if ip != d)
    print(f"[resolver] ✓  {resolved}/{len(only_domains)} domain(s) resolved to IP")
    return cache


# ── host extraction per scheme ────────────────────────────────────────────────

def _extract_host_standard(uri: str) -> Optional[str]:
    """Extract hostname from a standard URI (vless/trojan/ss/hy2/tuic/…)."""
    try:
        parsed = urlparse(uri)
        host = parsed.hostname  # strips brackets from IPv6
        return host if host else None
    except Exception:
        return None


def _extract_host_vmess(uri: str) -> Optional[str]:
    """Extract hostname from a vmess:// base64-JSON URI."""
    import base64
    try:
        b64 = uri[len("vmess://"):]
        # pad
        b64 += "=" * (-len(b64) % 4)
        data = json.loads(base64.b64decode(b64).decode("utf-8", errors="replace"))
        return data.get("add") or data.get("host") or None
    except Exception:
        return None


def extract_host(line: str) -> Optional[str]:
    if _VMESS_RE.match(line):
        return _extract_host_vmess(line)
    return _extract_host_standard(line)


# ── host replacement per scheme ───────────────────────────────────────────────

def _replace_host_standard(uri: str, new_host: str) -> str:
    """Replace hostname in a standard URI, preserving everything else."""
    try:
        parsed = urlparse(uri)
        old_netloc = parsed.netloc

        # Reconstruct netloc: [userinfo@]<host>[:port]
        # parsed.hostname strips brackets; we need raw host for IPv6
        raw_host = parsed.hostname or ""
        if ":" in new_host and not new_host.startswith("["):
            formatted_host = f"[{new_host}]"   # IPv6 literal needs brackets
        else:
            formatted_host = new_host

        if raw_host:
            # Replace only the host part in the original netloc string
            # to safely preserve userinfo and port
            if ":" in raw_host:                             # was IPv6
                old_host_in_netloc = f"[{raw_host}]"
            else:
                old_host_in_netloc = raw_host

            new_netloc = old_netloc.replace(old_host_in_netloc, formatted_host, 1)
        else:
            new_netloc = old_netloc

        new_parsed = parsed._replace(netloc=new_netloc)
        return urlunparse(new_parsed)
    except Exception:
        return uri


def _replace_host_vmess(uri: str, new_host: str) -> str:
    """Replace the 'add' field inside the vmess base64 payload."""
    import base64
    try:
        b64 = uri[len("vmess://"):]
        b64 += "=" * (-len(b64) % 4)
        data = json.loads(base64.b64decode(b64).decode("utf-8", errors="replace"))
        data["add"] = new_host
        new_b64 = base64.b64encode(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
        ).decode().rstrip("=")
        return f"vmess://{new_b64}"
    except Exception:
        return uri


def replace_host(line: str, new_host: str) -> str:
    if new_host == extract_host(line):   # nothing changed
        return line
    if _VMESS_RE.match(line):
        return _replace_host_vmess(line, new_host)
    return _replace_host_standard(line, new_host)


# ── protocol detection ────────────────────────────────────────────────────────

def detect_protocol(line: str) -> str:
    for pattern, name in _COMPILED:
        if pattern.match(line):
            return name
    return "unknown"


# ── main ──────────────────────────────────────────────────────────────────────

def split_google_200() -> None:
    if not os.path.isfile(INPUT_FILE):
        print(f"[split_by_protocol] ⚠  Input not found: {INPUT_FILE}")
        return

    # ── 1. Read all proxy lines ───────────────────────────────────────────────
    raw_lines: list[str] = []
    with open(INPUT_FILE, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            raw_lines.append(stripped)

    if not raw_lines:
        print("[split_by_protocol] ⚠  google_200.txt is empty or has no proxy lines.")
        return

    print(f"[split_by_protocol] Read {len(raw_lines)} proxy line(s) from google_200.txt")

    # ── 2. Collect all unique hosts ───────────────────────────────────────────
    host_map: dict[int, str] = {}   # line_index → host
    unique_hosts: set[str] = set()

    for idx, line in enumerate(raw_lines):
        host = extract_host(line)
        if host:
            host_map[idx] = host
            unique_hosts.add(host)

    # ── 3. Resolve all domains concurrently ───────────────────────────────────
    dns_cache = _build_cache(unique_hosts)

    # ── 4. Rewrite hosts in URI lines ─────────────────────────────────────────
    resolved_lines: list[str] = []
    rewrites = 0
    for idx, line in enumerate(raw_lines):
        host = host_map.get(idx)
        if host:
            ip = dns_cache.get(host, host)
            if ip != host:
                line = replace_host(line, ip)
                rewrites += 1
        resolved_lines.append(line)

    print(f"[split_by_protocol] ✓  {rewrites} URI(s) had domain replaced with IP")

    # ── 5. Split by protocol ──────────────────────────────────────────────────
    buckets: defaultdict[str, list[str]] = defaultdict(list)
    for line in resolved_lines:
        proto = detect_protocol(line)
        buckets[proto].append(line)

    os.makedirs(CONFIGS_DIR, exist_ok=True)

    for proto, lines in sorted(buckets.items()):
        out_path = os.path.join(CONFIGS_DIR, f"google_200_{proto}.txt")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"[split_by_protocol] ✓  {proto:15s}  {len(lines):>5} proxies  →  configs/google_200_{proto}.txt")

    total = sum(len(v) for v in buckets.values())
    print(f"[split_by_protocol] ✓  Total {total} proxies split into {len(buckets)} protocol file(s).")


if __name__ == "__main__":
    split_google_200()
