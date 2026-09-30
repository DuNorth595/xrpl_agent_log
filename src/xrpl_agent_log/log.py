# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Log — the public orchestrator for a MutualLog.

A Log is the live, appendable view of a sequence of Entries between two
specific agents. It enforces the mutual-attestation contract: every
appended entry must be signed by both parties before it commits.

Typical usage:

    from xrpl_agent_id.identity import AgentIdentity
    from xrpl_agent_log import Log, SigningPair
    from xrpl_agent_log.storage.sqlite import SQLiteStorage

    alice = AgentIdentity.from_seed("...", network="testnet")
    bob = AgentIdentity.from_seed("...", network="testnet")

    pair = SigningPair.from_identities(alice, bob)
    storage = SQLiteStorage(db_path="alice-bob.db", log_id="alice-bob-v1")
    log = Log(pair=pair, storage=storage)

    entry = log.append(
        intent="alice pays bob 100 XRP for invoice #42",
        on_chain_tx_hash=None,
        params={"amount_xrp": 100},
    )
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from xrpl_agent_log.entry import Entry, make_entry
from xrpl_agent_log.signing import attach_signature, both_signed
from xrpl_agent_log.storage.base import Storage

if TYPE_CHECKING:
    from xrpl_agent_id.identity import AgentIdentity


@dataclass
class SigningPair:
    """The two agents whose signatures are required for every entry."""

    wallet_a: Any  # xrpl-py Wallet
    wallet_b: Any  # xrpl-py Wallet
    did_a: str
    did_b: str
    network: str

    @classmethod
    def from_wallets_with_dids(
        cls,
        wallet_a: Any,
        wallet_b: Any,
        did_a: str,
        did_b: str,
        network: str,
    ) -> "SigningPair":
        return cls(
            wallet_a=wallet_a,
            wallet_b=wallet_b,
            did_a=did_a,
            did_b=did_b,
            network=network,
        )

    @classmethod
    def from_identities(
        cls,
        identity_a: "AgentIdentity",
        identity_b: "AgentIdentity",
    ) -> "SigningPair":
        return cls(
            wallet_a=identity_a.wallet,
            wallet_b=identity_b.wallet,
            did_a=identity_a.did,
            did_b=identity_b.did,
            network=identity_a.network,
        )


class Log:
    """Append-only sequence of mutually-attested Entries between two agents."""

    def __init__(self, pair: SigningPair, storage: Storage) -> None:
        self.pair = pair
        self.storage = storage

    @property
    def agent_a_did(self) -> str:
        return self.pair.did_a

    @property
    def agent_b_did(self) -> str:
        return self.pair.did_b

    def append(
        self,
        *,
        intent: str,
        on_chain_tx_hash: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Entry:
        """Build, sign with both parties, and commit a new Entry.

        Returns the committed Entry. Both SigningPair.wallet_a and
        wallet_b must be available in-process. For cross-process or
        cross-machine signing (where only one party is local), a separate
        `ProposeLog` / `CounterSignLog` API is planned for v0.3.0.
        """
        latest = self.storage.latest()
        next_seq = (latest.sequence + 1) if latest is not None else 1
        parent_hash = latest.entry_hash if latest is not None else None

        entry = make_entry(
            sequence=next_seq,
            parent_hash=parent_hash,
            agent_a_did=self.agent_a_did,
            agent_b_did=self.agent_b_did,
            intent=intent,
            on_chain_tx_hash=on_chain_tx_hash,
            params=params,
        )

        attach_signature(entry, self.pair.wallet_a)
        attach_signature(entry, self.pair.wallet_b)

        if not both_signed(entry):
            raise RuntimeError(
                "Both signatures should be populated after attach_signature; "
                f"got sig_a={bool(entry.sig_a)} sig_b={bool(entry.sig_b)}"
            )

        self.storage.append(entry)
        return entry

    def replay(self) -> "list[Entry]":
        """Return all entries in sequence order. Read-only."""
        return self.storage.all_entries()

    def latest(self) -> "Entry | None":
        return self.storage.latest()

    def count(self) -> int:
        return self.storage.count()