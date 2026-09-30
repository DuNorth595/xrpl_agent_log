# xrpl_agent_log

> **Tamper-evident history log for AI agents on the XRP Ledger.**
> Append-only, signed-by-both-parties, replayable from any point.
> Built on top of `xrpl_agent_id` — uses agent identities, does not redefine them.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![xrpl-py 4.5+](https://img.shields.io/badge/xrpl--py-4.5+-black.svg)](https://pypi.org/project/xrpl-py/)
[![xrpl_agent_id 0.4+](https://img.shields.io/badge/xrpl__agent__id-0.4+-green.svg)](https://github.com/DuNorth595/xrpl_agent_id)

---

## Cover Page

| **Package:** | `xrpl_agent_log` |
|---|---|
| **Version:** | 0.1.0 (alpha) |
| **Author:** | Justin Douglas |
| **Organization:** | S_DevLabs (Strategic Development Labs) |
| **Contact:** | S_DevLabs@outlook.com |
| **License:** | MIT |
| **Python:** | ≥ 3.9 |
| **Depends on:** | `xrpl_agent_id` ≥ 0.4, `xrpl-py` ≥ 4.5 |

**What this is in one sentence:**
A Python library that gives two XRPL agents a way to jointly produce a tamper-evident, append-only history log of their interactions — signed by both sides, anchored to on-chain transactions, replayable from any point in the sequence.

**What this is NOT:**
A compliance product, an audit-trail replacement for regulated environments, a legal-record system, or a substitute for on-chain settlement.
A log is a log. It's evidence. It's not a court filing. Don't promise users more than it delivers.

---

## See also

- [`xrpl_agent_id`](../XRPL_AGENT_ID/) — the identity primitives this package depends on. Every agent in a log entry is identified via `did:xrpl` from `xrpl_agent_id`.
- [`XRPL_DEEPDIVE`](../XRPL_DEEPDIVE/) — operational XRPL monitors and dashboards. Independent of this project.

---

## The problem

Two AI agents transact on the XRPL. An hour later, one party claims "I sent X and received Y." The other party claims "I sent X and received Z." The on-chain ledger shows what actually happened, but reconstructing the *intent* — what each side understood the transaction to be, what parameters they agreed to, what state they thought they were in — that information doesn't live anywhere except in each agent's internal memory.

If both agents used `xrpl_agent_log`, each entry in the shared log is:
- Signed by both parties (mutual attestation)
- Anchored to an on-chain transaction hash (verifiable against the ledger)
- Time-ordered (sequence is preserved)
- Hash-chained (any retroactive edit breaks the chain)

The result: a verifiable record of what two agents agreed happened, usable for engineering forensics, financial reconciliation, dispute resolution, and — when needed — production of evidence to a third party.

---

## Design principles

1. **Append-only.** Once an entry is committed, it cannot be edited or deleted. Tampering with any entry breaks the chain and is detectable.
2. **Mutual attestation.** Every entry is signed by both participating agents. Neither party can unilaterally add an entry that the other party didn't also sign.
3. **On-chain anchor optional but recommended.** Each entry can reference an XRPL transaction hash. The hash doesn't store the entry contents — it stores a pointer. The actual log lives off-chain.
4. **Replayability.** Given any entry in the log, you can reconstruct the full state of both agents up to that point. Useful for debugging, dispute resolution, and audit.
5. **Witness optional.** A third-party timestamp witness can attest to when each entry was committed. Useful when log entries may need to support time-sensitive claims (e.g., "this happened before X published Y").
6. **Durable primitives.** The data structures and crypto primitives used here (secp-256k1 signing, SHA-256 hash chaining, XRPL transaction hashes) are designed to outlive any specific XRPL feature. If the XRPL evolves, this package evolves minimally.

---

## What it provides (v0.1.0-alpha scope)

- **`Log`** — the append-only sequence. Add entries, retrieve entries, replay from any point.
- **`Entry`** — a single log record: two agent IDs, optional on-chain tx hash, signed payload, parent hash (chain).
- **`SigningPair`** — the two agent identities whose signatures an entry requires.
- **`Witness`** — optional third-party timestamp attestor. Out of scope for v0.1.0; design only.
- **`Storage`** — pluggable backend. v0.1.0 ships SQLite (the default); future versions may add IPFS, Git, or other append-only stores.
- **`Verify`** — given any entry, return whether it's valid (signatures check, hash chain intact, optional on-chain tx confirms).

---

## What is explicitly NOT in v0.1.0

- **Witness service.** Designed for, not implemented.
- **Multi-party logs.** v0.1.0 supports two-party entries. Multi-party is a v0.3.0 question.
- **On-chain log storage.** Entries are off-chain; only their hashes anchor on-chain. Storing full entries on XRPL is technically possible (via Memos, NFT data, or MPTs) but adds cost and complexity; deferred.
- **Compliance hooks.** This is not an audit product. Don't repackage it as one.
- **Post-quantum signing.** Uses secp-256k1 via `xrpl_agent_id`. Post-quantum migration tracked separately.

---

## What's new in v0.1.0

**Initial alpha.** Project structure mirrors `xrpl_agent_id` for maintainability. Nothing implemented yet — this release exists to lock in the public API surface and the project conventions before code lands.

The next release (v0.2.0) will add:
- `Log`, `Entry`, `SigningPair`, `Storage`, `Verify` modules with tests
- SQLite storage backend
- CLI smoke test
- A two-agent replay demo against the XRPL testnet

---

## Quickstart (planned, not yet implemented)

```python
from xrpl_agent_log import Log, Entry, SigningPair
from xrpl_agent_id.identity import Identity

alice = Identity.from_seed("...")
bob = Identity.from_seed("...")

pair = SigningPair(counterparty_a=alice, counterparty_b=bob)
log = Log.open("xalances://alice-and-bob", storage="sqlite")

# Both agents must sign every entry.
entry = log.append(
    pair=pair,
    intent="alice pays bob 100 XRP for invoice #42",
    on_chain_tx_hash="ABC123...",
    params={"amount_xrp": 100, "memo": "invoice-42"},
)
```

This is the planned interface. v0.1.0 ships the package skeleton; v0.2.0 makes the example run.

---

## Project structure

```
xrpl_agent_log/
├── pyproject.toml
├── README.md                # this file
├── LICENSE
├── SECURITY.md              # threat model + reporting
├── src/xrpl_agent_log/
│   ├── __init__.py
│   ├── log.py               # the append-only sequence
│   ├── entry.py             # one log record
│   ├── signing.py           # mutual-attestation helpers
│   ├── storage/
│   │   ├── base.py          # abstract storage backend
│   │   └── sqlite.py        # default backend
│   ├── verify.py            # chain + signature verification
│   └── cli.py               # command-line entry point
├── tests/                   # pytest suite
├── docs/                    # rendered documentation
├── scripts/                 # build + dev utilities
└── .github/workflows/       # CI: 3.9–3.12 on ubuntu-24.04, same as xrpl_agent_id
```

---

## Roadmap

| Version | Theme | Notes |
|---|---|---|
| v0.1.0 | Skeleton + spec lock | This release. No code, just structure. |
| v0.2.0 | Two-agent replay on testnet | First working version. SQLite storage. CLI smoke test. |
| v0.3.0 | Witness support | Optional third-party timestamp attestation. |
| v0.4.0 | Multi-party entries | More than two signers per entry. |
| v0.5.0 | Cross-log verification | Two logs that share an entry can verify alignment. |
| v1.0.0 | Stable public API | Post-quantum signing support added in parallel. |

---

## Conventions

This project follows the same conventions as `xrpl_agent_id`:

- **MIT license.** SPDX-REUSE compliant.
- **Python 3.9+.** Same matrix as `xrpl_agent_id`.
- **`ubuntu-24.04` CI runner.** Pinned to dodge Oct 19 2026 GitHub migration.
- **`@v7` GitHub Actions.** Pinned for security-patch tracking.
- **No telemetry.** Library is offline by default.
- **Bring your own keys.** Uses `xrpl_agent_id` identity, which uses `xrpl-py`'s `Wallet`.

---

## License

MIT. See `LICENSE`.