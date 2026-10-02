"""Proxy URI parsing, validation, and text extraction.

Public API:
    split_configs(text)   -> list[str]      (extract every URI from a blob)
    parse_config(uri)     -> dict | None    (normalized dict for one URI)
    extract_address(uri)  -> str | None     (just the hostname)
    is_valid(uri)         -> bool
"""
import base64
import binascii
import json
import re
from functools import lru_cache
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from settings import ALL_PROTOCOLS

# =============================================================================
# Base64 helpers
# =============================================================================

_B64_RE = re.compile(r"^[A-Za-z0-9+/\-_]+={0,2}$")


def is_base64(s: str) -> bool:
    return bool(s) and len(s) >= 4 and bool(_B64_RE.match(s))


@lru_cache(maxsize=4096)
def safe_b64decode(s: str) -> Optional[str]:
    if not s:
        return None
    s2 = s.replace("-", "+").replace("_", "/")
    s2 += "=" * (-len(s2) % 4)
    try:
        return base64.b64decode(s2, validate=True).decode("utf-8", "strict")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        try:
            return base64.b64decode(s2).decode("utf-8", "ignore")
        except Exception:
            return None


# =============================================================================
# Text -> list of URIs
# =============================================================================

def split_configs(text: str) -> list[str]:
    """Extract every proxy URI from arbitrary text (base64-aware, deduped)."""
    results: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Try base64-decoding the whole line first (common in Telegram posts).
        if len(line) >= 64 and is_base64(line):
            decoded = safe_b64decode(line)
            if decoded and any(f"{p}://" in decoded for p in ALL_PROTOCOLS):
                line = decoded

        for uri in _split_by_protocol(line):
            if uri not in seen:
                seen.add(uri)
                results.append(uri)

    return results


def _split_by_protocol(text: str) -> list[str]:
    """Cut text into segments starting at each protocol marker."""
    markers: list[tuple[int, str]] = []
    for proto in ALL_PROTOCOLS:
        marker = f"{proto}://"
        start = 0
        while True:
            idx = text.find(marker, start)
            if idx == -1:
                break
            # Marker must start at a word boundary to avoid false positives.
            if idx == 0 or text[idx - 1] in " \t\n<>\"'":
                markers.append((idx, proto))
            start = idx + len(marker)

    if not markers:
        return []

    markers.sort()
    out: list[str] = []
    for i, (idx, proto) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        uri = _trim_uri(text[idx:end])

        if proto == "vmess":
            uri = _clean_vmess(uri)
        elif proto == "hy2":
            uri = "hysteria2://" + uri[len("hy2://"):]

        if uri:
            out.append(uri)
    return out


_CUT_CHARS = (" ", "\t", "\n", "\r", "<", '"', "'")


def _trim_uri(raw: str) -> str:
    raw = raw.strip()
    for ch in _CUT_CHARS:
        idx = raw.find(ch)
        if idx != -1:
            raw = raw[:idx]
    return re.sub(r"[\x00-\x1f\x7f]", "", raw).strip()


def _clean_vmess(uri: str) -> str:
    body = uri[len("vmess://"):]
    m = re.match(r"[A-Za-z0-9+/=_-]+", body)
    return f"vmess://{m.group(0)}" if m else uri


# =============================================================================
# Single-URI parsers
# =============================================================================

def _first(params: dict, key: str, default: str = "") -> str:
    v = params.get(key)
    if not v:
        return default
    return v[0] if isinstance(v, list) else v


def _to_int(v, default=None):
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def parse_vmess(uri: str) -> Optional[dict]:
    decoded = safe_b64decode(uri[len("vmess://"):])
    if not decoded:
        return None
    try:
        d = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    if not all(d.get(k) for k in ("add", "port", "id")):
        return None
    port = _to_int(d["port"])
    if port is None:
        return None
    d["port"] = port
    d["_scheme"] = "vmess"
    d["name"] = d.get("ps", d.get("name", ""))
    return d


def parse_vless(uri: str) -> Optional[dict]:
    url = urlparse(uri)
    if not url.hostname or not url.username:
        return None
    q = parse_qs(url.query, keep_blank_values=True)
    return {
        "_scheme": "vless",
        "uuid": unquote(url.username),
        "address": url.hostname,
        "port": url.port or 443,
        "flow": _first(q, "flow").lower(),
        "sni": _first(q, "sni", url.hostname),
        "type": _first(q, "type", "tcp").lower(),
        "path": _first(q, "path"),
        "host": _first(q, "host", url.hostname),
        "security": _first(q, "security", "none").lower(),
        "alpn": _first(q, "alpn"),
        "fp": _first(q, "fp"),
        "pbk": _first(q, "pbk"),
        "sid": _first(q, "sid"),
        "spx": _first(q, "spx"),
        "name": unquote(url.fragment) if url.fragment else "",
    }


def parse_trojan(uri: str) -> Optional[dict]:
    url = urlparse(uri)
    if not url.hostname or not url.username:
        return None
    q = parse_qs(url.query, keep_blank_values=True)
    return {
        "_scheme": "trojan",
        "password": unquote(url.username),
        "address": url.hostname,
        "port": url.port or 443,
        "sni": _first(q, "sni", url.hostname),
        "alpn": _first(q, "alpn"),
        "type": _first(q, "type", "tcp").lower(),
        "path": _first(q, "path"),
        "host": _first(q, "host", url.hostname),
        "security": _first(q, "security", "tls"),
        "fp": _first(q, "fp"),
        "flow": _first(q, "flow"),
        "name": unquote(url.fragment) if url.fragment else "",
    }


def parse_hysteria2(uri: str) -> Optional[dict]:
    url = urlparse(uri)
    if not url.hostname:
        return None
    q = parse_qs(url.query, keep_blank_values=True)
    password = unquote(url.username) if url.username else _first(q, "password")
    if not password:
        return None
    return {
        "_scheme": "hysteria2",
        "address": url.hostname,
        "port": url.port or 443,
        "password": password,
        "sni": _first(q, "sni", url.hostname),
        "obfs": _first(q, "obfs"),
        "obfs-password": _first(q, "obfs-password"),
        "insecure": _first(q, "insecure", "0"),
        "pinSHA256": _first(q, "pinSHA256"),
        "name": unquote(url.fragment) if url.fragment else "",
    }


def parse_shadowsocks(uri: str) -> Optional[dict]:
    body = uri[len("ss://"):]
    fragment = ""
    if "#" in body:
        body, fragment = body.split("#", 1)

    query = ""
    if "?" in body:
        body, query = body.split("?", 1)

    try:
        if "@" in body:
            credential, server = body.split("@", 1)
            credential = unquote(credential)
            if is_base64(credential):
                decoded = safe_b64decode(credential)
                if not decoded or ":" not in decoded:
                    return None
                method, password = decoded.split(":", 1)
            else:
                if ":" not in credential:
                    return None
                method, password = credential.split(":", 1)
        else:
            decoded = safe_b64decode(body)
            if not decoded or "@" not in decoded:
                return None
            credential, server = decoded.split("@", 1)
            if ":" not in credential:
                return None
            method, password = credential.split(":", 1)

        if ":" not in server:
            return None
        host, port_str = server.rsplit(":", 1)
        host = host.strip("[]")
        port = _to_int(port_str)
        if port is None:
            return None
    except Exception:
        return None

    return {
        "_scheme": "ss",
        "method": method.lower().strip(),
        "password": password,
        "address": host,
        "port": port,
        "plugin": query,
        "name": unquote(fragment) if fragment else "",
    }


def parse_shadowsocksr(uri: str) -> Optional[dict]:
    decoded = safe_b64decode(uri[len("ssr://"):])
    if not decoded:
        return None
    main, _, query = decoded.partition("?")
    parts = main.split(":")
    if len(parts) < 6:
        return None
    host = parts[0]
    port = _to_int(parts[1])
    if port is None:
        return None
    params = parse_qs(query, keep_blank_values=True)
    name_b64 = _first(params, "remarks")
    return {
        "_scheme": "ssr",
        "address": host,
        "port": port,
        "protocol": parts[2],
        "method": parts[3],
        "obfs": parts[4],
        "password": safe_b64decode(":".join(parts[5:])) or ":".join(parts[5:]),
        "protocol_param": safe_b64decode(_first(params, "protoparam")) or "",
        "obfs_param": safe_b64decode(_first(params, "obfsparam")) or "",
        "name": safe_b64decode(name_b64) if name_b64 else "",
    }


def parse_wireguard(uri: str) -> Optional[dict]:
    url = urlparse(uri)
    if not url.hostname:
        return None
    q = parse_qs(url.query, keep_blank_values=True)
    private_key = unquote(url.username) if url.username else _first(q, "privatekey")
    if not private_key:
        return None
    return {
        "_scheme": "wireguard",
        "address": url.hostname,
        "port": url.port or 51820,
        "private_key": private_key,
        "public_key": _first(q, "publickey"),
        "preshared_key": _first(q, "presharedkey"),
        "reserved": _first(q, "reserved"),
        "mtu": _first(q, "mtu", "1420"),
        "local_address": _first(q, "address"),
        "peers": q.get("peer", []),
        "name": unquote(url.fragment) if url.fragment else "",
    }


def parse_tuic(uri: str) -> Optional[dict]:
    url = urlparse(uri)
    if not url.hostname or not url.username or ":" not in url.username:
        return None
    uuid, password = unquote(url.username).split(":", 1)
    q = parse_qs(url.query, keep_blank_values=True)
    return {
        "_scheme": "tuic",
        "address": url.hostname,
        "port": url.port or 443,
        "uuid": uuid,
        "password": password,
        "congestion_control": _first(q, "congestion_control", "bbr"),
        "udp_relay_mode": _first(q, "udp_relay_mode", "native"),
        "alpn": _first(q, "alpn", "h3"),
        "sni": _first(q, "sni", url.hostname),
        "allow_insecure": _first(q, "allow_insecure", "0"),
        "disable_sni": _first(q, "disable_sni", "0"),
        "name": unquote(url.fragment) if url.fragment else "",
    }


# =============================================================================
# Dispatcher
# =============================================================================

_PARSERS = {
    "vmess": parse_vmess,
    "vless": parse_vless,
    "trojan": parse_trojan,
    "hysteria2": parse_hysteria2,
    "hy2": parse_hysteria2,
    "ss": parse_shadowsocks,
    "ssr": parse_shadowsocksr,
    "wireguard": parse_wireguard,
    "tuic": parse_tuic,
}


def parse_config(uri: str) -> Optional[dict]:
    """Parse a single proxy URI. Returns a normalized dict or None."""
    if not uri or "://" not in uri:
        return None
    scheme = uri.split("://", 1)[0].lower()
    fn = _PARSERS.get(scheme)
    if fn is None:
        return None
    try:
        return fn(uri)
    except Exception:
        return None


def extract_address(uri: str) -> Optional[str]:
    d = parse_config(uri)
    return d.get("address") if d else None


def is_valid(uri: str) -> bool:
    return parse_config(uri) is not None
