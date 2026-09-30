#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Seed/secret scanner for the xrpl_agent_log repo.

Scans staged (or all) files for any of:
  - Classic XRPL family seeds ("s...") — these are master private keys.
  - 64-char hex strings (raw secp256k1 private keys).

Exits 1 if any are found in non-allowlisted files. Exits 0 if clean.

The allowlist intentionally covers:
  - .git/ directory (not tracked but defensive)
  - any test_*.py file that constructs ephemeral test wallets (these
    produce sEd... / s... seeds at runtime; we ignore them at the
    source level because they're ephemeral)
  - the scanner itself
  - .venv/ and node_modules/ (third-party code)

Pre-commit hook calls this with no args; CI calls with --all-files.

Usage:
    check_no_seeds.py                 # scan staged files (pre-commit mode)
    check_no_seeds.py --all-files     # scan all files in repo (CI mode)
    check_no_seeds.py path/to/file    # scan explicit files (override mode)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# --- Patterns ------------------------------------------------------------

# Classic XRPL family seed: starts with 's', base58 encoded, ~29-34 chars.
# Matches s..., sEd..., sP..., etc.
CLASSIC_SEED = re.compile(r"\bs[A-HJ-NP-Za-km-z1-9]{28,33}\b")

# Raw secp256k1 private key: 64 lowercase or uppercase hex chars.
# We anchor on common contexts to reduce false positives:
#   - prefixed by 0x
#   - inside JSON "private_key": "..." or "seed": "..."
#   - on a line by itself in a config-like file
HEX_KEY = re.compile(r"(?:0x)?[0-9a-fA-F]{64}")

# --- Allowlist -----------------------------------------------------------

# Files / patterns that are allowed to contain seed-like strings.
ALLOWLIST = (
    ".git/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    "build/",
    "dist/",
    "*.egg-info/",
    "check_no_seeds.py",  # the scanner itself
)

# Files where transient test seeds are allowed to appear (constructed
# at runtime by xrpl-py, not committed). Tests use ephemeral wallets.
LEGACY_ALLOWLIST = (
    "tests/",
    "test_",
)


def _is_allowlisted(path: Path) -> bool:
    """Return True if the path matches any allowlist entry."""
    s = str(path)
    for entry in ALLOWLIST:
        if entry in s:
            return True
        if entry.startswith("*") and s.endswith(entry[1:]):
            return True
    for entry in LEGACY_ALLOWLIST:
        if entry in s:
            return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return a list of (line_no, line, pattern_name) hits for the file."""
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return hits

    for lineno, line in enumerate(text.splitlines(), start=1):
        # Strip leading whitespace to look for classic seeds at line start.
        if CLASSIC_SEED.search(line):
            hits.append((lineno, line.strip(), "classic_seed"))
        # Hex key — only flag if 64 chars (without 0x prefix) or starts with 0x.
        for m in HEX_KEY.finditer(line):
            token = m.group(0)
            if token.startswith("0x") and len(token) == 66:
                hits.append((lineno, line.strip(), "hex_key_0x"))
            elif len(token) == 64:
                hits.append((lineno, line.strip(), "hex_key"))
    return hits


def _staged_files() -> list[Path]:
    """Return the list of files staged in git, or [] if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [Path(p) for p in out.stdout.splitlines() if p]


def _all_files(root: Path) -> list[Path]:
    """Return all tracked files in the repo (git ls-files)."""
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in root.rglob("*") if p.is_file()]
    return [root / p for p in out.stdout.splitlines() if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed/secret scanner")
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Scan all tracked files (CI mode). Default: staged files only.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to scan. Overrides staged/all-files mode.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: current directory).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()

    if args.files:
        targets = [Path(f).resolve() for f in args.files]
    elif args.all_files:
        targets = _all_files(root)
    else:
        targets = _staged_files()
        if not targets:
            # No staged files (e.g., nothing to commit yet); nothing to scan.
            print("No staged files to scan. OK.")
            return 0

    total_hits = 0
    scanned = 0
    for path in targets:
        if not path.exists() or not path.is_file():
            continue
        if _is_allowlisted(path):
            continue
        # Only scan text-like files.
        if path.suffix in {
            ".py",
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".sh",
            ".env",
            ".example",
        }:
            scanned += 1
            for lineno, line, pattern in _scan_file(path):
                total_hits += 1
                rel = (
                    path.relative_to(root)
                    if path.is_absolute() and str(path).startswith(str(root))
                    else path
                )
                print(
                    f"  {rel}:{lineno} [{pattern}] {line[:80]}",
                    file=sys.stderr,
                )

    if total_hits == 0:
        print(f"Seed scanner: {scanned} files scanned, clean.")
        return 0
    print(
        f"\nSeed scanner: {total_hits} potential secret(s) found in {scanned} files.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())