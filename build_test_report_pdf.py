# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""build_test_report_pdf.py — Render the live test report into a Letter PDF.

Mirrors the proven build_pdf.py pipeline used for xrpl_agent_id README:
  1. pandoc        → LIVE_TEST_REPORT.md → standalone HTML
  2. Playwright    → HTML → PDF (Letter, print_background)
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright


HERE = Path(__file__).parent
MD_IN = HERE / "LIVE_TEST_REPORT.md"
HTML_OUT = HERE / "xrpl_agent_log_TEST_REPORT.html"
PDF_OUT = HERE / "xrpl_agent_log_TEST_REPORT.pdf"

COVER = HERE / "_cover.html"
FOOTER = HERE / "_footer.html"
PRINT_CSS = HERE / "_print_css.css"


async def main() -> None:
    print(f"Rendering {MD_IN.name} → {HTML_OUT.name} (pandoc)...")
    cmd = [
        "pandoc",
        str(MD_IN),
        "--from", "markdown",
        "--to", "html5",
        "--standalone",
        f"--include-before-body={COVER}",
        f"--include-after-body={FOOTER}",
        "--css", str(PRINT_CSS),
        # Suppress pandoc's automatic <h1 class="title"> rendering at the top
        # of the body (the cover banner already provides the title).
        "--variable", "title=",
        "--variable", "author=",
        "-o", str(HTML_OUT),
    ]
    subprocess.run(cmd, check=True)

    print(f"Rendering {HTML_OUT.name} → {PDF_OUT.name} (playwright)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{HTML_OUT.resolve()}", wait_until="networkidle")
        await page.pdf(
            path=str(PDF_OUT),
            format="Letter",
            print_background=True,
            margin={"top": "0.6in", "bottom": "0.7in", "left": "0.65in", "right": "0.65in"},
        )
        await browser.close()

    print(f"Done: {PDF_OUT}  ({PDF_OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())