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

__version__ = "0.3.1"
XRPL_AGENT_LOG_VERSION = __version__  # canonical alias

# The source literal above is authoritative. It is the version of the code
# that is actually executing.
#
# This used to prefer importlib.metadata and overwrite __version__ with it.
# That inverts the truth: with an editable install, the installed metadata is
# stale the moment you bump the source and before you reinstall, so
# __version__ silently reported the OLD version for the NEW code — a drift
# report that looks self-consistent, which is the worst direction for it to be
# wrong in. `xrpl_agent_id` had this same bug; both now report the source and
# make drift LOUD instead of silent.
try:
    from importlib.metadata import version as _pkg_version

    _installed_version = _pkg_version("xrpl_agent_log")
    if _installed_version and _installed_version != __version__:
        import warnings as _warnings

        _warnings.warn(
            f"xrpl_agent_log source version is '{__version__}' but installed package "
            f"metadata says '{_installed_version}'. Reporting '{__version__}' because "
            f"that is the code actually running. Reinstall to sync "
            f"(pip install -e .).",
            RuntimeWarning,
            stacklevel=2,
        )
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