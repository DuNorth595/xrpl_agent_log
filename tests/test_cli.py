# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Smoke tests for the CLI: --version and --demo."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run `python -m xrpl_agent_log <args>` with PYTHONPATH=src.

    Returns a CompletedProcess with stdout/stderr captured."""
    return subprocess.run(
        [sys.executable, "-m", "xrpl_agent_log", *args],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_version_exits_zero():
    proc = _run_cli("--version")
    assert proc.returncode == 0
    assert "xrpl_agent_log v" in proc.stdout


def test_cli_version_lists_public_api():
    proc = _run_cli("--version")
    assert "Log" in proc.stdout
    assert "SigningPair" in proc.stdout
    assert "verify_chain" in proc.stdout


def test_cli_no_args_prints_version_and_api():
    """No-args invocation should match --version (mirrors xrpl_agent_id)."""
    proc = _run_cli()
    assert proc.returncode == 0
    assert "xrpl_agent_log v" in proc.stdout


def test_cli_demo_exits_zero():
    """The offline smoke test must succeed end-to-end."""
    proc = _run_cli("--demo")
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Demo PASSED" in proc.stdout