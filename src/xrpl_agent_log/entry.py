# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Entry — a single record in a MutualLog.

An Entry is a JSON-serializable, hash-chained record of one interaction
between two agents. It is signed by both parties.

The hash chain works like this:
    entry_hash = SHA-256(canonical_serialize({
        sequence:        <int>,       # monotonic, starts at 1
        parent_hash:     <str|null>,  # previous entry's hash, null for genesis
        agent_a_did:     <str>,
        agent_b_did:     <str>,
        intent:          <str>,       # human-readable description
        on_chain_tx_hash:<str|null>,  # optional XRPL tx anchor
        params:          <dict>,      # structured parameters
        timestamp:       <int>,       # unix seconds
    }))

`canonical_serialize` is a deterministic JSON encoder (sorted keys, no
whitespace) so the same logical entry always hashes to the same value.
This is the property that makes the chain verifiable.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


def canonical_serialize(payload: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, no whitespace, separators explicit."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def compute_entry_hash(
    *,
    sequence: int,
    parent_hash: str | None,
    agent_a_did: str,
    agent_b_did: str,
    intent: str,
    on_chain_tx_hash: str | None,
    params: dict[str, Any],
    timestamp: int,
) -> str:
    """SHA-256 hex digest of the canonical serialization."""
    payload = {
        "sequence": sequence,
        "parent_hash": parent_hash,
        "agent_a_did": agent_a_did,
        "agent_b_did": agent_b_did,
        "intent": intent,
        "on_chain_tx_hash": on_chain_tx_hash,
        "params": params,
        "timestamp": timestamp,
    }
    return hashlib.sha256(canonical_serialize(payload).encode("utf-8")).hexdigest()


@dataclass
class Entry:
    """A single signed record in a MutualLog.

    Constructed via `Log.make_entry()` or `Log.append()` — not directly by callers,
    since constructing an Entry without both signatures breaks the mutual-
    attestation contract.
    """

    sequence: int
    parent_hash: str | None
    agent_a_did: str
    agent_b_did: str
    intent: str
    on_chain_tx_hash: str | None
    params: dict[str, Any]
    timestamp: int
    entry_hash: str
    sig_a: str  # hex-encoded ECDSA signature over entry_hash, by agent_a
    sig_b: str  # hex-encoded ECDSA signature over entry_hash, by agent_b

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def payload_for_signing(self) -> str:
        """The canonical string both parties sign. entry_hash is the digest."""
        return self.entry_hash


def make_entry(
    *,
    sequence: int,
    parent_hash: str | None,
    agent_a_did: str,
    agent_b_did: str,
    intent: str,
    on_chain_tx_hash: str | None,
    params: dict[str, Any] | None = None,
    timestamp: int | None = None,
) -> Entry:
    """Build an Entry with both signatures EMPTY.

    Caller is responsible for populating `sig_a` and `sig_b` via
    `signing.sign_entry()` before committing. Returning an Entry with empty
    signatures is fine — verification will reject it.
    """
    params = params or {}
    timestamp = timestamp if timestamp is not None else int(time.time())
    entry_hash = compute_entry_hash(
        sequence=sequence,
        parent_hash=parent_hash,
        agent_a_did=agent_a_did,
        agent_b_did=agent_b_did,
        intent=intent,
        on_chain_tx_hash=on_chain_tx_hash,
        params=params,
        timestamp=timestamp,
    )
    return Entry(
        sequence=sequence,
        parent_hash=parent_hash,
        agent_a_did=agent_a_did,
        agent_b_did=agent_b_did,
        intent=intent,
        on_chain_tx_hash=on_chain_tx_hash,
        params=params,
        timestamp=timestamp,
        entry_hash=entry_hash,
        sig_a="",
        sig_b="",
    )