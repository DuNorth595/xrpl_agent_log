# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""xrpl_agent_log — Tamper-evident history log for AI agents on the XRP Ledger.

Public surface:

    Log           — the appendable sequence (requires both signatures per entry)
    Entry         — a single signed record in a Log
    SigningPair   — the two agents whose signatures are required per entry
    verify_chain, verify_signatures, verify_on_chain_anchor
                   — pure-function integrity checks
    Storage (ABC), SQLiteStorage
                   — pluggable persistence; SQLite is the default backend

Quickstart:

    from xrpl_agent_id.identity import AgentIdentity
    from xrpl_agent_log import Log, SigningPair
    from xrpl_agent_log.storage.sqlite import SQLiteStorage

    alice = AgentIdentity.from_seed("...", network="testnet")
    bob = AgentIdentity.from_seed("...", network="testnet")
    pair = SigningPair.from_identities(alice, bob)
    storage = SQLiteStorage("alice-bob.db", log_id="alice-bob-v1")
    log = Log(pair=pair, storage=storage)
    log.append(intent="alice pays bob 100 XRP for invoice #42",
               params={"amount_xrp": 100})

What this is NOT:
    A compliance product. A legal-record system. An audit-trail replacement
    for regulated environments. A log is a log. It's evidence — not a court
    filing. Don't promise users more than it delivers.
"""

from xrpl_agent_log.entry import Entry, compute_entry_hash, make_entry
from xrpl_agent_log.log import Log, SigningPair
from xrpl_agent_log.storage.base import Storage
from xrpl_agent_log.storage.sqlite import SQLiteStorage
from xrpl_agent_log.verify import (
    VerificationResult,
    verify_chain,
    verify_on_chain_anchor,
    verify_signatures,
)

__version__ = "0.2.0a1"
XRPL_AGENT_LOG_VERSION = __version__  # canonical alias

try:
    from importlib.metadata import version as _pkg_version

    _installed_version = _pkg_version("xrpl_agent_log")
    if _installed_version and _installed_version != __version__:
        __version__ = _installed_version
        XRPL_AGENT_LOG_VERSION = _installed_version
except Exception:
    pass


__all__ = [
    "Entry",
    "Log",
    "SigningPair",
    "Storage",
    "SQLiteStorage",
    "VerificationResult",
    "compute_entry_hash",
    "make_entry",
    "verify_chain",
    "verify_on_chain_anchor",
    "verify_signatures",
    "__version__",
]