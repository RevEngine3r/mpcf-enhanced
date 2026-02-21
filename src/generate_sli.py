"""generate_sli.py

Produces configs/proxy_configs_sli.txt – a Hiddify subscription file where
every gathered proxy is chained through a fixed landing ("SLI") proxy.

Hiddify supports chain proxies via the `#sni=...` fragment trick or,
more reliably, via the `proxy-chain` URI scheme.  The safest cross-version
approach is to emit pairs of lines that Hiddify reads as a chain:

    <landing_proxy>
    <real_proxy>#_chain_=<landing_tag>

For broader compatibility we use Hiddify's documented approach of prepending
the landing proxy tag to each proxy comment so the client knows to route
through it, OR (more robustly) we output a Hiddify-compatible subscription
body where the landing SS proxy appears first, followed by all other proxies
with `detour=<landing_tag>` embedded as a URI fragment parameter.  Hiddify
parses `detour` (or `chain`) from the fragment when present.

Format emitted per proxy:
    ss://...#<name>&detour=<landing_tag>
    vless://...?...#<name>&detour=<landing_tag>
    vmess://...   (vmess uses a JSON param – we embed `detour` in fragment)

Usage:
    python src/generate_sli.py [input.txt] [output.txt]
"""
import logging
import os
import sys
from urllib.parse import urlparse, parse_qs, urlencode, quote, unquote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed landing proxy
# ---------------------------------------------------------------------------
LANDING_PROXY = (
    'ss://YWVzLTEyOC1jZmI6c2hhZG93c29ja3M=@109.201.152.181:443'
    '#%F0%9F%94%92%20SS-TCP-NA%20%F0%9F%87%B3%F0%9F%87%B1%20NL-109.201.152.181:443'
)
LANDING_TAG = 'SS-TCP-NA-NL'


def load_lines(path: str) -> list[str]:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return [
                l.strip() for l in fh
                if l.strip() and not l.startswith('//')
            ]
    except FileNotFoundError:
        logger.error(f"Input not found: {path}")
        return []


def _set_fragment_detour(uri: str, detour_tag: str) -> str:
    """Append &detour=<tag> to the URI fragment, preserving existing fragment."""
    if '#' in uri:
        base, frag = uri.split('#', 1)
        frag_decoded = unquote(frag)
        # avoid double-appending
        if 'detour=' not in frag_decoded:
            frag_decoded = frag_decoded + f'&detour={detour_tag}'
        return base + '#' + quote(frag_decoded, safe='=&@:-_.!~*()/')
    else:
        return uri + f'#detour={detour_tag}'


def chain_proxy(proxy_uri: str, landing_tag: str) -> str:
    """Return the proxy URI with a detour/chain fragment pointing to landing_tag."""
    lower = proxy_uri.lower()
    # vmess: JSON-based – append detour to fragment
    if lower.startswith('vmess://'):
        return _set_fragment_detour(proxy_uri, landing_tag)
    # URI-based protocols (vless, trojan, ss, hysteria2, …)
    return _set_fragment_detour(proxy_uri, landing_tag)


def main() -> None:
    input_file  = sys.argv[1] if len(sys.argv) > 1 else 'configs/proxy_configs.txt'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'configs/proxy_configs_sli.txt'

    lines = load_lines(input_file)
    if not lines:
        logger.warning("No proxy lines found – writing header-only file.")

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as out:
        # 1. Emit the landing proxy first (un-chained)
        out.write(LANDING_PROXY + '\n\n')

        # 2. Emit every gathered proxy chained through the landing proxy
        chained = 0
        for uri in lines:
            # Skip the landing proxy itself if it somehow appears in the pool
            if '109.201.152.181:443' in uri and 'YWVzLTEyOC1jZmI6c2hhZG93c29ja3M=' in uri:
                continue
            out.write(chain_proxy(uri, LANDING_TAG) + '\n\n')
            chained += 1

    logger.info(
        f"Written {chained} chained proxies + landing proxy → {output_file}"
    )


if __name__ == '__main__':
    main()
