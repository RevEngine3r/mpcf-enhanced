#!/usr/bin/env python3
"""
persist_google_200.py
~~~~~~~~~~~~~~~~~~~~~
Two-phase history manager for google_200 proxies.

Phase A  (pre-test)  --  called BEFORE unified_tester.py
---------------------------------------------------------
  1. Read  configs/proxy_configs.txt        (freshly fetched + renamed)
  2. Read  configs/google_200_history.txt   (ever-growing archive of past winners)
  3. Merge both lists, deduplicate by URI key (part before #comment).
     Priority: proxy_configs wins over history so fresh renames are kept.
  4. Write the deduped union to  configs/proxy_configs_merged.txt
     → unified_tester.py is run on THIS file instead of proxy_configs.txt.

Phase B  (post-test) --  called AFTER unified_tester.py
--------------------------------------------------------
  5. Read  configs/google_200.txt           (freshly written by unified_tester)
  6. Merge into  configs/google_200_history.txt.
     Priority: current run wins (updates flag/country renames).
  7. Overwrite  configs/google_200.txt  with the full merged pool so
     split_by_protocol.py always works on the complete historical set.

Edge-case: if unified_tester produced an empty google_200.txt (e.g. network
failure), Phase B restores the full history into google_200.txt so downstream
files are never empty.

CLI
---
  python src/persist_google_200.py pre    # Phase A
  python src/persist_google_200.py post   # Phase B

Deduplication key
-----------------
  line.split('#', 1)[0].strip()

Two lines differing only in their #comment are the same proxy.
"""

from __future__ import annotations

import os
import sys

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.dirname(SCRIPT_DIR)
CONFIGS_DIR  = os.path.join(REPO_ROOT, "configs")

PROXY_FILE   = os.path.join(CONFIGS_DIR, "proxy_configs.txt")
MERGED_FILE  = os.path.join(CONFIGS_DIR, "proxy_configs_merged.txt")
HISTORY_FILE = os.path.join(CONFIGS_DIR, "google_200_history.txt")
CURRENT_FILE = os.path.join(CONFIGS_DIR, "google_200.txt")


# ── helpers ───────────────────────────────────────────────────────────────────

def _uri_key(line: str) -> str:
    """Dedup key: bare URI before any trailing #comment."""
    return line.split("#", 1)[0].strip()


def _read_proxies(path: str) -> list[str]:
    """Read proxy file; skip blank lines and full-line # comments."""
    if not os.path.isfile(path):
        return []
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def _write_proxies(path: str, lines: list[str]) -> None:
    """Write proxy lines one per line, no blank separators."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")


def _merge(base: list[str], override: list[str]) -> list[str]:
    """
    Union of base + override, deduplicated by URI key.
    override entries take priority (rename/comment updates).
    Order: base order preserved for existing keys; new keys appended.
    """
    merged: dict[str, str] = {}
    for line in base:
        key = _uri_key(line)
        if key:
            merged[key] = line
    for line in override:
        key = _uri_key(line)
        if key:
            merged[key] = line
    return list(merged.values())


# ── Phase A: pre-test ─────────────────────────────────────────────────────────

def build_merged_input() -> None:
    """
    Merge proxy_configs.txt + google_200_history.txt → proxy_configs_merged.txt
    (deduplicated). This is the file unified_tester.py should be run on.
    """
    proxy   = _read_proxies(PROXY_FILE)
    history = _read_proxies(HISTORY_FILE)

    if not proxy and not history:
        print("[persist:pre] ⚠  Both proxy_configs.txt and history are empty. Aborting.")
        sys.exit(1)

    before = len(proxy)
    # proxy_configs wins over history so fresh renames are preserved
    merged = _merge(history, proxy)   # base=history, override=proxy
    dupes  = (before + len(history)) - len(merged)

    _write_proxies(MERGED_FILE, merged)

    print(
        f"[persist:pre] proxy_configs={before} | history={len(history)} | "
        f"merged={len(merged)} | dupes_removed={dupes}"
    )
    print(f"[persist:pre] ✓  Written → {MERGED_FILE}")


# ── Phase B: post-test ────────────────────────────────────────────────────────

def save_history() -> None:
    """
    Merge freshly-tested google_200.txt into google_200_history.txt,
    then overwrite google_200.txt with the full merged pool.
    """
    history = _read_proxies(HISTORY_FILE)
    current = _read_proxies(CURRENT_FILE)

    if not current:
        print("[persist:post] ⚠  google_200.txt is empty (tester produced no results).")
        if history:
            _write_proxies(CURRENT_FILE, history)
            print(f"[persist:post] ✓  Restored {len(history)} historic proxies → google_200.txt")
        return

    print(f"[persist:post] history={len(history)} | current_run={len(current)}")

    # current run wins (update flag/country renames)
    merged      = _merge(history, current)
    new_entries = len(merged) - len(history)

    _write_proxies(HISTORY_FILE, merged)
    _write_proxies(CURRENT_FILE, merged)

    print(
        f"[persist:post] ✓  Merged total: {len(merged)} proxies (+{new_entries} new this run)"
    )
    print(f"[persist:post] ✓  Written → {HISTORY_FILE}")
    print(f"[persist:post] ✓  Written → {CURRENT_FILE}")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    phase = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if phase == "pre":
        build_merged_input()
    elif phase == "post":
        save_history()
    else:
        print("Usage: persist_google_200.py <pre|post>")
        sys.exit(1)
