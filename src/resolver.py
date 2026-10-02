# src/ipresolver.py
"""Resolve hostnames in a proxy-URI file to IPs.

Reads every proxy URI from the input file, extracts the hostname via
parsers.parse_config(), resolves it to an IP (IPv4 preferred, IPv6 fallback),
and writes a new file where each URI's hostname has been replaced by its IP.

DNS results are cached in memory for the lifetime of the process only
(no on-disk cache). Unresolvable hosts are left untouched unless --drop
is given, in which case those configs are omitted entirely.

Usage:
    python src/ipresolver.py <input.txt> [output.txt] [--drop]
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import logging
import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse, urlunparse, quote, unquote

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

DNS_TIMEOUT = 5  # seconds per getaddrinfo call
MAX_WORKERS = 32

# Drop no ip from dns ?
DROP = False

# In-memory cache: host -> IP (str) or None if the lookup failed.
# Lives only for the process. A None value means "already tried, no answer",
# so we never re-query the same failed host during one run.
_dns_cache: dict[str, Optional[str]] = {}


# ---------------------------------------------------------------------------
# DNS resolution
# ---------------------------------------------------------------------------

def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def resolve_host(host: str) -> Optional[str]:
    """Return an IP string for `host`, or None. IPv4 preferred.

    Results (including failures) are memoized in `_dns_cache`.
    """
    if not host:
        return None

    # already an IP -> return as-is (but don't cache this trivial case)
    if _is_ip(host):
        return host.strip("[]")

    if host in _dns_cache:
        return _dns_cache[host]

    socket.setdefaulttimeout(DNS_TIMEOUT)
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        _dns_cache[host] = None
        return None
    except Exception:
        _dns_cache[host] = None
        return None
    finally:
        socket.setdefaulttimeout(None)

    v4: list[str] = []
    v6: list[str] = []
    for fam, _, _, _, sockaddr in infos:
        addr = sockaddr[0]
        if fam == socket.AF_INET:
            v4.append(addr)
        elif fam == socket.AF_INET6:
            v6.append(addr)

    ip = v4[0] if v4 else (v6[0] if v6 else None)
    _dns_cache[host] = ip
    return ip


def cache_stats() -> tuple[int, int]:
    """(hits_with_ip, misses) — useful for the end-of-run summary."""
    ok = sum(1 for v in _dns_cache.values() if v)
    bad = sum(1 for v in _dns_cache.values() if v is None)
    return ok, bad


# ---------------------------------------------------------------------------
# URI hostname replacement
# ---------------------------------------------------------------------------

def _replace_host_in_url(uri: str, new_host: str) -> str:
    """Replace the hostname in a scheme://user:pass@host:port/... URI."""
    try:
        p = urlparse(uri)
    except Exception:
        return uri
    if not p.hostname:
        return uri

    userinfo = ""
    if p.username is not None:
        userinfo = quote(unquote(p.username), safe="")
        if p.password is not None:
            userinfo += ":" + quote(unquote(p.password), safe="")
        userinfo += "@"

    host_part = f"[{new_host}]" if ":" in new_host else new_host
    netloc = f"{userinfo}{host_part}"
    if p.port is not None:
        netloc += f":{p.port}"

    return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))


def _replace_host_in_vmess(uri: str, new_host: str) -> str:
    decoded = parsers.safe_b64decode(uri[len("vmess://"):])
    if not decoded:
        return uri
    try:
        d = json.loads(decoded)
    except json.JSONDecodeError:
        return uri
    if not isinstance(d, dict) or not d.get("add"):
        return uri
    d["add"] = new_host
    encoded = base64.b64encode(
        json.dumps(d, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    return f"vmess://{encoded}"


def _replace_host_in_ssr(uri: str, new_host: str) -> str:
    decoded = parsers.safe_b64decode(uri[len("ssr://"):])
    if not decoded:
        return uri
    # SSR format: host:port:proto:method:obfs:password_b64/?params
    main, sep, query = decoded.partition("?")
    parts = main.split(":")
    if len(parts) < 6:
        return uri
    parts[0] = new_host
    rebuilt = ":".join(parts) + (sep + query if sep else "")
    encoded = base64.urlsafe_b64encode(rebuilt.encode("utf-8")).decode("ascii").rstrip("=")
    return f"ssr://{encoded}"


def replace_host(uri: str, new_host: str) -> str:
    """Return `uri` with its hostname replaced by `new_host`."""
    scheme = uri.split("://", 1)[0].lower()
    if scheme == "vmess":
        return _replace_host_in_vmess(uri, new_host)
    if scheme == "ssr":
        return _replace_host_in_ssr(uri, new_host)
    return _replace_host_in_url(uri, new_host)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def read_configs(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [
                l.strip()
                for l in f
                if l.strip() and not l.startswith("//")
            ]
    except FileNotFoundError:
        log.error(f"{path} not found")
        return []


def write_configs(path: str, configs: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(settings.SUBSCRIPTION_HEADER)
        f.write("\n")
        for c in configs:
            f.write(c + "\n\n")
    log.info(f"wrote {len(configs)} -> {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    configs = read_configs(settings.MERGED_FILE)
    if not configs:
        log.error("no configs to process")
        sys.exit(0)

    # First pass: collect unique hostnames.
    host_of: dict[str, str] = {}  # uri -> host
    hosts: set[str] = set()
    for uri in configs:
        d = parsers.parse_config(uri)
        if not d:
            continue
        host = d.get("address") or d.get("add")
        if not host:
            continue
        host_of[uri] = host
        if not _is_ip(host):
            hosts.add(host)

    log.info(f"{len(configs)} configs, {len(hosts)} unique hostnames to resolve")

    if hosts:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(resolve_host, h): h for h in hosts}
            done = 0
            for fut in as_completed(futures):
                done += 1
                if done % 25 == 0 or done == len(hosts):
                    log.info(f"  resolved {done}/{len(hosts)}")
                try:
                    fut.result()
                except Exception as e:
                    log.debug(f"resolve error: {e}")

    ok, bad = cache_stats()
    log.info(f"dns cache: {ok} resolved, {bad} failed")

    # Second pass: substitute.
    out: list[str] = []
    dropped = 0
    for uri in configs:
        host = host_of.get(uri)
        if not host:
            out.append(uri)  # unparseable -> pass through unchanged
            continue
        if _is_ip(host):
            out.append(uri)
            continue

        ip = _dns_cache.get(host)
        if not ip:
            if DROP:
                dropped += 1
                continue
            out.append(uri)
            continue

        try:
            out.append(replace_host(uri, ip))
        except Exception as e:
            log.debug(f"replace_host failed for {host}: {e}")
            out.append(uri)

    write_configs(settings.MERGED_FILE, out)
    if dropped:
        log.info(f"dropped {dropped} configs with unresolvable hosts")


if __name__ == "__main__":
    main()
