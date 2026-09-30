# xrpl_agent_log — Testing Log

## Test layout

| Layer | File | Tests | Time | Coverage |
|---|---|---|---|---|
| Local unit + integration | `tests/test_entry.py`, `test_signing.py`, `test_storage.py`, `test_verify.py`, `test_log.py`, `test_cli.py` | 43 | ~2.0s | All code paths except live ledger |
| Live testnet integration | `tests/test_integration_ledger_live.py` | 1 | ~18s | Full end-to-end with real testnet anchor |
| Live extended verification | `scripts/verify_live_extended.py` | 4 phases | ~93s | Multi-anchor, round-trip lookup, tamper detection, scale |
| Seed scanner (CI gate) | `scripts/check_no_seeds.py` | 2 canary | <1s | Catches classic + hex seeds in staged files |
| Pre-commit backstop | `.pre-commit-config.yaml` | 1 hook | <1s | Same scanner, runs on every commit |

**Total: 50 verification artifacts (44 pytest + 4 extended phases + 2 scanner canaries)**

## What each layer proves

### Local pytest (43 tests)

- Entry serialization is canonical (same payload → same hash)
- Hash chain detects single-byte mutations
- Signature verification fails on tampered entries
- SQLite storage is append-only (raises on duplicate sequence)
- Cross-log isolation (different `log_id`s don't see each other)
- CLI surface is reachable (`--version`, `--demo`)
- Verifier functions return `True` for valid logs and catch known tampering

These run on every commit in CI, on Python 3.9–3.12, ubuntu-24.04.

### Live testnet pytest (1 test)

- Real XRPL testnet anchor submission
- Real JSON-RPC round-trip of the stored anchor hash
- Real on-chain memo round-trip (entry hash → ledger → verifier)
- `verify_chain`, `verify_signatures`, `verify_on_chain_anchor` all
  pass against the live ledger

Gated on `RUN_LIVE=1`. Skipped in CI.

### Live extended verification (4 phases)

- **Phase 1** — multi-anchor chain (3 anchors in one log of 10 entries)
- **Phase 2** — independent JSON-RPC round-trip + memo payload extraction
- **Phase 3** — tampered-anchor detection (verifier rejects a tx hash
  that doesn't exist on the ledger)
- **Phase 4** — scale (50 entries, all three verify_* layers under 0.4s)

Runs the library's *exact* verification path against real testnet txs.
See [`xrpl_agent_log_TEST_REPORT.pdf`](../xrpl_agent_log_TEST_REPORT.pdf)
for the full 5-page report.

### Seed scanner

- **Canary classic seed** (`sEdT...`) — caught, exit 1
- **Canary 64-char hex** — caught, exit 1
- **Real test wallet** (`toxin-classic-...`) in tests — permitted via
  `LEGACY_ALLOWLIST` (tests/ + test_ prefixes)
- **Published tx hash** in `SESSION_2026-09-30.md` — permitted via
  `LINE_ALLOWLIST`

Runs on every commit (pre-commit) and on every PR (CI backstop).

## Honest timing breakdown (from extended verification)

| Phase | Total | Faucet | Tx submit | Verify |
|---|---|---|---|---|
| 1 — Multi-anchor (10 entries, 3 anchors) | 36.72s | 13.39s | 22.26s | 1.07s |
| 2 — Round-trip lookup | 19.74s | 12.93s | 6.49s | 0.32s |
| 3 — Tampered-anchor detection | 22.68s | ~13s | 8.94s | 0.31s |
| 4 — Scale (50 entries) | 13.79s | 13.09s | 0s | 0.70s |
| **TOTAL** | **92.92s** | **~52s (57%)** | **~38s (41%)** | **~2s (2%)** |

The **faucet** is the test-time bottleneck — not the library.
On mainnet, wallets are funded once; per-tx cost is ~12 drops
(≈$0.000005 USD).

## What this library does NOT yet test (v0.4.0+ roadmap)

- Multi-party (3+ signer) logs — see [03_known_issues.md §8](03_known_issues.md#8-v040-roadmap-items-not-yet-shipped)
- Cross-log verification (linked_ref entries between separate logs)
- ObservationLog / ProposedLog modes (v0.3.0)
- Local rippled standalone integration test (would replace faucet-bound live test)

## Running locally

```bash
# Local pytest (43 tests, ~2s)
python -m pytest tests/ -v

# Live testnet pytest (1 test, ~18s; needs network + faucet access)
RUN_LIVE=1 python -m pytest tests/test_integration_ledger_live.py -v

# Live extended verification (4 phases, ~93s; needs network + faucet access)
python scripts/verify_live_extended.py

# Seed scanner (manual)
python scripts/check_no_seeds.py --all-files
```