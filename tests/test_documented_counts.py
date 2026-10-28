# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Pin the counts that the published documentation quotes.

Documentation that quotes a number nothing keeps in sync is the most
common way a repository starts to look careless. The test counts here
had already drifted once (43 -> 46) before this file existed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _offline_test_count() -> int:
    """Count the test functions in the suite, statically.

    The live testnet test is gated behind RUN_LIVE and self-skips, so
    the offline figure is one less than the total. Parsing the source
    rather than running the suite keeps this check from shelling out to
    pytest -- which would recurse, since this file is part of the suite.
    """
    total = 0
    for path in TESTS.glob("test_*.py"):
        source = path.read_text(encoding="utf-8")
        total += len(re.findall(r"^def (test_\w+)", source, re.M))
    return total


def _own_test_count() -> int:
    """How many test functions this guard file contributes."""
    source = Path(__file__).read_text(encoding="utf-8")
    return len(re.findall(r"^def (test_\w+)", source, re.M))


def _live_gated_count() -> int:
    """Tests that self-skip unless RUN_LIVE is set.

    Two forms are in use: a module-level ``pytestmark`` that gates every
    test in the file, and a per-test ``@pytest.mark.skipif`` decorator.
    Both have to be counted.
    """
    gated = 0
    for path in TESTS.glob("test_*.py"):
        source = path.read_text(encoding="utf-8")
        total = len(re.findall(r"^def (test_\w+)", source, re.M))

        # Per-test decorator.
        decorated = len(re.findall(
            r"@pytest\.mark\.skipif\([^)]*RUN_LIVE[^)]*\)\s*\ndef\s+test_",
            source,
        ))

        # Module-level pytestmark gating the whole file.
        module_gated = 0
        if re.search(r"^pytestmark\s*=\s*pytest\.mark\.skipif\(", source, re.M):
            block = source[source.find("pytestmark"):]
            if re.search(r"RUN_LIVE", block[:400]):
                module_gated = total

        gated += decorated + module_gated
    return gated


def test_documented_offline_count_is_current() -> None:
    """Every document quoting an offline test count must quote the real one.

    The count is the number of tests in the library's own suite -- the
    tests that exercise the library -- excluding this guard file and
    excluding the ones gated behind RUN_LIVE.

    Excluding this file is deliberate and permanent. If the guard
    counted itself, then adding a check to the guard would change the
    number the documents quote, and the guard would fail every time
    someone extended it. The number that matters is the size of the
    library's test suite, and that is stable.
    """
    expected = _offline_test_count() - _live_gated_count() - _own_test_count()

    docs = {
        "README.md": r"(\d+) offline tests pass",
        "CONTRIBUTING.md": r"The offline suite is (\d+) tests",
        "docs/00_executive_summary.md": r"\*\*(\d+) offline tests pass",
        "docs/02_testing_log.md": r"Local pytest \((\d+) tests",
    }
    for rel, pattern in docs.items():
        text = _read(rel)
        found = re.search(pattern, text)
        assert found, f"{rel} no longer states an offline test count"
        stated = int(found.group(1))
        assert stated == expected, (
            f"{rel} says {stated} offline tests; the suite has {expected}."
        )


def test_version_is_consistent() -> None:
    """The package version must match the one in pyproject and the README."""
    import xrpl_agent_log

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'version\s*=\s*"([^"]+)"', pyproject).group(1)

    assert xrpl_agent_log.__version__ == version, (
        f"pyproject.toml says {version} but the package says "
        f"{xrpl_agent_log.__version__}"
    )
    assert f"| **Version:** | {version} |" in _read("README.md"), (
        f"README.md does not state version {version}"
    )
    assert f"release-v{version}-blue" in _read("README.md"), (
        f"README.md release badge does not say v{version}"
    )


def test_dependency_pins_agree_with_xrpl_agent_id() -> None:
    """The xrpl-py pin must match the one xrpl_agent_id requires.

    The two packages must resolve together. When this package pinned
    xrpl-py<5.0 while xrpl_agent_id required >=5.0, pip silently
    downgraded xrpl_agent_id to v0.4.3 whenever both were installed.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    xrpl_py = re.search(r'"xrpl-py([^"]*)"', pyproject)
    assert xrpl_py, "pyproject.toml does not pin xrpl-py"
    assert ">=5.0" in xrpl_py.group(1), (
        f"the xrpl-py pin is {xrpl_py.group(1)!r}; xrpl_agent_id v0.5.x "
        "requires >=5.0, and a narrower pin makes pip downgrade it."
    )

    agent_id = re.search(r'"xrpl_agent_id @ git\+[^"]*@([^"]+)"', pyproject)
    assert agent_id, "pyproject.toml does not pin xrpl_agent_id"
    assert agent_id.group(1) >= "v0.5.1", (
        f"xrpl_agent_id is pinned at {agent_id.group(1)}; v0.5.1 is the "
        "first release whose AgentIdentity.provider accessor works "
        "without a deprecation warning."
    )
