# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""SigningPair.from_identities must not use the deprecated .wallet accessor.

xrpl_agent_id v0.5.0 renamed `AgentIdentity.wallet` to
`AgentIdentity.provider` and deprecated the old name; it is removed in
v0.6.0. `AgentIdentity.wallet` also raises AttributeError for an
identity backed by an external signer, because such an identity has no
in-process key.

These tests pin both behaviours so the log keeps working when
.wallet goes away.
"""

from __future__ import annotations

import warnings

import pytest

xrpl_agent_id = pytest.importorskip("xrpl_agent_id")

from xrpl_agent_id import AgentIdentity, ExternalSignerProvider  # noqa: E402

from xrpl_agent_log import SigningPair  # noqa: E402


def _seed() -> str:
    import xrpl.core.keypairs.main as km

    return km.generate_seed()


def test_from_identities_uses_provider_not_the_deprecated_wallet() -> None:
    a = AgentIdentity.from_seed(_seed(), network="testnet")
    b = AgentIdentity.from_seed(_seed(), network="testnet")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pair = SigningPair.from_identities(a, b)

    deprecations = [
        str(w.message) for w in caught
        if issubclass(w.category, DeprecationWarning)
    ]
    assert not deprecations, (
        "from_identities triggered a DeprecationWarning: "
        f"{deprecations}. It is using AgentIdentity.wallet, which is "
        "removed in xrpl_agent_id v0.6.0."
    )

    assert pair.wallet_a is not None
    assert pair.wallet_b is not None
    assert pair.did_a == a.did
    assert pair.did_b == b.did
    assert pair.network == "testnet"


def test_from_identities_rejects_an_external_signer_clearly() -> None:
    """An identity with no in-process key must fail with a useful message."""
    provider = ExternalSignerProvider(
        classic_address="rExternalSignerAddressHere",
        public_key="EC" + "1" * 52,
        signer=lambda message_hex: "00" * 35,
    )
    external = AgentIdentity(provider=provider, network="testnet")
    local = AgentIdentity.from_seed(_seed(), network="testnet")

    with pytest.raises(ValueError) as exc:
        SigningPair.from_identities(external, local)

    message = str(exc.value)
    assert "from_wallets_with_dids" in message, (
        f"the error should point at the alternative API, got: {message}"
    )
