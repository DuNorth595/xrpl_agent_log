# xrpl_agent_log

> **Tamper-evident history log for AI agents on the XRP Ledger.**
> Append-only, hash-chained, mutually-signed, replayable from public data alone.
> Anchor references are yours to make; verification is ours.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![xrpl-py 4.5+](https://img.shields.io/badge/xrpl--py-4.5+-black.svg)](https://pypi.org/project/xrpl-py/)
[![SPDX: REUSE](https://img.shields.io/badge/SPDX-REUSE--compliant-brightgreen)](https://reuse.software/)
[![CI](https://github.com/DuNorth595/xrpl_agent_log/actions/workflows/ci.yml/badge.svg)](https://github.com/DuNorth595/xrpl_agent_log/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/badge/release-v0.3.0-blue)](https://github.com/DuNorth595/xrpl_agent_log/releases)

---

## Cover Page

| **Package:** | `xrpl_agent_log` |
| **Version:** | 0.3.0 |
| **Author:** | Justin Douglas |
| **Organization:** | S_DevLabs (Strategic Development Labs) |
| **Contact:** | S_DevLabs@outlook.com |
| **License:** | MIT |
| **Python:** | ≥ 3.9 |
| **Dependencies:** | `xrpl-py` ≥ 4.5.0, [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) ≥ 0.4.3 (installed from GitHub — not on PyPI yet) |
| **Optional extras:** | `dev` (pytest + pre-commit) |

**What this is in one sentence:**
A small Python library that gives AI agents a tamper-evident history log —
append-only entries, hash-chained via SHA-256, mutually-signed by both
parties with ECDSA over secp256k1. Entries may reference an XRPL transaction
hash you submitted yourself; the library verifies that reference against public
ledger data but never submits a transaction.

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
pip install "xrpl_agent_log @ git+https://github.com/DuNorth595/xrpl_agent_log.git@v0.3.0"
```

Or, for the very latest main:

```bash
pip install "xrpl_agent_log[dev] @ git+https://github.com/DuNorth595/xrpl_agent_log.git@v0.3.0"
```

> **Why no `pip install xrpl_agent_log`?** Both `xrpl_agent_log` and
> `xrpl_agent_id` is published via GitHub, not PyPI. Install from source.
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

> **Repository layout:** this package uses a `src/` layout, while the companion
> [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) uses a flat layout.
> Both are standard Python packaging and both install correctly — only the source
> directory location differs.

## On-chain anchoring

**This library does not submit transactions.** There is no code path in `src/`
that constructs, signs, or sends one.

`on_chain_tx_hash` is an opaque string *you* supply. The library stores it,
folds it into the entry hash so it is tamper-evident like any other field, and
can optionally check that it resolves to a real transaction.

| | |
|---|---|
| Stores your anchor hash | yes |
| Includes it in the entry hash | yes |
| Verifies it resolves to a real tx | yes — requires an `xrpl_client` |
| Submits a Payment transaction | no |
| Chooses an amount or destination | no |
| Decides whether to anchor | no |
| Keeps your keys | no — bring your own `xrpl-py` `Wallet` |

### Typical workflow

```python
from xrpl.clients import WebsocketClient
from xrpl.transaction import Payment, TxResponse

# 1. You decide what, if anything, to put on the ledger.
client = WebsocketClient("wss://xrplcluster.com")
tx: TxResponse = Payment(
    account=wallet,
    destination=anchor_sink,
    amount="1",                      # 1 drop — a minimum-fee payment
    last_ledger_sequence=75,
).submit_and_wait(client)

# 2. You record what you did.
entry = log.append(
    intent="settle",
    params={"invoice": "inv-42"},
    on_chain_tx_hash=tx.result["hash"],
)

# 3. Anyone can later check that reference against public data.
from xrpl_agent_log import verify_on_chain_anchor
result = verify_on_chain_anchor(log, client)
assert result.ok, result.errors
```

### What anchoring does and does not buy you

Anchoring publishes a **timestamped reference**. It proves a transaction existed
at a point in ledger history. It does **not** publish entry contents — the
`params` payload stays wherever your storage is. Entries carrying an anchor are
public by design.

> `verify_on_chain_anchor(log, client=None)` returns `ok=True` when no client is
> passed. A skipped check is not a passing check. If you need anchors verified,
> pass a client.

---

## Relationship to `xrpl_agent_id`

Two libraries, layered:

| | [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) | `xrpl_agent_log` |
|---|---|---|
| Answers | Who is this agent? | What has it done? |
| Produces | identity, credentials, authorization | signed, chained history |
| Needed by the other | no | optional |

`xrpl_agent_id` gives an agent an identity and an authorization model.
`xrpl_agent_log` records agreements **between** two such agents in a form that
cannot be edited afterwards without detection.

The `agent_a_did` / `agent_b_did` fields on an entry reference agent
identities. They are carried as strings; Agent Log does not resolve them and
does not require them to come from Agent ID.

Each library is usable alone. Install `xrpl_agent_id` alongside this one if you
want identity as well as history.

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the hash chain, signing, and anchoring actually work |
| [docs/00_executive_summary.md](docs/00_executive_summary.md) | One-page pitch |
| [docs/01_usage.md](docs/01_usage.md) | API reference + examples |
| [docs/02_testing_log.md](docs/02_testing_log.md) | Test layout, what each layer proves |
| [docs/03_known_issues.md](docs/03_known_issues.md) | Honest disclosures from live testing |
| [SECURITY.md](SECURITY.md) | Security policy, threat model, seed rules |

---

## License

MIT — see [LICENSE](LICENSE).

SPDX-License-Identifier: MIT