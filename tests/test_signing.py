# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Tests for the SigningPair and per-entry signing helpers."""
from __future__ import annotations

import pytest
from xrpl.wallet import Wallet

from xrpl_agent_log.entry import make_entry
from xrpl_agent_log.signing import (
    attach_signature,
    both_signed,
    sign_entry,
    verify_entry_signature,
)


def _make_unsigned_entry(wallet_a: Wallet, wallet_b: Wallet):
    return make_entry(
        sequence=1,
        parent_hash=None,
        agent_a_did=f"did:xrpl:testnet:{wallet_a.classic_address}",
        agent_b_did=f"did:xrpl:testnet:{wallet_b.classic_address}",
        intent="test",
        on_chain_tx_hash=None,
        params={},
    )


def test_sign_entry_returns_hex_string(alice_wallet, bob_wallet):
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    sig = sign_entry(e, alice_wallet)
    assert isinstance(sig, str)
    assert len(sig) > 0
    # Hex strings are 0-9 a-f; ensure no odd characters.
    int(sig, 16)


def test_attach_signature_fills_correct_slot(alice_wallet, bob_wallet):
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    attach_signature(e, alice_wallet)
    assert e.sig_a != ""
    assert e.sig_b == ""
    attach_signature(e, bob_wallet)
    assert e.sig_b != ""
    assert both_signed(e)


def test_attach_signature_rejects_non_party_wallet(
    alice_wallet, bob_wallet
):
    """A wallet from neither party must raise ValueError on attach."""
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    intruder = Wallet.create()
    with pytest.raises(ValueError, match="does not match either party"):
        attach_signature(e, intruder)


def test_verify_entry_signature_succeeds_with_correct_wallet(
    alice_wallet, bob_wallet
):
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    attach_signature(e, alice_wallet)
    attach_signature(e, bob_wallet)
    assert verify_entry_signature(e, alice_wallet)
    assert verify_entry_signature(e, bob_wallet)


def test_verify_entry_signature_fails_with_non_party_wallet(
    alice_wallet, bob_wallet
):
    """A wallet that wasn't a signer must return False, not raise."""
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    attach_signature(e, alice_wallet)
    attach_signature(e, bob_wallet)
    intruder = Wallet.create()
    assert not verify_entry_signature(e, intruder)


def test_verify_entry_signature_fails_when_sig_missing(
    alice_wallet, bob_wallet
):
    """If one signature is missing, verification of the missing side is False."""
    e = _make_unsigned_entry(alice_wallet, bob_wallet)
    attach_signature(e, alice_wallet)  # only A signed
    assert verify_entry_signature(e, alice_wallet)
    assert not verify_entry_signature(e, bob_wallet)


def test_both_signed_returns_false_for_unsigned():
    e = _make_unsigned_entry(Wallet.create(), Wallet.create())
    assert not both_signed(e)
    assert e.sig_a == ""
    assert e.sig_b == ""


def test_sign_entry_raises_on_empty_hash(alice_wallet, bob_wallet):
    """An Entry without an entry_hash can't be signed."""
    from xrpl_agent_log.entry import Entry

    e = Entry(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={},
        timestamp=1700000000,
        entry_hash="",  # explicitly empty
        sig_a="",
        sig_b="",
    )
    with pytest.raises(ValueError, match="no entry_hash"):
        sign_entry(e, alice_wallet)