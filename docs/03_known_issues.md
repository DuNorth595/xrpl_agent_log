# xrpl_agent_log — Known Issues & Honest Disclosures

This document captures every honest finding from live XRPL testnet
verification of `xrpl_agent_log` v0.2.0. **None are blockers** — all are
documented so users know what to expect.

## 1. xrpl-py 4.x returns rippled error envelopes in JSON-RPC results

**Severity:** Medium
**Status:** Mitigated in v0.2.0; pinning to `xrpl-py>=4.5.0,<5.0`

A `txnNotFound` (anchor tx doesn't exist on the ledger) comes back as
`{"result": {"error": "txnNotFound", "error_code": 28, ...}}` rather than
as a Python exception. We had two real bugs here during development:

- An early version of `verify_on_chain_anchor` assumed every successful
  JSON-RPC call returned a populated `tx_json` — silently passing
  through `txnNotFound` envelopes and returning `True`.
- An earlier "tamper detection" test only passed because the raw-dict
  code path raised on every shape mismatch — not because it was
  actually testing what it claimed.

Both are fixed. `verify_on_chain_anchor` now uses `xrpl.models.Tx` to
parse the response and explicitly checks for the `error` envelope key
before declaring success.

## 2. XRPL rejects 0-XRP Payments on the native payment engine

**Severity:** Low (one-line fix)
**Status:** Mitigated

`Amount: "0"` is rejected with `temBAD_AMOUNT`. Anchor transactions use
**1 drop** (`"1"` as the Amount string, representing `0.000001 XRP`).

## 3. XRPL rejects self-payments on the native payment engine

**Severity:** Low (architectural)
**Status:** Mitigated by design

A 1-drop Payment from Party A → Party A is rejected with `temBAD_SEND`.
Mutual logs that anchor from a single party's wallet must use either:

- A **distinct counterparty address** (the reference demo — Party A
  sends to Party B, both of whom already had to be online to produce
  the entry)
- A **destination tag** to disambiguate the destination
- An **alternative anchor pattern** (e.g., `AccountSet` with the
  entry hash as `MessageKey`)

The reference demo and tests use two distinct testnet wallets.

## 4. Seed scanner flags 64-char hex strings

**Severity:** Informational (working as intended)
**Status:** Documented

XRPL transaction hashes are themselves 64-char hex. The scanner's
`LINE_ALLOWLIST` in `scripts/check_no_seeds.py` lists every
`(file, line)` where a tx hash is intentionally embedded in docs.
Contributors adding new public-data hex strings must add a
corresponding allowlist entry with a one-line justification.

## 5. Live integration test creates real funded wallets

**Severity:** Informational (intentional)
**Status:** Documented

`tests/test_integration_ledger_live.py` is gated on `RUN_LIVE=1` and
funds fresh testnet wallets via the public faucet. CI does not have
funded testnet wallets, so the test self-skips in CI. The ephemeral
wallets are discarded after the test; the issued anchor txs persist
on the testnet ledger indefinitely. Public, by design.

## 6. Faucet rate-limit dominates test runtime, not library correctness

**Severity:** Informational (test artifact, not production concern)
**Status:** Documented

In the live verification report, **52% of the 92.92s total wall-clock
was spent on faucet round-trips** (one per fresh wallet). The library's
own logic (chain + sigs + on-chain verify) ran in under 2 seconds.

**This is a testnet artifact, not a production concern.** On mainnet,
wallets are funded once via deposit and reused; the per-tx cost is ~12
drops (≈$0.000005 USD).

## 7. Pre-existing test seeds in the legacy allowlist

**Severity:** Informational (working as intended)
**Status:** Documented

The `LEGACY_ALLOWLIST` in `scripts/check_no_seeds.py` permits
seed-like strings under `tests/` and `test_` paths. This is intentional —
ephemeral test wallets are constructed at runtime and never committed.
If you add production seed-like strings to tests, move them to
`xrpl.wallet.Wallet.create()` or load from environment variables.

## 8. v0.4.0+ roadmap items (not yet shipped)

- **Multi-party (3+) logs.** Current design supports exactly two
  signers (`party_a`, `party_b`). 3+ requires a generalized signature
  collection loop.
- **Cross-log verification.** Two logs from different systems producing
  interlinked entries (e.g., a service log + a counterparty log
  producing matching `linked_ref` entries).
- **ObservationLog mode** (one-party-signed, no mutual attestation).
  Useful for unilateral audit trails.
- **ProposedLog mode** (one party signs a proposal; counterparty
  counter-signs later). Useful for asynchronous workflows.
- **Local rippled standalone integration test.** Would replace the
  faucet-bound live test with a 50ms-confirmation, no-faucet local
  integration test. Pure library-correctness check.

## 9. What v0.2.0 does NOT cover

- **Privacy.** Anchors and memos are public on the ledger. If you need
  confidential logs, encrypt the payload before calling `log.append()`
  and store the key elsewhere.
- **Key management.** We don't custody keys. Use `xrpl-py`'s `Wallet`
  (or a future KMS wrapper) and pass it in.
- **Ledger fallback if xrpl-py changes.** We're pinned to
  `xrpl-py>=4.5.0,<5.0`. A v5.0 release will require a minor version
  bump here.
- **Performance tuning.** SQLite is fine for thousands of entries; for
  millions, swap `SQLiteStorage` for a custom backend (the interface is
  stable).

---

*Last updated 2026-09-30 — reflects v0.2.0 working implementation.*