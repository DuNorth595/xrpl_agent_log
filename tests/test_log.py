# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Tests for the Log orchestrator and replay."""
from __future__ import annotations

import pytest

from xrpl_agent_log import Log, verify_chain, verify_signatures


def test_log_starts_empty(log):
    assert log.count() == 0
    assert log.latest() is None
    assert log.replay() == []


def test_log_append_returns_signed_entry(log):
    e = log.append(intent="first event", params={"x": 1})
    assert e.sequence == 1
    assert e.parent_hash is None
    assert e.sig_a and e.sig_b  # both signatures populated
    assert e.entry_hash


def test_log_appends_increment_sequence(log):
    e1 = log.append(intent="first")
    e2 = log.append(intent="second")
    e3 = log.append(intent="third")
    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 3


def test_log_chain_links_to_previous(log):
    """Each new entry's parent_hash equals the previous entry's entry_hash."""
    e1 = log.append(intent="first")
    e2 = log.append(intent="second")
    e3 = log.append(intent="third")
    assert e2.parent_hash == e1.entry_hash
    assert e3.parent_hash == e2.entry_hash


def test_log_replay_returns_in_order(log):
    log.append(intent="first")
    log.append(intent="second")
    log.append(intent="third")
    entries = log.replay()
    assert [e.intent for e in entries] == ["first", "second", "third"]


def test_log_verify_chain_passes_for_valid_log(
    log, alice_wallet, bob_wallet
):
    log.append(intent="first")
    log.append(intent="second")
    log.append(intent="third")

    result = verify_chain(log)
    assert result.ok
    assert result.errors == []


def test_log_verify_signatures_passes_for_valid_log(
    log, alice_wallet, bob_wallet
):
    log.append(intent="first")
    log.append(intent="second")

    result = verify_signatures(log, alice_wallet, bob_wallet)
    assert result.ok
    assert result.errors == []


def test_log_verify_signatures_fails_for_wrong_wallet(log):
    from xrpl.wallet import Wallet

    log.append(intent="first")
    intruder_a = Wallet.create()
    intruder_b = Wallet.create()

    result = verify_signatures(log, intruder_a, intruder_b)
    assert not result.ok
    assert any("Sig_a failed" in err for err in result.errors)
    assert any("Sig_b failed" in err for err in result.errors)


def test_log_attach_params_to_entry(log):
    e = log.append(
        intent="alice pays bob",
        on_chain_tx_hash="DEADBEEF" * 8,
        params={"amount_xrp": 100, "memo": "invoice-42"},
    )
    assert e.params == {"amount_xrp": 100, "memo": "invoice-42"}
    assert e.on_chain_tx_hash == "DEADBEEF" * 8


def test_log_agent_a_did_and_b_did_exposed(log, did_alice, did_bob):
    assert log.agent_a_did == did_alice
    assert log.agent_b_did == did_bob


def test_log_append_with_none_params_is_safe(log):
    """Appending with params=None should default to {}."""
    e = log.append(intent="first", params=None)
    assert e.params == {}