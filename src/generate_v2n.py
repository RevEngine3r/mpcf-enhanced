"""generate_v2n.py

Reads proxy_configs.txt and writes proxy_configs_v2n.txt.
The output is a single Base64-encoded string (no newlines inside),
readable as a subscription link by NekoBox / v2rayNG.

Usage:
    python src/generate_v2n.py [input.txt] [output.txt]
"""
import base64
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


def encode_to_v2n(lines: list[str]) -> str:
    """Join proxy lines with newlines then Base64-encode the result."""
    joined = '\n'.join(lines)
    return base64.b64encode(joined.encode('utf-8')).decode('ascii')


def write_output(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content + '\n')


def main() -> None:
    input_file  = sys.argv[1] if len(sys.argv) > 1 else 'configs/proxy_configs.txt'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'configs/proxy_configs_v2n.txt'

    lines = load_proxy_lines(input_file)
    if not lines:
        logger.error("No proxy lines found – writing empty file.")
        write_output(output_file, '')
        sys.exit(0)

    encoded = encode_to_v2n(lines)
    write_output(output_file, encoded)
    logger.info(f"Wrote v2n subscription ({len(lines)} proxies) → {output_file}")


if __name__ == '__main__':
    main()
