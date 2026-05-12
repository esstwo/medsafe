"""
Download NIH ODS supplement fact sheets → data/nih_ods/

Scrapes the NIH Office of Dietary Supplements fact sheet listing page,
downloads each fact sheet as plain text, and saves to disk.
Does NOT index into ChromaDB — that is deferred to Week 5.

Run from backend/:  python -m scripts.ingest_nih_ods
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ODS_BASE = "https://ods.od.nih.gov"
ODS_LIST_URL = f"{ODS_BASE}/factsheets/list-all/"


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name.lower().strip())


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
    return None


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove nav, header, footer, scripts
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    # Get main content area
    main = soup.find("main") or soup.find("div", {"id": "content"}) or soup.body
    if main is None:
        return ""
    text = main.get_text(separator="\n")
    # Clean up whitespace
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def scrape_fact_sheet_links(html: str) -> list[tuple[str, str]]:
    """Return [(name, url), ...] for all fact sheet links on the listing page."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if "/factsheets/" in href and "list" not in href and "VitalMix" not in href:
            name = a.get_text(strip=True)
            url = href if href.startswith("http") else ODS_BASE + href
            if name and url not in [u for _, u in links]:
                links.append((name, url))
    return links


async def main() -> None:
    from app.config import get_settings

    settings = get_settings()
    out_dir = Path(settings.chroma_persist_path).parent / "nih_ods"
    out_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        headers={"User-Agent": "MedSafe Research Tool (educational use)"},
        follow_redirects=True,
    ) as client:
        logger.info("Fetching ODS fact sheet listing...")
        listing_html = await fetch_page(client, ODS_LIST_URL)
        if not listing_html:
            logger.error("Could not load ODS listing page. Aborting.")
            sys.exit(1)

        links = scrape_fact_sheet_links(listing_html)
        logger.info("Found %d fact sheet links.", len(links))

        downloaded = 0
        for name, url in links:
            filename = _safe_filename(name) + ".txt"
            out_path = out_dir / filename
            if out_path.exists():
                logger.debug("Already downloaded: %s", filename)
                downloaded += 1
                continue

            html = await fetch_page(client, url)
            if not html:
                continue

            text = extract_text(html)
            if len(text) > 200:
                out_path.write_text(text, encoding="utf-8")
                downloaded += 1
                logger.info("Saved: %s (%d chars)", filename, len(text))
            else:
                logger.debug("Too short, skipping: %s", name)

            time.sleep(0.5)  # polite crawl rate

    logger.info("NIH ODS download complete. %d fact sheets saved to %s", downloaded, out_dir)
    logger.info("Note: indexing into ChromaDB is deferred to Week 5.")


if __name__ == "__main__":
    asyncio.run(main())
