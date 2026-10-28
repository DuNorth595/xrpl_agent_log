# Changelog

All notable changes to `xrpl_agent_log` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-10-28

Dependency compatibility with `xrpl_agent_id` v0.5.x, and one API change
that keeps a deprecated accessor out of the hot path.

### Fixed
- **Installing both packages silently downgraded `xrpl_agent_id`.** This
  package pinned `xrpl-py>=4.5.0,<5.0` while `xrpl_agent_id` v0.5.x
  requires `xrpl-py>=5.0,<6`. pip resolved the conflict by installing
  `xrpl_agent_id` v0.4.3 and `xrpl-py` 4.5.0 — so a user who installed
  both got the old versions of both, with no error. The pins now agree:
  `xrpl-py>=5.0,<6` and `xrpl_agent_id` v0.5.1.
- **`SigningPair.from_identities()` used the deprecated
  `AgentIdentity.wallet`.** `xrpl_agent_id` v0.5.0 renamed it to
  `.provider` and deprecated the old name; it is removed in v0.6.0. The
  method now reads `.provider`, so it raises no `DeprecationWarning` and
  will keep working after v0.6.0.

### Changed
- An identity whose provider signs externally — a KMS or hardware
  wallet — has no in-process key, because a log entry is signed with an
  arbitrary message rather than an XRPL transaction. `from_identities()`
  now raises a `ValueError` that names the alternative,
  `SigningPair.from_wallets_with_dids()`, instead of an `AttributeError`
  from deep inside the identity object.

### Added
- `tests/test_identity_pairing.py` — pins both behaviours: no
  `DeprecationWarning` from `from_identities()`, and a clear error for
  an externally-signing identity.
- The README's "Relationship to `xrpl_agent_id`" section now shows the
  two packages working together, states the version compatibility
  requirement, and explains why an external signer cannot be used for
  this side of the pair.

## [0.3.0] - 2026-10-23

Documentation, packaging, and a dependency correction. No API changes.

### Fixed
- **The headline claim about on-chain anchoring was untrue.** The tagline and the
  one-sentence description said the library anchors "via 1-drop Payment
  transactions." It does not. `src/` contains no `submit`, `submit_and_wait`,
  `Transaction(`, `Wallet(`, `autofill`, or `Payment(` — there is no code path
  that constructs, signs, or sends a transaction. `on_chain_tx_hash` is a
  caller-supplied opaque string: the library stores it, folds it into the entry
  hash so it is tamper-evident, and can optionally verify it resolves to a real
  transaction. It does not decide what to anchor, or whether to. The README
  already said "this library does NOT submit transactions" while pointing at an
  "On-chain anchoring" section that did not exist; that section is now written.
- **`__version__` reported the installed metadata instead of the running code.**
  The module preferred `importlib.metadata` and overwrote `__version__` with
  it. With an editable install, the installed metadata is stale the moment the
  source is bumped and before a reinstall, so `__version__` reported the *old*
  version for the *new* code — a drift report that looks self-consistent, which
  is the worst direction for it to be wrong in. The source literal is now
  authoritative and any mismatch raises a `RuntimeWarning` instead of silently
  substituting the wrong number. (`xrpl_agent_id` had the same bug; both are
  fixed the same way.)
- **The `xrpl_agent_id` dependency was pinned to `v0.4.2`**, which predates the
  five security fixes released in `xrpl_agent_id` v0.4.3. An install of this
  release now pulls the fixed version.

### Added
- `docs/ARCHITECTURE.md` — components, hash chain, mutual signing, verification,
  storage, CLI, and trust boundaries, with every claim traced to a source line.
  It also records the three behaviours that read as oversights but are
  deliberate: genesis uses `parent_hash=None`, DIDs match by string suffix
  rather than being parsed, and a skipped anchor check reports `ok=True`.
- `docs/README.md` — documentation index.
- The relationship between `xrpl_agent_id` and `xrpl_agent_log`, which was
  invisible from either repo.

### Changed
- Package metadata now carries the org name and org contact address in
  `authors`, the field pip reads and prints on install.
- A dangling README link to a session file deleted in `67ee382` was removed.

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
- **`xrpl_agent_log` requires `xrpl_agent_id` ≥ 0.4.3** installed via `git+https://github.com/DuNorth595/xrpl_agent_id.git@v0.4.3`.
- Two-party signing only — no N-party witness scheme yet.
- Single SQLite file per log — no horizontal sharding.
- MPT-specific anchoring not yet supported (Payment-only).

### See also
- Sibling project: [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) v0.4.3.
- Roadmap: v0.4.0 (ObservationLog + ProposedLog + witness), v0.5.0 multi-party, v0.6.0 cross-log verify, v1.0.0 stable + post-quantum.

[Unreleased]: https://github.com/DuNorth595/xrpl_agent_log/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/DuNorth595/xrpl_agent_log/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/DuNorth595/xrpl_agent_log/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/DuNorth595/xrpl_agent_log/releases/tag/v0.2.0