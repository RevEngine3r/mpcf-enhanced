"""unified_tester.py

Single-pass proxy tester:
  1. Spins up a temporary Xray HTTP inbound per proxy.
  2. Fires a HEAD request to https://aistudio.google.com/ through it.
  3. Buckets the result:
       - HTTP 200  -> google_200 list
       - working but non-200 -> all_working list
       - failed    -> discarded

Outputs (plain-text, one URI per line + blank separator):
  configs/all_working.txt
  configs/google_200.txt
  configs/hiddify_all_working.txt   (identical content to all_working)
  configs/hiddify_google_200.txt    (identical content to google_200)
  configs/hiddify_all_detour.txt    (all_working with NL landing proxy chain)

Usage:
  python src/unified_tester.py [input.txt]
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
from typing import Optional, Tuple
from urllib.parse import unquote

import requests

sys.path.insert(0, os.path.dirname(__file__))
import config_parser as parser
import transport_builder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GOOGLE_TARGET  = 'https://aistudio.google.com/'
XRAY_PATH      = 'xray'
TIMEOUT        = 15
STARTUP_DELAY  = 2.0
MAX_WORKERS    = max(4, (os.cpu_count() or 4) * 2)

SKIP_PROTOCOLS = {'tuic://', 'wireguard://', 'hysteria2://', 'hy2://'}

# Landing proxy for the detour chain.
# LANDING_TAG must be the exact decoded fragment of LANDING_PROXY
# (i.e. what appears after '#', percent-decoded) so Hiddify can resolve it.
LANDING_PROXY_RAW = (
    'ss://YWVzLTEyOC1jZmI6c2hhZG93c29ja3M=@109.201.152.181:443'
    '#%F0%9F%94%92%20SS-TCP-NA%20%F0%9F%87%B3%F0%9F%87%B1%20NL-109.201.152.181:443'
)
# Decoded name of the landing proxy — this is what Hiddify sees as the tag.
LANDING_TAG = unquote(
    LANDING_PROXY_RAW.split('#', 1)[1]
)  # → "🔒 SS-TCP-NA 🇳🇱 NL-109.201.152.181:443"

# Write the landing proxy with its decoded fragment so all names in the file
# are consistent plain-text (Hiddify reads fragments as plain text).
LANDING_PROXY = (
    LANDING_PROXY_RAW.split('#')[0] + '#' + LANDING_TAG
)


# ---------------------------------------------------------------------------
# Port helper
# ---------------------------------------------------------------------------
def find_free_port() -> int:
    for _ in range(20):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('127.0.0.1', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = s.getsockname()[1]
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as t:
                    t.settimeout(0.05)
                    t.connect(('127.0.0.1', port))
            except (socket.error, socket.timeout):
                return port
    raise RuntimeError('Cannot find a free port')


# ---------------------------------------------------------------------------
# Proxy URI -> Xray outbound dict
# ---------------------------------------------------------------------------
def build_outbound(uri: str) -> Optional[dict]:
    low = uri.lower()
    try:
        if low.startswith('vmess://'):
            d = parser.decode_vmess(uri)
            if not d:
                return None
            return {
                'protocol': 'vmess',
                'settings': {'vnext': [{
                    'address': d.get('add'),
                    'port': int(d.get('port', 0)),
                    'users': [{
                        'id': d.get('id'),
                        'alterId': int(d.get('aid', 0)),
                        'security': d.get('scy', 'auto'),
                    }],
                }]},
                'streamSettings': transport_builder.build_xray_settings(d),
            }

        if low.startswith('vless://'):
            d = parser.parse_vless(uri)
            if not d:
                return None
            return {
                'protocol': 'vless',
                'settings': {'vnext': [{
                    'address': d['address'],
                    'port': d['port'],
                    'users': [{
                        'id': d['uuid'],
                        'encryption': 'none',
                        'flow': d.get('flow', ''),
                    }],
                }]},
                'streamSettings': transport_builder.build_xray_settings(d),
            }

        if low.startswith('trojan://'):
            d = parser.parse_trojan(uri)
            if not d:
                return None
            return {
                'protocol': 'trojan',
                'settings': {'servers': [{
                    'address': d['address'],
                    'port': d['port'],
                    'password': d['password'],
                }]},
                'streamSettings': transport_builder.build_xray_settings(d),
            }

        if low.startswith('ss://'):
            d = parser.parse_shadowsocks(uri)
            if not d:
                return None
            return {
                'protocol': 'shadowsocks',
                'settings': {'servers': [{
                    'address': d['address'],
                    'port': d['port'],
                    'method': d['method'],
                    'password': d['password'],
                }]},
            }
    except Exception as e:
        logger.debug(f'parse error for {uri[:60]}: {e}')
    return None


# ---------------------------------------------------------------------------
# Single-proxy test
# ---------------------------------------------------------------------------
def test_proxy(uri: str) -> Tuple[str, str]:
    low = uri.lower()
    for skip in SKIP_PROTOCOLS:
        if low.startswith(skip):
            logger.debug(f'skip unsupported protocol: {uri[:50]}')
            return 'failed', uri

    outbound = build_outbound(uri)
    if outbound is None:
        return 'failed', uri

    port = find_free_port()
    xray_cfg = {
        'log': {'loglevel': 'none'},
        'inbounds': [{'port': port, 'protocol': 'http', 'listen': '127.0.0.1'}],
        'outbounds': [outbound],
    }

    fd, cfg_path = tempfile.mkstemp(suffix='.json', prefix='ut_')
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
            time.sleep(STARTUP_DELAY)
            if proc.poll() is not None:
                return 'failed', uri

            proxies = {
                'http':  f'http://127.0.0.1:{port}',
                'https': f'http://127.0.0.1:{port}',
            }
            resp = requests.head(
                GOOGLE_TARGET,
                proxies=proxies,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                logger.info(f'\u2713 google200  {uri[:70]}')
                return 'google200', uri
            else:
                logger.info(f'\u2713 working({resp.status_code})  {uri[:70]}')
                return 'working', uri

        except requests.exceptions.ProxyError:
            return 'failed', uri
        except requests.exceptions.Timeout:
            return 'failed', uri
        except Exception as e:
            logger.debug(f'request error: {e}')
            return 'failed', uri
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
# Detour helper
# ---------------------------------------------------------------------------
def with_detour(uri: str, tag: str) -> str:
    """Append detour=<tag> to the proxy name (fragment), keeping everything
    as plain decoded text so Hiddify can match the tag by exact string."""
    if '#' in uri:
        base, frag = uri.split('#', 1)
        # Always work with the decoded fragment - never re-encode it.
        frag_decoded = unquote(frag)
        if 'detour=' not in frag_decoded:
            frag_decoded += f'&detour={tag}'
        return base + '#' + frag_decoded
    return uri + '#' + f'detour={tag}'


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def load_lines(path: str) -> list[str]:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return [
                l.strip() for l in fh
                if l.strip() and not l.startswith('//')
            ]
    except FileNotFoundError:
        logger.error(f'Input file not found: {path}')
        return []


def write_plain(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(line + '\n\n')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'configs/proxy_configs.txt'

    lines = load_lines(input_file)
    if not lines:
        logger.error('No proxy lines found. Aborting.')
        sys.exit(0)

    logger.info(f'Testing {len(lines)} proxies with {MAX_WORKERS} workers ...')
    logger.info(f'Google target: {GOOGLE_TARGET}')
    logger.info(f'Landing proxy tag: {LANDING_TAG}')

    google200: list[str] = []
    all_working: list[str] = []
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(test_proxy, uri): uri for uri in lines}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                result, uri = fut.result(timeout=TIMEOUT + 10)
            except Exception as e:
                logger.error(f'Future error: {e}')
                result, uri = 'failed', futures[fut]

            if result == 'google200':
                google200.append(uri)
            elif result == 'working':
                all_working.append(uri)
            else:
                failed += 1

            if done % 25 == 0 or done == len(lines):
                logger.info(
                    f'Progress {done}/{len(lines)} '
                    f'| google200={len(google200)} '
                    f'| working={len(all_working)} '
                    f'| failed={failed}'
                )

    logger.info(
        f'Done. google200={len(google200)}  '
        f'all_working={len(all_working)}  '
        f'failed={failed}'
    )

    # --- write outputs ---
    write_plain('configs/google_200.txt',          google200)
    write_plain('configs/all_working.txt',         all_working)
    write_plain('configs/hiddify_google_200.txt',  google200)
    write_plain('configs/hiddify_all_working.txt', all_working)

    # Detour file: landing proxy first (plain-text fragment), then every
    # all_working proxy with &detour=<landing tag> appended to its name.
    detour_lines = [LANDING_PROXY]
    for uri in all_working:
        if '109.201.152.181:443' in uri:
            continue
        detour_lines.append(with_detour(uri, LANDING_TAG))
    write_plain('configs/hiddify_all_detour.txt', detour_lines)

    logger.info('Output files written:')
    for f in [
        'configs/all_working.txt',
        'configs/google_200.txt',
        'configs/hiddify_all_working.txt',
        'configs/hiddify_google_200.txt',
        'configs/hiddify_all_detour.txt',
    ]:
        logger.info(f'  {f}')


if __name__ == '__main__':
    main()
