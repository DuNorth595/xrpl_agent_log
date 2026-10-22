# Changelog

All notable changes to `xrpl_agent_log` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-10-22

Fixes a broken install and a documentation layer that did not match the code.

### Fixed
- **`v0.2.0` could not be installed.** The tag's `pyproject.toml` required
  `xrpl_agent_id>=0.4.0` from PyPI, where neither package is published, so pip
  failed to resolve it. That dependency now points at a pinned GitHub tag. This
  release is the first installable tag.
- README quick-start rewritten — every line previously used an API that does not
  exist (`Log(storage=, signers=)`, `log.append(payload)`, `entry.canonical_hash`,
  `verify_signatures(log)`, `verify_on_chain_anchor(log, -1)`).
- The headline "optionally XRPL-anchored / submits 1-drop Payment" claim was
  untrue: the library contains no `Payment` or `submit` call. It records an anchor
  hash you supply and verifies it over JSON-RPC. README and docs corrected.
- `44/44 tests passing` corrected to `43 passed, 1 skipped` — the live testnet
  test is gated behind `RUN_LIVE=1` and self-skips.
- `docs/01_usage.md` API reference regenerated from source; it documented
  `DuplicateSequenceError`, `_with_report()`, `canonical_hash`, `anchor_tx_hash`
  and a `Party` dataclass, none of which exist.
- Three links to `xrpl_agent_log_TEST_REPORT.pdf` pointed at a gitignored file and
  404'd; repointed at tracked markdown.
- `build_test_report_pdf.py` read a path that no longer existed after the report
  moved to `docs/archive/`.
- Development Status Alpha -> Beta.

### Added
- REUSE/SPDX compliance made real: `LICENSES/MIT.txt`, `.reuse/dep5`, and a
  `reuse lint` CI gate, so the badge in the README is now true.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and GitHub issue/PR templates.

### Changed
- Install instructions pinned to a tag (`@v0.2.1`) instead of tracking `main`.
- `SESSION_2026-09-30.md` moved to `docs/internal/`.

## [0.2.0] - 2026-09-30

First public release. **Alpha** — APIs may change before 1.0.0.

### Added
- `Log` — append-only history log requiring both parties' signatures per entry.
- `Entry` — single signed record; SHA-256 hash-chained to prior entry.
- `SigningPair.from_identities(...)` — construct from two `xrpl_agent_id.AgentIdentity` objects.
- `SQLiteStorage` (default backend), `Storage` ABC for pluggable persistence.
- `verify_chain`, `verify_signatures`, `verify_on_chain_anchor` — pure-function integrity checks.
- CLI: `python -m xrpl_agent_log --version`, `--demo` (offline end-to-end run).
- Hash chain: SHA-256 over `(prev_hash, seq, timestamp, intent, params)`.
- Signatures: ECDSA secp256k1 via `xrpl.core.keypairs.sign` / `is_valid_message`.
- Optional on-chain anchor: 1-drop XRPL Payment with memo = entry hash.
- Documentation: `README.md`, `docs/00_executive_summary.md`, `docs/01_usage.md`, `docs/02_testing_log.md`, `docs/03_known_issues.md`, `SECURITY.md`, `SESSION_2026-09-30.md`.
- CI matrix: Python 3.9–3.12 on ubuntu-24.04.
- Pre-commit seed scanner (`scripts/check_no_seeds.py`).

### Security
- Seed-scanner in CI + pre-commit prevents accidental commit of family seeds.
- PII scrub performed: ephemeral testnet wallet addresses redacted; build artifacts (HTML/CSS print templates containing home path) untracked.

### Known limitations
- **No PyPI package.** Both `xrpl_agent_id` and `xrpl_agent_log` install from GitHub via `git+https://...` URLs (PyPI account under S_DevLabs@outlook.com not available).
- **`xrpl_agent_log` requires `xrpl_agent_id` ≥ 0.4.1** installed via `git+https://github.com/DuNorth595/xrpl_agent_id.git@v0.4.1`.
- Two-party signing only — no N-party witness scheme yet.
- Single SQLite file per log — no horizontal sharding.
- MPT-specific anchoring not yet supported (Payment-only).

### See also
- Sibling project: [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) v0.4.1.
- Roadmap: v0.3.0 (ObservationLog + ProposedLog + witness), v0.4.0 multi-party, v0.5.0 cross-log verify, v1.0.0 stable + post-quantum.

[Unreleased]: https://github.com/DuNorth595/xrpl_agent_log/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/DuNorth595/xrpl_agent_log/releases/tag/v0.2.0