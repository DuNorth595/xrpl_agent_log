# xrpl_agent_log

> **Tamper-evident history log for AI agents on the XRP Ledger.**
> Append-only, hash-chained, mutually-signed, optionally XRPL-anchored.
> Replayable from public data alone.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![xrpl-py 4.5+](https://img.shields.io/badge/xrpl--py-4.5+-black.svg)](https://pypi.org/project/xrpl-py/)
[![SPDX: REUSE](https://img.shields.io/badge/SPDX-REUSE--compliant-brightgreen)](https://reuse.software/)
[![CI](https://github.com/DuNorth595/xrpl_agent_log/actions/workflows/ci.yml/badge.svg)](https://github.com/DuNorth595/xrpl_agent_log/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/badge/release-v0.2.0-blue)](https://github.com/DuNorth595/xrpl_agent_log/releases)

---

## Cover Page

| **Package:** | `xrpl_agent_log` |
| **Version:** | 0.2.0 |
| **Author:** | Justin Douglas |
| **Organization:** | S_DevLabs (Strategic Development Labs) |
| **Contact:** | S_DevLabs@outlook.com |
| **License:** | MIT |
| **Python:** | ≥ 3.9 |
| **Dependencies:** | `xrpl-py` ≥ 4.5.0, [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) ≥ 0.4.1 (installed from GitHub — not on PyPI yet) |
| **Optional extras:** | `dev` (pytest + pre-commit) |

**What this is in one sentence:**
A small Python library that gives AI agents a tamper-evident history log —
append-only entries, hash-chained via SHA-256, mutually-signed by both
parties with ECDSA over secp256k1, optionally anchored to the XRP Ledger
via 1-drop Payment transactions for public timestamping.

**What this is NOT:**
A key-management system, a wallet, a privacy layer, or a replacement for
SIEM tools. Logs are public-by-design (anchors are). Bring your own keys.
Use `xrpl-py`'s `Wallet`.

---

## Quick start

```python
from xrpl.wallet import Wallet
from xrpl_agent_log import Log, SigningPair, SQLiteStorage

# Two parties — each loads its own wallet + DID
wallet_a = Wallet.create()   # In production: load from secure storage
wallet_b = Wallet.create()

# A signing pair is the mutual-attestation identity of the two parties
# The DID must end in the matching wallet's classic address — the library
# enforces this on every signature and raises ValueError otherwise.
pair = SigningPair(
    wallet_a=wallet_a,
    wallet_b=wallet_b,
    did_a=f"did:xrpl:testnet:{wallet_a.classic_address}",
    did_b=f"did:xrpl:testnet:{wallet_b.classic_address}",
    network="testnet",
)

# Open the log (append-only SQLite)
storage = SQLiteStorage("agent_history.db", log_id="alice<->bob")
log = Log(pair, storage)

# Append — `intent` is required; `params` is any JSON-serializable dict
entry = log.append(
    intent="transfer",
    params={"amount": 100, "currency": "USD"},
)
print(entry.sequence, entry.entry_hash[:16])

# `params` is the payload; `on_chain_tx_hash` records an anchor you already made.
# See "On-chain anchoring" below — this library does NOT submit transactions.
entry = log.append(
    intent="settle",
    params={"tx_ref": "ext-12345"},
    on_chain_tx_hash="A1B2C3...F9C3",
)

# Read back
print(log.count())               # number of entries
print(log.latest().intent)       # most recent Entry (or None on an empty log)
for e in log.replay():           # walk the chain oldest -> newest
    print(e.sequence, e.intent)

# Verify (returns a VerificationResult, not a bare bool)
from xrpl_agent_log import verify_chain, verify_signatures, verify_on_chain_anchor

result = verify_chain(log)                     # hash chain intact
assert result.ok, result.errors

result = verify_signatures(log, wallet_a, wallet_b)   # both signatures valid
assert result.ok, result.errors

result = verify_on_chain_anchor(log, xrpl_client=None)  # anchor matches an on-chain tx
```

Every verification helper returns a `VerificationResult(ok: bool, errors: list[str])`
so you get the failure reason, not just `False`.

## Highlights

- **Three layers of tamper-evidence** — hash chain, mutual signatures, optional on-chain anchor.
  The library *records* an anchor tx hash you supply and verifies it against the ledger;
  it does **not** submit the anchor transaction itself. See "On-chain anchoring".
- **No infrastructure** — pure Python + SQLite + XRPL JSON-RPC
- **Auditor-friendly** — verify with just public keys + the chain + JSON-RPC
- **Live-testable on XRPL Testnet** — 43 offline tests pass by default; the live testnet
  test is gated behind `RUN_LIVE=1` and self-skips, so a normal run reports
  `43 passed, 1 skipped`
- **Honest about limits** — see [SECURITY.md](SECURITY.md) for known issues
- **SPDX-licensed** — MIT for code, REUSE-compliant metadata

---

## Install

```bash
# Install xrpl_agent_log — pulls xrpl_agent_id from GitHub automatically
# (xrpl_agent_id is not on PyPI yet; see pyproject.toml)
pip install "xrpl_agent_log @ git+https://github.com/DuNorth595/xrpl_agent_log.git@v0.2.1"
```

Or, for the very latest main:

```bash
pip install "xrpl_agent_log[dev] @ git+https://github.com/DuNorth595/xrpl_agent_log.git@v0.2.1"
```

> **Why no `pip install xrpl_agent_log`?** Both `xrpl_agent_log` and
> `xrpl_agent_id` are published via GitHub, not PyPI, in the 0.2.x line.
> Once both reach PyPI, `pip install xrpl_agent_log` will work.
> Until then, install via `git+https://...`.

For development (test + pre-commit):

```bash
git clone https://github.com/DuNorth595/xrpl_agent_log.git
cd xrpl_agent_log
pip install -e ".[dev]"
pre-commit install   # enables the local seed-scanner hook
```

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/00_executive_summary.md](docs/00_executive_summary.md) | One-page pitch |
| [docs/01_usage.md](docs/01_usage.md) | API reference + examples |
| [docs/02_testing_log.md](docs/02_testing_log.md) | Test layout, what each layer proves |
| [docs/03_known_issues.md](docs/03_known_issues.md) | Honest disclosures from live testing |
| [SESSION_2026-09-30.md](SESSION_2026-09-30.md) | Session log — what shipped, when, why |
| [SECURITY.md](SECURITY.md) | Security policy, threat model, seed rules |
| [docs/02_testing_log.md](docs/02_testing_log.md) | Full test log with live testnet run |

---

## License

MIT — see [LICENSE](LICENSE).

SPDX-License-Identifier: MIT