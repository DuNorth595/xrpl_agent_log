# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""xrpl_agent_log.__main__ — entry point for `python -m xrpl_agent_log`.

Modes (mirroring xrpl_agent_id's CLI):

* `python -m xrpl_agent_log --version`
    Print version + public API surface and exit.
* `python -m xrpl_agent_log --demo`
    Build two ephemeral wallets, sign and append three entries to an
    in-memory SQLite log, then verify chain + signatures. Pure offline
    smoke test; no XRPL network calls.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from xrpl.wallet import Wallet

from xrpl_agent_log import (
    Log,
    SigningPair,
    SQLiteStorage,
    __version__,
    verify_chain,
    verify_signatures,
)


def _print_version_and_api() -> None:
    print(f"xrpl_agent_log v{__version__}")
    print()
    print("Public API:")
    print("  - Log                  (the appendable sequence)")
    print("  - Entry                (a single signed record)")
    print("  - SigningPair          (two-party mutual attestation)")
    print("  - Storage (ABC)        (pluggable persistence)")
    print("  - SQLiteStorage        (append-only SQLite backend)")
    print("  - VerificationResult   (verification outcome)")
    print("  - verify_chain(log)        — hash chain integrity")
    print("  - verify_signatures(log, a, b)  — signature integrity")
    print("  - verify_on_chain_anchor(log, client=None)")
    print()
    print("What it is NOT: a compliance product, a legal-record system,")
    print("or a regulated-environment audit trail. A log is a log.")


def _run_demo() -> int:
    """Offline end-to-end smoke test. Returns 0 on success, 1 on failure."""
    print(f"xrpl_agent_log v{__version__} — offline demo")
    print()

    # Two ephemeral test wallets — NEVER persist these.
    a = Wallet.create()
    b = Wallet.create()

    print(f"Agent A address: {a.classic_address}")
    print(f"Agent B address: {b.classic_address}")
    print()

    did_a = f"did:xrpl:testnet:{a.classic_address}"
    did_b = f"did:xrpl:testnet:{b.classic_address}"

    pair = SigningPair.from_wallets_with_dids(
        a, b, did_a, did_b, network="testnet"
    )

    # Use a temp file so the demo leaves no trace.
    tmp = Path(tempfile.mkstemp(suffix=".db")[1])
    storage = SQLiteStorage(db_path=tmp, log_id="demo-log-v1")
    log = Log(pair=pair, storage=storage)

    print("Appending 3 entries...")
    log.append(
        intent="alice pays bob 100 XRP for invoice #42",
        params={"amount_xrp": 100, "memo": "invoice-42"},
    )
    log.append(
        intent="bob confirms receipt of 100 XRP from alice",
        params={"amount_xrp": 100, "confirms_invoice": "invoice-42"},
    )
    log.append(
        intent="alice and bob close out invoice #42",
        params={"invoice": "invoice-42", "status": "closed"},
    )

    latest = log.latest()
    assert latest is not None, "Expected at least one entry after appends"
    print(f"  log count: {log.count()}")
    print(f"  latest sequence: {latest.sequence}")
    print(f"  latest entry_hash: {latest.entry_hash[:16]}...")
    print()

    print("Verifying chain...")
    chain_result = verify_chain(log)
    print(f"  chain ok: {chain_result.ok}")
    if not chain_result.ok:
        for err in chain_result.errors:
            print(f"  - {err}")
        return 1

    print("Verifying signatures...")
    sig_result = verify_signatures(log, a, b)
    print(f"  signatures ok: {sig_result.ok}")
    if not sig_result.ok:
        for err in sig_result.errors:
            print(f"  - {err}")
        return 1

    print()
    print("Demo PASSED. All entries hash-chained, all signatures valid.")
    storage.close()
    tmp.unlink(missing_ok=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xrpl_agent_log",
        description="Tamper-evident history log for XRPL agents",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and public API surface",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run an offline end-to-end smoke test",
    )
    args = parser.parse_args(argv)

    if args.version:
        _print_version_and_api()
        return 0

    if args.demo:
        return _run_demo()

    # Default: same as --version (backward-compat with xrpl_agent_id pattern)
    _print_version_and_api()
    return 0


if __name__ == "__main__":
    sys.exit(main())