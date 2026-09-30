# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Tests for the Entry dataclass and hash-chain primitives."""
from __future__ import annotations

import pytest

from xrpl_agent_log.entry import (
    Entry,
    canonical_serialize,
    compute_entry_hash,
    make_entry,
)


def test_canonical_serialize_sorts_keys():
    """Order of keys in input dicts must not affect the canonical output."""
    a = canonical_serialize({"b": 2, "a": 1})
    b = canonical_serialize({"a": 1, "b": 2})
    assert a == b == '{"a":1,"b":2}'


def test_canonical_serialize_handles_unicode():
    """Non-ASCII content round-trips correctly without escaping."""
    out = canonical_serialize({"name": "Über"})
    assert "Über" in out  # ensure_ascii=False keeps unicode literals


def test_compute_entry_hash_is_deterministic():
    """Same logical entry → same hash."""
    h1 = compute_entry_hash(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={"x": 1},
        timestamp=1700000000,
    )
    h2 = compute_entry_hash(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={"x": 1},
        timestamp=1700000000,
    )
    assert h1 == h2


def test_compute_entry_hash_changes_on_any_field_change():
    """Any field change produces a different hash."""
    base_kwargs: dict = dict(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={"x": 1},
        timestamp=1700000000,
    )
    base_hash = compute_entry_hash(**base_kwargs)

    # Sequence change
    h = compute_entry_hash(**{**base_kwargs, "sequence": 2})
    assert h != base_hash

    # Intent change
    h = compute_entry_hash(**{**base_kwargs, "intent": "different"})
    assert h != base_hash

    # Params change
    h = compute_entry_hash(**{**base_kwargs, "params": {"x": 2}})
    assert h != base_hash

    # Timestamp change
    h = compute_entry_hash(**{**base_kwargs, "timestamp": 1700000001})
    assert h != base_hash


def test_make_entry_returns_unsigned_entry():
    """make_entry produces an Entry with sig_a and sig_b empty."""
    e = make_entry(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={},
    )
    assert isinstance(e, Entry)
    assert e.sig_a == ""
    assert e.sig_b == ""
    assert e.entry_hash  # populated


def test_make_entry_uses_current_time_when_timestamp_omitted():
    """If timestamp is None, make_entry should populate it with a recent time."""
    import time

    before = int(time.time())
    e = make_entry(
        sequence=1,
        parent_hash=None,
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash=None,
        params={},
    )
    after = int(time.time())
    assert before <= e.timestamp <= after + 1


def test_entry_to_dict_round_trip():
    """to_dict() should produce a JSON-serializable dict."""
    import json

    e = make_entry(
        sequence=7,
        parent_hash="abc123",
        agent_a_did="did:xrpl:testnet:rA",
        agent_b_did="did:xrpl:testnet:rB",
        intent="test",
        on_chain_tx_hash="DEADBEEF" * 8,
        params={"amount": 100, "memo": "hi"},
    )
    d = e.to_dict()
    # Should round-trip cleanly through JSON.
    json.dumps(d)
    assert d["sequence"] == 7
    assert d["parent_hash"] == "abc123"
    assert d["params"] == {"amount": 100, "memo": "hi"}