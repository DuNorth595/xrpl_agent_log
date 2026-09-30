# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `0.2.x` (latest) | ✅ |
| `0.1.x` | ⚠️ Critical fixes only |
| `< 0.1` | ❌ No longer supported |

## Reporting a vulnerability

**Do not file a public GitHub issue for security bugs.**

Email: `S_DevLabs@outlook.com` (PGP not currently configured — cleartext
accepted for now, switch to a PGP-encrypted channel if you need one and
I'll add a key). Expect an acknowledgement within 72 hours.

Please include:
- Reproduction steps (a failing test is the best case)
- Impact assessment (what an attacker can do)
- XRPL testnet vs. mainnet
- Any associated transaction hashes (testnet is fine to share)

## Threat model

`xrpl_agent_log` is a **client-side library** that maintains append-only,
hash-chained, mutually-signed history logs and (optionally) anchors them
to the XRP Ledger via 1-drop Payment transactions. It does not run a
server, does not hold user funds on the user's behalf, and does not
custody keys.

| Asset | Where it lives | What this library does with it |
|---|---|---|
| Party A seed | Operator's machine (or KMS, in future) | Uses it to sign entries via `xrpl-py`. **Never logs it. Never writes it to disk.** |
| Party B seed | Counterparty's machine | Uses it to sign entries via `xrpl-py`. **Never logs it. Never writes it to disk.** |
| Log entries (SQLite) | Operator's filesystem | Writes via append-only `INSERT` (no UPDATE/DELETE). Signed by both parties at write time. |
| On-chain anchor tx | Public on-ledger | Writes via 1-drop Payment signed by operator's wallet. Plaintext by design — anyone can verify. |
| Chain verification | Local — no network | Computed from local SQLite + pubkey material + (optional) JSON-RPC anchor lookup. |

## Seed-handling rules (for contributors)

1. **Never log a seed.** `print(seed)`, `logger.info(seed)`, `repr(wallet)`,
   `f"wallet={wallet}"`, `traceback.print_exception()` on a wallet — all forbidden.
   `xrpl-py`'s `Wallet` class does not override `__repr__`, so it leaks the seed
   in default reprs. Always log the **classic address** (`wallet.classic_address`),
   never the wallet object itself.
2. **Never commit a seed.** Even for test fixtures. Two layers of
   defense:
   - **Local pre-commit hook** (`.pre-commit-config.yaml` →
     `scripts/check_no_seeds.py`). Install once with
     `pip install -e ".[dev]" && pre-commit install` and every
     `git commit` is blocked if a staged file contains an XRPL
     classic seed (`s...`) or a 64-char hex seed. The scanner
     exits non-zero on a hit.
   - **CI backstop** (`.github/workflows/ci.yml`) runs the same
     scanner via `pre-commit run --all-files`, so even a bypassed
     local hook (`git commit --no-verify`) is caught before merge.
   If you need a wallet for a test, generate one inside the test:
   `Wallet.create()`.
3. **Persist test scripts' seeds with `chmod 600`.** Pattern from
   `scripts/verify_live_anchor.py` — write to `~/.xrpl_testnet_seeds.json` with
   `os.chmod(path, 0o600)`, never to a world-readable path.
4. **Use environment variables, never hardcoded literals.** `os.environ["PARTY_A_SEED"]`,
   not `Seed.from_string("sEd...")`. The env var should be set by the operator
   in a shell that's not logged.
5. **No seeds in error messages.** When wrapping exceptions, log
   `e.args[0]` (the human message), not the full exception object that
   might contain a seed attached by an upstream library.
6. **Memory hygiene is out of scope for this project.** Python strings are
   immutable; you can't reliably scrub a seed from process memory after
   use. Don't try — instead, minimize the seed's lifetime: load, sign,
   drop the reference, `gc.collect()` is overkill but reasonable in
   long-lived processes.

## Cryptographic choices

- **Signing algorithm:** `xrpl-py` uses ECDSA over secp256k1 for transaction
  signing. Library inherits this — no custom crypto.
- **Entry signing:** ECDSA over secp256k1 via `xrpl.core.keypairs.sign()`,
  one signature per party per entry. The signed payload is the entry's
  canonical CBOR-style serialization (sorted keys, deterministic encoding).
- **Chain hashing:** SHA-256 via `hashlib`. Each entry's `prev_hash` is
  `SHA-256(canonical_bytes(entry_{i-1}))`. Tampering with any field of
  entry N invalidates every `prev_hash` for entries N+1, N+2, … — full
  recomputation required.
- **Anchor hashing:** On-chain anchor tx hashes are SHA-256 fingerprints
  validated against the live ledger via `xrpl.models.Tx` + JSON-RPC.
- **No post-quantum crypto.** Plan: revisit if/when XRPL adopts a PQC
  signing scheme. Not on the v0.4.0+ roadmap.

## Dependencies

`xrpl_agent_log` has **two runtime dependencies**:

| Dependency | Why |
|---|---|
| `xrpl-py>=4.5.0` | Wallet creation, signing, JSON-RPC client, on-chain tx submission |
| `xrpl_agent_id>=0.4.0` | DID-based party identity (DIDs are referenced in log metadata) |

And one optional dependency group:

| Extra | What it adds | Why it's optional |
|---|---|---|
| `dev` | `pytest>=8.0`, `pre-commit>=3.5.0` | Only needed for running the test suite and the local seed-scanner hook |

`xrpl-py` is a well-maintained library from the XRP Ledger Foundation.
We pin a minimum version (`>=4.5.0`) but do not pin the patch version.
For supply-chain hardening, run `pip-audit` against your installed
environment; we plan to add this to CI in a future release.

## Known limitations (honest disclosures from live testing)

The following were discovered during real XRPL testnet verification.
None are blockers — all are documented so users know what to expect.

1. **xrpl-py 4.x returns rippled error envelopes in the JSON-RPC result
   instead of raising.** A `txnNotFound` (anchor tx doesn't exist on
   the ledger) comes back as `{"result": {"error": "txnNotFound", ...}}`
   rather than as a Python exception. `verify_on_chain_anchor` was
   updated to detect this envelope explicitly. Future xrpl-py versions
   may change the envelope shape — pinned to `>=4.5.0,<5.0` until v0.3.0.

2. **XRPL rejects 0-XRP Payments on the native payment engine.** Anchor
   txs use 1 drop (`0.000001 XRP`) — the minimum representable native
   amount. Anything less gets `temBAD_AMOUNT`.

3. **XRPL rejects self-payments on the native payment engine.** A
   1-drop Payment from Party A to Party A is rejected with `temBAD_SEND`.
   Mutual logs that anchor from a single party's wallet must use the
   destination tag pattern or send to a *distinct* counterparty
   address. The reference demo uses two testnet wallets.

4. **The seed scanner flags 64-char hex strings.** XRPL tx hashes are
   themselves 64-char hex. The scanner's `LINE_ALLOWLIST` in
   `scripts/check_no_seeds.py` lists every `(file, line)` where a tx
   hash is intentionally embedded in docs. Contributors adding new
   public-data hex strings must add a corresponding allowlist entry
   with a one-line justification.

5. **Live integration test creates real funded wallets.** `tests/test_integration_ledger_live.py`
   is gated on `RUN_LIVE=1` and funds fresh testnet wallets via the
   public faucet. CI does not have funded testnet wallets, so the
   test self-skips in CI. If you fork this library and run those tests
   yourself, the ephemeral wallets get discarded but the issued
   anchor txs persist on the testnet ledger indefinitely.

6. **Faucet rate-limit dominates test runtime, not library correctness.**
   In the live verification report (page 2), 52% of the 92.92s total
   wall-clock was spent on faucet round-trips (one per fresh wallet).
   The library's own logic (chain + sigs + on-chain verify) ran in
   under 2 seconds. **This is a testnet artifact, not a production
   concern.** On mainnet, wallets are funded once via deposit and
   reused; the per-tx cost is ~12 drops (≈$0.000005 USD).

7. **Pre-existing test seeds in the legacy allowlist.** The
   `LEGACY_ALLOWLIST` in `scripts/check_no_seeds.py` permits seed-like
   strings under `tests/` and `test_` paths. This is intentional —
   ephemeral test wallets are constructed at runtime and never
   committed. If you add production seed-like strings to tests, move
   them to `xrpl.wallet.Wallet.create()` or load from environment
   variables.

## Bug bounty

Not currently offered. For responsible disclosure of significant bugs,
email `S_DevLabs@outlook.com` — credit will be given in the CHANGELOG
and the README contributors section, and the fix will be coordinated
with you before public disclosure.

## Acknowledgements

This policy is modelled on the [GitHub Security Lab's guide to writing
a SECURITY.md](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository)
and the [`xrpl_agent_id` SECURITY.md](https://github.com/DuNorth595/xrpl_agent_id/blob/main/SECURITY.md)
which served as the structural template for this library.