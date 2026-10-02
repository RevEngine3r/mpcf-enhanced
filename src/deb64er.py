# src/de_base64.py
"""Normalize an input file to plain-text proxy URIs (no base64 wrappers).

Handles three input shapes:
  1. Already-plain text with one URI per line       -> passed through
  2. Whole-file base64 blob (subscription style)    -> decoded, then split
  3. A mix of both (common for Telegram previews)   -> decoded per-line, then split

Additionally, every individual proxy URI is scanned and any base64-encoded
segment inside it (vmess payload, ss userinfo, ssr payload, trojan password,
query params, fragments, etc.) is decoded in place.

The output is a newline-separated list of plain-text proxy URIs, deduped,
one per line, ready to feed into enricher.py / renamer.py / tester.py.

Usage:
    python src/de_base64.py <input.txt> <output.txt>
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import settings

# local modules
try:
    import parsers  # type: ignore
except ImportError:  # allow running from repo root
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import parsers  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# All proxy schemes we know about
_SCHEME_RE = re.compile(
    r'^(vmess|vless|ss|ssr|trojan|trojan-go|hysteria|hysteria2|hy2|tuic|'
    r'wireguard|wg|snell|brook|juicity|naive|http|https|socks|socks5)://',
    re.I,
)

_B64_CHARS = re.compile(r'^[A-Za-z0-9+/_\-=]+$')


# ---------------------------------------------------------------------------
# base64 helpers
# ---------------------------------------------------------------------------
def _b64decode(s: str) -> str | None:
    """Decode a base64 string (standard or urlsafe), tolerating missing padding."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # urlsafe -> standard
    s = s.replace('-', '+').replace('_', '/')
    pad = (-len(s)) % 4
    try:
        raw = base64.b64decode(s + '=' * pad, validate=False)
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return None


def _b64encode(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('ascii')


def _looks_b64(s: str) -> bool:
    """Heuristic: could this string be base64?"""
    if not s or len(s) < 8:
        return False
    if not _B64_CHARS.match(s):
        return False
    # Must have at least one uppercase, lowercase, or digit mix, and length % 4 == 0 or urlsafe chars
    if len(s) % 4 not in (0, 2, 3):
        return False
    # Try to decode and see if it produces mostly printable text
    dec = _b64decode(s)
    if dec is None:
        return False
    if not dec:
        return False
    printable = sum(1 for c in dec if c.isprintable() or c in '\r\n\t')
    return printable / max(len(dec), 1) > 0.85


def _decode_if_b64(s: str) -> str:
    """If `s` is base64, return decoded; otherwise return `s` unchanged."""
    if _looks_b64(s):
        dec = _b64decode(s)
        if dec is not None:
            return dec
    return s


# ---------------------------------------------------------------------------
# scheme-specific normalizers (decode embedded base64)
# ---------------------------------------------------------------------------
def _norm_vmess(uri: str) -> str | None:
    """vmess://<base64-json>  ->  decode JSON, re-encode canonically."""
    payload = uri[len('vmess://'):]
    frag = ''
    if '#' in payload:
        payload, frag = payload.split('#', 1)
        frag = '#' + frag
    decoded = _b64decode(payload)
    if not decoded:
        return None
    try:
        obj = json.loads(decoded)
    except Exception:
        return None
    if not isinstance(obj, dict) or 'add' not in obj:
        return None
    canon = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
    return f"vmess://{_b64encode(canon)}{frag}"


def _norm_ss(uri: str) -> str | None:
    """
    ss:// forms:
      - ss://<base64(method:password)>@host:port#frag   (SIP002)
      - ss://<base64(method:password@host:port)>#frag   (legacy)
      - ss://<base64(method:password)>@host:port?plugin=...#frag
    Decode whatever base64 is present.
    """
    body = uri[len('ss://'):]
    frag = ''
    if '#' in body:
        body, frag = body.split('#', 1)
        frag = '#' + frag
    query = ''
    if '?' in body:
        body, query = body.split('?', 1)
        query = '?' + query

    if '@' in body:
        userinfo, hostport = body.rsplit('@', 1)
        dec = _b64decode(userinfo)
        if dec and ':' in dec:
            userinfo = dec
        return f"ss://{userinfo}@{hostport}{query}{frag}"
    else:
        # whole body is base64
        dec = _b64decode(body)
        if not dec or '@' not in dec:
            return None
        return f"ss://{dec}{query}{frag}"


def _norm_ssr(uri: str) -> str | None:
    """ssr://<base64(host:port:proto:method:obfs:base64pass/?params)>"""
    body = uri[len('ssr://'):]
    dec = _b64decode(body)
    if not dec:
        return None
    # SSR body format: host:port:protocol:method:obfs:base64(password)/?params
    # We re-encode as-is but canonical (compact)
    return f"ssr://{_b64encode(dec)}"


def _norm_trojan(uri: str) -> str | None:
    """trojan://password@host:port?params#frag
    password may be URL-encoded; query values may be base64 too (rare).
    """
    # Leave as-is but try decoding any obviously-base64 query values.
    return _decode_query_values(uri)


def _decode_query_values(uri: str) -> str:
    """Decode base64-looking query parameter values in a URI."""
    try:
        parts = urlsplit(uri)
    except Exception:
        return uri
    if not parts.query:
        return uri
    new_q = []
    changed = False
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        dec = _decode_if_b64(v)
        if dec != v:
            changed = True
        new_q.append((k, dec))
    if not changed:
        return uri
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(new_q, doseq=True),
        parts.fragment,
    ))


def _norm_generic(uri: str) -> str | None:
    """Generic fallback: decode query values, leave the rest alone."""
    return _decode_query_values(uri)


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------
def _normalize_uri(uri: str) -> str | None:
    uri = uri.strip()
    if not uri:
        return None
    low = uri.lower()
    if low.startswith('vmess://'):
        return _norm_vmess(uri)
    if low.startswith('ssr://'):
        return _norm_ssr(uri)
    if low.startswith('ss://'):
        return _norm_ss(uri)
    if _SCHEME_RE.match(uri):
        return _norm_generic(uri)
    return None


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def de_base64_text(text: str) -> list[str]:
    """Return a deduped list of fully-decoded plain-text proxy URIs."""
    raw_blobs: list[str] = []

    # 1) Whole-file base64 subscription blob?
    compact = "".join(text.split())
    if len(compact) >= 64 and "://" not in compact:
        try:
            if parsers.is_base64(compact):
                decoded = parsers.safe_b64decode(compact)
                if decoded and "://" in decoded:
                    raw_blobs.append(decoded)
                    log.info("decoded whole-file base64 blob")
        except Exception:
            pass

    raw_blobs.append(text)

    # 2) Split into individual candidate URI lines
    candidates: list[str] = []
    for blob in raw_blobs:
        split: list[str] = []
        try:
            split = list(parsers.split_configs(blob))
        except Exception:
            split = []

        # Fallback: line-by-line, decoding each line if it's a raw base64 blob
        if not split:
            for line in blob.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "://" not in line and _looks_b64(line):
                    dec = _b64decode(line)
                    if dec and "://" in dec:
                        split.extend(dec.splitlines())
                        continue
                split.append(line)
        else:
            # Even when split_configs works, expand any raw base64 lines it left in
            expanded: list[str] = []
            for cand in split:
                cand = cand.strip()
                if not cand:
                    continue
                if "://" not in cand and _looks_b64(cand):
                    dec = _b64decode(cand)
                    if dec and "://" in dec:
                        expanded.extend(dec.splitlines())
                        continue
                expanded.append(cand)
            split = expanded

        candidates.extend(split)

    # 3) Normalize each candidate (decodes embedded base64)
    out: list[str] = []
    seen: set[str] = set()
    for cand in candidates:
        cand = cand.strip()
        if not cand:
            continue
        norm = _normalize_uri(cand)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)

    log.info(f"de_base64_text: {len(out)} unique URIs")
    return out


def de_base64_file(input_file: str, output_file: str) -> int:
    with open(input_file, encoding="utf-8") as f:
        text = f.read()

    uris = de_base64_text(text)
    log.info(f"{input_file}: {len(uris)} plain-text URIs")

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for uri in uris:
            f.write(uri + "\n")

    log.info(f"wrote {len(uris)} -> {output_file}")
    return len(uris)


def main() -> None:
    de_base64_file(settings.MERGED_FILE, settings.MERGED_FILE)


if __name__ == "__main__":
    main()