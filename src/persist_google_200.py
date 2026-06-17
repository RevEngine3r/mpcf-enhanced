#!/usr/bin/env python3
"""
persist_google_200.py
~~~~~~~~~~~~~~~~~~~~~
Maintains a permanent history of every proxy that has ever passed the
google-200 test, so good proxies are never lost just because they didn't
appear in the latest fetch cycle.

What it does
------------
1. Load  configs/google_200_history.txt  (the ever-growing archive).
2. Load  configs/google_200.txt          (freshly written by unified_tester).
3. Merge: union of both sets, deduplicated by URI key (part before #comment).
4. Write the merged set back to  configs/google_200_history.txt.
5. Overwrite  configs/google_200.txt  with the merged set so that
   split_by_protocol.py always works on the full historical pool.

Deduplication key
-----------------
  line.split('#', 1)[0].strip()

This means two lines that differ only in their #comment suffix are treated as
the same proxy. The version from the *current* run takes priority (its line
replaces any older copy in the history) so that flag/country renames are
always reflected in the output.

File format
-----------
Plain text, one proxy URI per line (plus optional #comment), no blank lines
between entries in the history file.  The google_200.txt produced by
unified_tester uses double-newline separators; this script normalises that
before writing.
"""

from __future__ import annotations

import os
from typing import Iterator

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.dirname(SCRIPT_DIR)
CONFIGS_DIR  = os.path.join(REPO_ROOT, "configs")

CURRENT_FILE = os.path.join(CONFIGS_DIR, "google_200.txt")
HISTORY_FILE = os.path.join(CONFIGS_DIR, "google_200_history.txt")


# ── helpers ───────────────────────────────────────────────────────────────────

def _uri_key(line: str) -> str:
    """Dedup key: URI part before any trailing #comment, stripped."""
    return line.split("#", 1)[0].strip()


def _read_proxies(path: str) -> list[str]:
    """Read a proxy file; skip blank lines and full-line comments."""
    if not os.path.isfile(path):
        return []
    lines: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def _write_proxies(path: str, lines: list[str]) -> None:
    """Write proxy lines, one per line, no extra blank lines."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")


def merge(history: list[str], current: list[str]) -> list[str]:
    """
    Merge history + current into a single deduplicated list.

    Priority: current run entries overwrite older history entries for the
    same URI key (so renamed #comments are always up-to-date).
    Order: history-order for existing entries, current-order appended for new.
    """
    # Build an ordered dict: key -> line, seeded from history
    merged: dict[str, str] = {}
    for line in history:
        key = _uri_key(line)
        if key:
            merged[key] = line

    # Current run: overwrite existing keys (update comment/name) or append new
    for line in current:
        key = _uri_key(line)
        if key:
            merged[key] = line

    return list(merged.values())


# ── main ──────────────────────────────────────────────────────────────────────

def persist() -> None:
    history  = _read_proxies(HISTORY_FILE)
    current  = _read_proxies(CURRENT_FILE)

    if not current:
        print("[persist_google_200] ⚠  google_200.txt is empty — nothing to merge.")
        # Still write history back unchanged so the file is always present
        if history:
            _write_proxies(CURRENT_FILE, history)
            print(f"[persist_google_200] ✓  Restored {len(history)} historic proxies into google_200.txt")
        return

    print(f"[persist_google_200] History: {len(history)} | Current run: {len(current)}")

    merged = merge(history, current)
    new_entries = len(merged) - len(history)

    _write_proxies(HISTORY_FILE, merged)
    _write_proxies(CURRENT_FILE, merged)

    print(
        f"[persist_google_200] ✓  Merged total: {len(merged)} proxies "
        f"(+{new_entries} new this run)"
    )
    print(f"[persist_google_200] ✓  Written → {HISTORY_FILE}")
    print(f"[persist_google_200] ✓  Written → {CURRENT_FILE}")


if __name__ == "__main__":
    persist()
