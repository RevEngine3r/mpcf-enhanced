"""generate_v2n.py

Reads proxy_configs.txt and writes proxy_configs_v2n.txt as plain text
(one proxy URI per line, blank line as separator) – directly importable
by v2rayNG and NekoBox as a local subscription file.

Usage:
    python src/generate_v2n.py [input.txt] [output.txt]
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_proxy_lines(path: str) -> list[str]:
    """Return non-empty, non-comment proxy lines from *path*."""
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return [
                line.strip()
                for line in fh
                if line.strip() and not line.startswith('//')
            ]
    except FileNotFoundError:
        logger.error(f"Input file not found: {path}")
        return []


def write_plain(path: str, lines: list[str]) -> None:
    """Write proxy lines separated by blank lines (v2rayNG / NekoBox format)."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for line in lines:
            fh.write(line + '\n\n')


def main() -> None:
    input_file  = sys.argv[1] if len(sys.argv) > 1 else 'configs/proxy_configs.txt'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'configs/proxy_configs_v2n.txt'

    lines = load_proxy_lines(input_file)
    if not lines:
        logger.error("No proxy lines found – writing empty file.")
        open(output_file, 'w').close()
        sys.exit(0)

    write_plain(output_file, lines)
    logger.info(f"Wrote {len(lines)} proxies (plain text) → {output_file}")


if __name__ == '__main__':
    main()
