# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Signing — mutual attestation helpers.

Each `Entry` requires two signatures: one from each participating agent.
Signatures are ECDSA over the entry hash, using the same secp-256k1 keys
the agent uses for XRPL transactions (via `xrpl-py`'s `Wallet`).

We use `xrpl.core.keypairs.sign` and `is_valid_message` directly rather
than `Wallet.sign` (which doesn't exist in xrpl-py 4.x) — same keys, same
curve, same signatures as XRPL transactions use.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from xrpl.core.keypairs import is_valid_message, sign as kp_sign
from xrpl.wallet import Wallet

if TYPE_CHECKING:
    from xrpl_agent_log.entry import Entry


def _wallet_private_key_hex(wallet: Wallet) -> str:
    """Return the wallet's private key as a hex string.

    xrpl-py's Wallet exposes `private_key` directly as a hex string in
    4.x; the underlying seed is decoded to a private key on demand.
    """
    return wallet.private_key


def sign_entry(entry: Entry, wallet: Wallet) -> str:
    """Sign an Entry's hash with the given wallet. Returns hex signature.

    The signature is over the entry_hash bytes (UTF-8 encoded hex string).
    """
    if not entry.entry_hash:
        raise ValueError("Entry has no entry_hash — cannot sign")
    message = entry.entry_hash.encode("utf-8")
    private_key = _wallet_private_key_hex(wallet)
    return kp_sign(message, private_key)


def _which_slot(entry: Entry, wallet: Wallet) -> str | None:
    """Return 'a', 'b', or None depending on which DID matches wallet address."""
    addr = wallet.classic_address
    if entry.agent_a_did.endswith(addr):
        return "a"
    if entry.agent_b_did.endswith(addr):
        return "b"
    return None


def attach_signature(entry: Entry, wallet: Wallet) -> None:
    """Attach the wallet's signature to the appropriate sig slot on the Entry.

    Mutates `entry` in place. Raises ValueError if the wallet doesn't match
    either party.
    """
    slot = _which_slot(entry, wallet)
    if slot is None:
        addr = wallet.classic_address
        raise ValueError(
            f"Wallet address {addr} does not match either party "
            f"({entry.agent_a_did}, {entry.agent_b_did})"
        )
    sig = sign_entry(entry, wallet)
    if slot == "a":
        entry.sig_a = sig
    else:
        entry.sig_b = sig


def both_signed(entry: Entry) -> bool:
    """True iff both sig slots are populated and entry_hash is set."""
    return bool(entry.sig_a) and bool(entry.sig_b) and bool(entry.entry_hash)


def verify_entry_signature(
    entry: Entry,
    wallet: Wallet,
) -> bool:
    """Verify that the wallet's signature on this entry is valid.

    Looks up the wallet's slot (sig_a or sig_b) by address match and verifies
    the signature against the entry_hash using xrpl-py's `is_valid_message`.
    """
    slot = _which_slot(entry, wallet)
    if slot is None:
        return False
    sig = entry.sig_a if slot == "a" else entry.sig_b
    if not sig:
        return False
    try:
        return is_valid_message(
            entry.entry_hash.encode("utf-8"),
            bytes.fromhex(sig),
            wallet.public_key,
        )
    except Exception:
        return False