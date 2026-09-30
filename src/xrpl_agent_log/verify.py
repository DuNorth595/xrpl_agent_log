# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Verify — chain + signature integrity for a committed log.

Three checks:
1. `verify_chain(log)` — every entry's entry_hash matches its computed hash,
   and every entry's parent_hash equals the previous entry's entry_hash.
2. `verify_signatures(log, wallet_a, wallet_b)` — both signatures valid
   against each entry's entry_hash.
3. `verify_on_chain_anchor(log, entry, client)` — the on_chain_tx_hash
   (if present) corresponds to a transaction on the XRPL network.

All checks are pure functions over the log's entries — they don't mutate
state. They're suitable for use in CLI smoke tests, CI, and audit scripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xrpl.wallet import Wallet

from xrpl_agent_log.entry import compute_entry_hash
from xrpl_agent_log.signing import verify_entry_signature

if TYPE_CHECKING:
    from xrpl_agent_log.log import Log


@dataclass
class VerificationResult:
    """Result of a verification pass over a log or single entry."""

    ok: bool
    errors: list[str]

    def __bool__(self) -> bool:
        return self.ok


def verify_chain(log: "Log") -> VerificationResult:
    """Walk the log in sequence order; check each entry's hash and parent link."""
    errors: list[str] = []
    entries = log.storage.all_entries()

    expected_seq = 1
    expected_parent: str | None = None

    for e in entries:
        if e.sequence != expected_seq:
            errors.append(
                f"Sequence gap: expected {expected_seq}, found {e.sequence}"
            )
        if e.parent_hash != expected_parent:
            errors.append(
                f"Parent link broken at sequence {e.sequence}: "
                f"expected {expected_parent!r}, got {e.parent_hash!r}"
            )

        recomputed = compute_entry_hash(
            sequence=e.sequence,
            parent_hash=e.parent_hash,
            agent_a_did=e.agent_a_did,
            agent_b_did=e.agent_b_did,
            intent=e.intent,
            on_chain_tx_hash=e.on_chain_tx_hash,
            params=e.params,
            timestamp=e.timestamp,
        )
        if recomputed != e.entry_hash:
            errors.append(
                f"Entry hash mismatch at sequence {e.sequence}: "
                f"stored {e.entry_hash[:16]}..., "
                f"recomputed {recomputed[:16]}..."
            )

        if not e.sig_a:
            errors.append(f"Missing sig_a at sequence {e.sequence}")
        if not e.sig_b:
            errors.append(f"Missing sig_b at sequence {e.sequence}")

        expected_parent = e.entry_hash
        expected_seq += 1

    return VerificationResult(ok=len(errors) == 0, errors=errors)


def verify_signatures(
    log: "Log",
    wallet_a: Wallet,
    wallet_b: Wallet,
) -> VerificationResult:
    """Verify both signatures on every committed entry."""
    errors: list[str] = []
    for e in log.storage.all_entries():
        if not verify_entry_signature(e, wallet_a):
            errors.append(
                f"Sig_a failed at sequence {e.sequence} "
                f"(wallet_a address={wallet_a.classic_address})"
            )
        if not verify_entry_signature(e, wallet_b):
            errors.append(
                f"Sig_b failed at sequence {e.sequence} "
                f"(wallet_b address={wallet_b.classic_address})"
            )
    return VerificationResult(ok=len(errors) == 0, errors=errors)


def verify_on_chain_anchor(
    log: "Log",
    xrpl_client=None,
) -> VerificationResult:
    """Optional check: every entry's on_chain_tx_hash, if present, corresponds
    to a real transaction on the XRPL network.

    If `xrpl_client` is None, this check is skipped (returns ok=True).
    Otherwise, uses `xrpl_client.request(Tx, {...})` to look up each tx.
    """
    errors: list[str] = []
    if xrpl_client is None:
        return VerificationResult(ok=True, errors=[])

    for e in log.storage.all_entries():
        if e.on_chain_tx_hash is None:
            continue
        try:
            response = xrpl_client.request({
                "command": "tx",
                "transaction": e.on_chain_tx_hash,
            })
            if response.result.get("hash") != e.on_chain_tx_hash:
                errors.append(
                    f"On-chain anchor mismatch at sequence {e.sequence}: "
                    f"looked up {e.on_chain_tx_hash[:16]}... "
                    "but XRPL returned a different hash"
                )
        except Exception as exc:  # noqa: BLE001 — verifier must not raise
            errors.append(
                f"On-chain lookup failed at sequence {e.sequence} "
                f"(tx_hash={e.on_chain_tx_hash[:16]}...): {exc}"
            )
    return VerificationResult(ok=len(errors) == 0, errors=errors)