# xrpl_agent_log

> **Tamper-evident history log for AI agents on the XRP Ledger.**
> Append-only, hash-chained, mutually-signed, optionally XRPL-anchored.
> Replayable from public data alone.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![xrpl-py 4.5+](https://img.shields.io/badge/xrpl--py-4.5+-black.svg)](https://pypi.org/project/xrpl-py/)
[![SPDX: REUSE](https://img.shields.io/badge/SPDX-REUSE--compliant-brightgreen)](https://reuse.software/)

---

## Cover Page

| **Package:** | `xrpl_agent_log` |
| **Version:** | 0.2.0 (alpha) |
| **Author:** | Justin Douglas |
| **Organization:** | S_DevLabs (Strategic Development Labs) |
| **Contact:** | S_DevLabs@outlook.com |
| **License:** | MIT |
| **Python:** | ≥ 3.9 |
| **Dependencies:** | `xrpl-py` ≥ 4.5.0, `xrpl_agent_id` ≥ 0.4.0 |
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
from xrpl_agent_id import AgentIdentity
from xrpl_agent_log import Log, SigningPair, SQLiteStorage

# Two parties — each loads its own wallet + DID
wallet_a = Wallet.create()  # In production: load from secure storage
wallet_b = Wallet.create()
identity_a = AgentIdentity.from_seed(wallet_a.seed, network="testnet")
identity_b = AgentIdentity.from_seed(wallet_b.seed, network="testnet")

# Create a signing pair (mutual attestation)
sig_pair = SigningPair.from_wallets_with_dids(
    party_a=(wallet_a, identity_a.did),
    party_b=(wallet_b, identity_b.did),
)

# Open the log (append-only SQLite)
storage = SQLiteStorage("agent_history.db", log_id="alice<->bob")
log = Log(storage=storage, signers=sig_pair)

# Append — payload is any JSON-serializable dict
entry = log.append({"action": "transfer", "amount": 100, "currency": "USD"})
print(f"entry {entry.sequence}: {entry.canonical_hash[:16]}...")

# Anchor to XRPL (optional — requires funded wallet)
entry = log.append(
    {"action": "settle", "tx_ref": "ext-12345"},
    anchor_with=wallet_a,  # submits 1-drop Payment with entry hash as memo
)

# Verify (the library, or anyone with the data + pubkeys)
from xrpl_agent_log import verify_chain, verify_signatures, verify_on_chain_anchor
verify_chain(log)                  # → True
verify_signatures(log)             # → True
verify_on_chain_anchor(log, -1)    # → True (verifies last entry's anchor)
```

---

## Highlights

- **Three layers of tamper-evidence** — hash chain, mutual signatures, optional on-chain anchor
- **No infrastructure** — pure Python + SQLite + XRPL JSON-RPC
- **Auditor-friendly** — verify with just public keys + the chain + JSON-RPC
- **Live-tested on XRPL Testnet** — 44/44 tests passing (43 offline + 1 live)
- **Honest about limits** — see [SECURITY.md](SECURITY.md) for known issues
- **SPDX-licensed** — MIT for code, REUSE-compliant metadata

---

## Install

```bash
pip install xrpl_agent_log
```

For development (test + pre-commit):

```bash
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
| [xrpl_agent_log_TEST_REPORT.pdf](xrpl_agent_log_TEST_REPORT.pdf) | 5-page live testnet report |

---

## License

MIT — see [LICENSE](LICENSE).

SPDX-License-Identifier: MIT