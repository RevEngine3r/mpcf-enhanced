"""Test every candidate config through a short-lived Xray HTTP inbound.

Buckets the outcome:
    google200 -> HEAD https://dl.google.com/... returned HTTP 200
    working   -> HTTP response but non-200
    failed    -> no usable response

Writes:
    configs/all_working.txt
    configs/google_200.txt

Usage:
    python src/tester.py
"""
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from typing import Optional

import requests

import parsers
import settings
import transport

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Port helper
# ---------------------------------------------------------------------------

def find_free_port() -> int:
    for _ in range(20):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("127.0.0.1", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = s.getsockname()[1]
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as t:
                    t.settimeout(0.05)
                    t.connect(("127.0.0.1", port))
            except (socket.error, socket.timeout):
                return port
    raise RuntimeError("cannot find a free port")


# ---------------------------------------------------------------------------
# URI -> Xray outbound
# ---------------------------------------------------------------------------

def build_outbound(uri: str) -> Optional[dict]:
    scheme = uri.split("://", 1)[0].lower()
    d = parsers.parse_config(uri)
    if not d:
        return None

    try:
        if scheme == "vmess":
            return {
                "protocol": "vmess",
                "settings": {"vnext": [{
                    "address": d["add"],
                    "port": int(d["port"]),
                    "users": [{
                        "id": d["id"],
                        "alterId": int(d.get("aid", 0)),
                        "security": d.get("scy", "auto"),
                    }],
                }]},
                "streamSettings": transport.build_xray_settings(d),
            }
        if scheme == "vless":
            return {
                "protocol": "vless",
                "settings": {"vnext": [{
                    "address": d["address"],
                    "port": d["port"],
                    "users": [{
                        "id": d["uuid"],
                        "encryption": "none",
                        "flow": d.get("flow", ""),
                    }],
                }]},
                "streamSettings": transport.build_xray_settings(d),
            }
        if scheme == "trojan":
            return {
                "protocol": "trojan",
                "settings": {"servers": [{
                    "address": d["address"],
                    "port": d["port"],
                    "password": d["password"],
                }]},
                "streamSettings": transport.build_xray_settings(d),
            }
        if scheme == "ss":
            return {
                "protocol": "shadowsocks",
                "settings": {"servers": [{
                    "address": d["address"],
                    "port": d["port"],
                    "method": d["method"],
                    "password": d["password"],
                }]},
            }
    except Exception as e:
        log.debug(f"build_outbound error for {uri[:60]}: {e}")
    return None


# ---------------------------------------------------------------------------
# Single proxy test
# ---------------------------------------------------------------------------

def test_proxy(uri: str) -> tuple[str, str]:
    scheme = uri.split("://", 1)[0].lower()
    if scheme in settings.XRAY_SKIP_PROTOCOLS:
        return "failed", uri

    outbound = build_outbound(uri)
    if outbound is None:
        return "failed", uri

    port = find_free_port()
    cfg = {
        "log": {"loglevel": "none"},
        "inbounds": [{"port": port, "protocol": "http", "listen": "127.0.0.1"}],
        "outbounds": [outbound],
    }

    fd, cfg_path = tempfile.mkstemp(suffix=".json", prefix="ut_")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(cfg, fh)

        proc = subprocess.Popen(
            [settings.XRAY_BINARY, "run", "-c", cfg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        try:
            time.sleep(settings.XRAY_STARTUP_DELAY)
            if proc.poll() is not None:
                return "failed", uri

            proxies = {
                "http": f"http://127.0.0.1:{port}",
                "https": f"http://127.0.0.1:{port}",
            }
            r = requests.head(
                settings.XRAY_TARGET,
                proxies=proxies,
                timeout=settings.XRAY_REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if r.status_code == 200:
                log.info(f"✓ google200  {uri[:70]}")
                return "google200", uri
            log.info(f"✓ working({r.status_code})  {uri[:70]}")
            return "working", uri
        except (requests.exceptions.ProxyError, requests.exceptions.Timeout):
            return "failed", uri
        except Exception as e:
            log.debug(f"request error: {e}")
            return "failed", uri
        finally:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=2)
            except Exception:
                pass
    finally:
        try:
            os.unlink(cfg_path)
        except Exception:
            pass
        time.sleep(0.1)


# ---------------------------------------------------------------------------
# File I/O + dedup
# ---------------------------------------------------------------------------

def read_lines(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("//")]
    except FileNotFoundError:
        return []


def write_lines(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")


def uri_key(line: str) -> str:
    return line.split("#", 1)[0].strip()


def merge_dedup(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for line in lst:
            key = uri_key(line)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(line)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    merged = read_lines(settings.MERGED_FILE)

    if not merged:
        log.error("nothing to test (no fetched.txt, no all_working.txt)")
        sys.exit(0)

    pool = merge_dedup(merged)
    log.info(
        f"pool: merged={len(merged)} merged={len(pool)}"
    )

    all_working: list[str] = []
    google200: list[str] = []

    with ThreadPoolExecutor(max_workers=settings.XRAY_MAX_WORKERS) as ex:
        futures = {ex.submit(test_proxy, uri): uri for uri in pool}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                result, uri = fut.result(timeout=settings.XRAY_REQUEST_TIMEOUT + 10)
            except Exception as e:
                log.error(f"future error: {e}")
                continue

            if result in ("working", "google200"):
                all_working.append(uri)
            if result == "google200":
                google200.append(uri)

            if done % 25 == 0 or done == len(pool):
                log.info(
                    f"progress {done}/{len(pool)} | "
                    f"all_working={len(all_working)} | google200={len(google200)}"
                )

    write_lines(settings.ALL_WORKING_FILE, all_working)
    log.info(f"wrote {len(all_working)} -> {settings.ALL_WORKING_FILE}")

    write_lines(settings.GOOGLE200_FILE, google200)
    log.info(f"wrote {len(google200)} -> {settings.GOOGLE200_FILE}")

    try:
        os.remove(settings.FETCHED_FILE)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
