# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Tests for the verify module — chain, signatures, and on-chain anchors."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from xrpl.wallet import Wallet

from xrpl_agent_log import (
    Log,
    SigningPair,
    SQLiteStorage,
    verify_chain,
    verify_on_chain_anchor,
    verify_signatures,
)
from xrpl_agent_log.entry import make_entry
from xrpl_agent_log.signing import attach_signature


def _append_tampered_entry(
    storage: SQLiteStorage,
    alice_wallet: Wallet,
    bob_wallet: Wallet,
    *,
    sequence: int,
    parent: str | None,
    intent: str,
) -> None:
    """Append an entry, then directly mutate the SQLite row to corrupt its hash.

    This bypasses normal append() validation to simulate a hostile actor
    with database access."""
    e = make_entry(
        sequence=sequence,
        parent_hash=parent,
        agent_a_did=f"did:xrpl:testnet:{alice_wallet.classic_address}",
        agent_b_did=f"did:xrpl:testnet:{bob_wallet.classic_address}",
        intent=intent,
        on_chain_tx_hash=None,
        params={},
    )
    attach_signature(e, alice_wallet)
    attach_signature(e, bob_wallet)
    storage.append(e)
    # Tamper with intent without re-hashing.
    storage._conn.execute(  # noqa: SLF001 — internal channel used only in tests
        "UPDATE entries SET intent = ? WHERE log_id = ? AND sequence = ?",
        ("tampered", storage.log_id, sequence),
    )
    storage._conn.commit()


def test_verify_chain_detects_hash_tampering(
    tmp_path: Path, alice_wallet: Wallet, bob_wallet: Wallet
):
    """If intent is mutated post-commit, verify_chain must fail."""
    storage = SQLiteStorage(db_path=tmp_path / "tamper.db", log_id="t")
    pair = SigningPair.from_wallets_with_dids(
        alice_wallet,
        bob_wallet,
        f"did:xrpl:testnet:{alice_wallet.classic_address}",
        f"did:xrpl:testnet:{bob_wallet.classic_address}",
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)

    # Append a clean entry first.
    log.append(intent="clean")

    # Append a tampered entry via the back-channel.
    latest = log.latest()
    assert latest is not None
    _append_tampered_entry(
        storage,
        alice_wallet,
        bob_wallet,
        sequence=2,
        parent=latest.entry_hash,
        intent="this will be tampered",
    )

    result = verify_chain(log)
    assert not result.ok
    assert any("hash mismatch" in err for err in result.errors)


def test_verify_chain_detects_sequence_gap(
    tmp_path: Path, alice_wallet: Wallet, bob_wallet: Wallet
):
    """A missing sequence (e.g., a deleted row) must be detected."""
    storage = SQLiteStorage(db_path=tmp_path / "gap.db", log_id="t")
    pair = SigningPair.from_wallets_with_dids(
        alice_wallet,
        bob_wallet,
        f"did:xrpl:testnet:{alice_wallet.classic_address}",
        f"did:xrpl:testnet:{bob_wallet.classic_address}",
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)

    log.append(intent="first")  # seq=1
    log.append(intent="third")  # seq=2 (intent suggests third; pretend it's a gap)

    # Mutate sequence 2 → 3 to simulate a deleted row in between.
    storage._conn.execute(  # noqa: SLF001
        "UPDATE entries SET sequence = 3 WHERE log_id = ? AND sequence = 2",
        (storage.log_id,),
    )
    storage._conn.commit()

    result = verify_chain(log)
    assert not result.ok
    assert any("Sequence gap" in err for err in result.errors)


def test_verify_signatures_passes_for_clean_log(log, alice_wallet, bob_wallet):
    log.append(intent="first")
    log.append(intent="second")
    result = verify_signatures(log, alice_wallet, bob_wallet)
    assert result.ok


def test_verify_signatures_fails_when_sig_removed(
    tmp_path: Path, alice_wallet: Wallet, bob_wallet: Wallet
):
    """Removing sig_a post-commit must fail verification."""
    storage = SQLiteStorage(db_path=tmp_path / "sig.db", log_id="t")
    pair = SigningPair.from_wallets_with_dids(
        alice_wallet,
        bob_wallet,
        f"did:xrpl:testnet:{alice_wallet.classic_address}",
        f"did:xrpl:testnet:{bob_wallet.classic_address}",
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)
    log.append(intent="only entry")

    # Wipe sig_a directly.
    storage._conn.execute(  # noqa: SLF001
        "UPDATE entries SET sig_a = '' WHERE log_id = ? AND sequence = 1",
        (storage.log_id,),
    )
    storage._conn.commit()

    result = verify_signatures(log, alice_wallet, bob_wallet)
    assert not result.ok
    assert any("Sig_a failed" in err for err in result.errors)


def test_verify_on_chain_anchor_skipped_without_client(log):
    """When xrpl_client is None, the on-chain check is a no-op pass."""
    log.append(intent="first", on_chain_tx_hash=None)
    log.append(intent="second", on_chain_tx_hash="DEADBEEF" * 8)
    result = verify_on_chain_anchor(log, xrpl_client=None)
    assert result.ok


def test_verify_on_chain_anchor_detects_missing_tx(log):
    """A tx hash that doesn't resolve on the network must fail verification."""
    from xrpl.clients import JsonRpcClient

    client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")
    log.append(intent="first", on_chain_tx_hash="00" * 32)
    result = verify_on_chain_anchor(log, xrpl_client=client)
    assert not result.ok
    assert any("On-chain lookup failed" in err for err in result.errors)