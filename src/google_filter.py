"""google_filter.py

Tests every proxy in proxy_configs.txt by routing a HEAD request to
https://aistudio.google.com/ through that proxy (via a temporary Xray
HTTP inbound).  Proxies that return HTTP 200 are written to:

  configs/proxy_configs_g200.txt      – plain text (Hiddify)
  configs/proxy_configs_v2n_g200.txt  – Base64-encoded (v2rayNG / NekoBox)

Usage:
    python src/google_filter.py [input.txt]
"""
import base64
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
from typing import Optional, Tuple

import requests

sys.path.insert(0, os.path.dirname(__file__))
import config_parser as parser
import transport_builder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_URL    = 'https://aistudio.google.com/'
XRAY_PATH     = 'xray'
TIMEOUT       = 20           # seconds per proxy
MAX_WORKERS   = 6
SKIP_PROTOCOLS = {'tuic://', 'wireguard://', 'hysteria2://', 'hy2://'}


# ---------------------------------------------------------------------------
# Helpers shared with xray_config_tester
# ---------------------------------------------------------------------------

def find_free_port() -> int:
    for _ in range(10):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('127.0.0.1', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = s.getsockname()[1]
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as t:
                    t.settimeout(0.1)
                    t.connect(('127.0.0.1', port))
            except (socket.error, socket.timeout):
                return port
    raise RuntimeError("Cannot find a free port")


def build_xray_outbound(config_str: str) -> Optional[dict]:
    """Parse a proxy URI into an Xray outbound dict."""
    lower = config_str.lower()
    try:
        if lower.startswith('vmess://'):
            data = parser.decode_vmess(config_str)
            if not data:
                return None
            return {
                'protocol': 'vmess',
                'settings': {
                    'vnext': [{
                        'address': data.get('add'),
                        'port': int(data.get('port', 0)),
                        'users': [{
                            'id': data.get('id'),
                            'alterId': int(data.get('aid', 0)),
                            'security': data.get('scy', 'auto'),
                        }],
                    }]
                },
                'streamSettings': transport_builder.build_xray_settings(data),
            }

        if lower.startswith('vless://'):
            data = parser.parse_vless(config_str)
            if not data:
                return None
            return {
                'protocol': 'vless',
                'settings': {
                    'vnext': [{
                        'address': data['address'],
                        'port': data['port'],
                        'users': [{
                            'id': data['uuid'],
                            'encryption': 'none',
                            'flow': data.get('flow', ''),
                        }],
                    }]
                },
                'streamSettings': transport_builder.build_xray_settings(data),
            }

        if lower.startswith('trojan://'):
            data = parser.parse_trojan(config_str)
            if not data:
                return None
            return {
                'protocol': 'trojan',
                'settings': {
                    'servers': [{
                        'address': data['address'],
                        'port': data['port'],
                        'password': data['password'],
                    }]
                },
                'streamSettings': transport_builder.build_xray_settings(data),
            }

        if lower.startswith('ss://'):
            data = parser.parse_shadowsocks(config_str)
            if not data:
                return None
            return {
                'protocol': 'shadowsocks',
                'settings': {
                    'servers': [{
                        'address': data['address'],
                        'port': data['port'],
                        'method': data['method'],
                        'password': data['password'],
                    }]
                },
            }
    except Exception as exc:
        logger.debug(f"parse error: {exc}")
    return None


def test_single(config_str: str) -> Tuple[bool, str]:
    """Return (passed, config_str).  Spins up a temporary Xray HTTP proxy."""
    lower = config_str.lower()
    for skip in SKIP_PROTOCOLS:
        if lower.startswith(skip):
            logger.info(f"⊘ skip unsupported: {skip}")
            return False, config_str

    outbound = build_xray_outbound(config_str)
    if outbound is None:
        return False, config_str

    http_port = find_free_port()
    xray_cfg = {
        'log': {'loglevel': 'error'},
        'inbounds': [{'port': http_port, 'protocol': 'http'}],
        'outbounds': [outbound],
    }

    fd, cfg_path = tempfile.mkstemp(suffix='.json', prefix='gf_')
    try:
        with os.fdopen(fd, 'w') as fh:
            json.dump(xray_cfg, fh)

        proc = subprocess.Popen(
            [XRAY_PATH, 'run', '-c', cfg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        try:
            time.sleep(2.5)
            if proc.poll() is not None:
                return False, config_str

            proxies = {
                'http':  f'http://127.0.0.1:{http_port}',
                'https': f'http://127.0.0.1:{http_port}',
            }
            resp = requests.head(
                TARGET_URL,
                proxies=proxies,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            ok = resp.status_code == 200
            logger.info(f"{'✓' if ok else '✗'} {resp.status_code} – {config_str[:60]}")
            return ok, config_str

        except Exception as exc:
            logger.debug(f"request error: {exc}")
            return False, config_str
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
        time.sleep(0.2)


def load_lines(path: str) -> list[str]:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return [
                l.strip() for l in fh
                if l.strip() and not l.startswith('//')
            ]
    except FileNotFoundError:
        logger.error(f"Not found: {path}")
        return []


def write_plain(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(line + '\n\n')


def write_v2n(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    encoded = base64.b64encode('\n'.join(lines).encode()).decode()
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(encoded + '\n')


def main() -> None:
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'configs/proxy_configs.txt'

    lines = load_lines(input_file)
    if not lines:
        logger.error("No proxy lines – aborting.")
        sys.exit(0)

    logger.info(f"Testing {len(lines)} proxies against {TARGET_URL} …")
    passing: list[str] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(test_single, l): l for l in lines}
        done = 0
        for fut in as_completed(futures):
            done += 1
            ok, cfg = fut.result()
            if ok:
                passing.append(cfg)
            if done % 20 == 0 or done == len(lines):
                logger.info(f"Progress {done}/{len(lines)} – {len(passing)} passing")

    logger.info(f"{len(passing)} proxies passed the Google 200 filter.")

    write_plain('configs/proxy_configs_g200.txt',     passing)
    write_v2n  ('configs/proxy_configs_v2n_g200.txt', passing)
    logger.info("Written: configs/proxy_configs_g200.txt  |  configs/proxy_configs_v2n_g200.txt")


if __name__ == '__main__':
    main()
