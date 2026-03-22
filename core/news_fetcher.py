"""RSS feed aggregator with deduplication."""

import difflib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import yaml
from pathlib import Path

from core.news_store import url_exists

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "news_sources.yaml"
KEYWORDS_PATH = Path(__file__).parent.parent / "config" / "keywords.yaml"

_sources_cache = None
_keywords_cache = None


def _sources() -> dict:
    global _sources_cache
    if _sources_cache is None:
        with open(CONFIG_PATH) as f:
            _sources_cache = yaml.safe_load(f)
    return _sources_cache


def _keywords() -> dict:
    global _keywords_cache
    if _keywords_cache is None:
        with open(KEYWORDS_PATH) as f:
            _keywords_cache = yaml.safe_load(f)
    return _keywords_cache


def _match_keywords(text: str) -> tuple[list[str], list[str]]:
    """Return (matched_terms, matched_groups) for a piece of text."""
    text_lower = text.lower()
    matched_terms = []
    matched_groups = []
    for group_name, group in _keywords()["keyword_groups"].items():
        for term in group.get("terms", []):
            if term.lower() in text_lower:
                matched_terms.append(term)
                if group_name not in matched_groups:
                    matched_groups.append(group_name)
                break
    return matched_terms, matched_groups


def _parse_date(entry) -> str | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return None


def _title_seen(title: str, seen_titles: list[str], threshold: float = 0.85) -> bool:
    for seen in seen_titles:
        ratio = difflib.SequenceMatcher(None, title.lower(), seen.lower()).ratio()
        if ratio >= threshold:
            return True
    return False


_RSS_PROBE_PATHS = ["/feed", "/feed.xml", "/rss", "/rss.xml", "/atom.xml", "/?feed=rss2"]
_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NemoClaw/1.0)"}


def _probe_rss(base_url: str) -> list:
    """Try common RSS paths on base_url. Returns feedparser entries or []."""
    root = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    for path in _RSS_PROBE_PATHS:
        try:
            parsed = feedparser.parse(root + path)
            if parsed.entries:
                logger.debug(f"RSS found at {root + path}")
                return parsed.entries
        except Exception as e:
            logger.debug("RSS probe failed at %s: %s", root + path, e)
    return []


def _scrape_pdf_links(page_url: str) -> list[dict]:
    """GET a page and return all distinct PDF hrefs as minimal article dicts."""
    try:
        resp = requests.get(page_url, timeout=15, headers=_HTTP_HEADERS)
        resp.raise_for_status()
        hrefs = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', resp.text, re.IGNORECASE)
        seen = set()
        results = []
        for href in hrefs:
            full_url = href if href.startswith("http") else urljoin(page_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            filename = full_url.split("/")[-1].split("?")[0]
            results.append({"title": filename, "url": full_url, "summary": ""})
        return results
    except Exception as e:
        logger.warning(f"PDF scrape failed for {page_url}: {e}")
        return []


def _entries_from_feedparser(entries, cfg: dict) -> list[dict]:
    """Convert feedparser entries to article dicts, applying keyword filter and dedup."""
    articles = []
    seen_titles: list[str] = []
    for entry in entries:
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "")
        summary = getattr(entry, "summary", "") or ""

        if not title or (url and url_exists(url)):
            continue
        if _title_seen(title, seen_titles):
            continue

        matched_terms, matched_groups = _match_keywords(f"{title} {summary}")
        seen_titles.append(title)
        articles.append({
            "source": cfg["name"],
            "source_tier": 1,
            "trust_flag": None,
            "title": title,
            "url": url,
            "summary": summary[:500],
            "published_at": _parse_date(entry),
            "matched_keywords": matched_terms,
            "matched_groups": matched_groups,
            "research_category": cfg.get("category", ""),
        })
    return articles


def _entries_from_pdf_links(links: list[dict], cfg: dict) -> list[dict]:
    """Convert scraped PDF links to article dicts (no keyword filter — all PDFs are relevant)."""
    articles = []
    for link in links:
        url = link["url"]
        title = link["title"]
        if not title or (url and url_exists(url)):
            continue
        articles.append({
            "source": cfg["name"],
            "source_tier": 1,
            "trust_flag": None,
            "title": title,
            "url": url,
            "summary": f"Quarterly letter from {cfg.get('author', cfg['name'])}",
            "published_at": None,
            "matched_keywords": [],
            "matched_groups": [cfg.get("category", "research")],
            "research_category": cfg.get("category", ""),
        })
    return articles


def fetch_research_urls() -> list[dict]:
    """Fetch free research URLs (access=free only). Returns articles in same format as fetch_all()."""
    research_cfg = _sources().get("research_urls", {})
    fetch_filter = research_cfg.get("fetch_filter", "free")
    sources = research_cfg.get("sources", [])

    articles = []
    for cfg in sources:
        if cfg.get("access") != fetch_filter:
            continue

        fmt = cfg.get("format", "articles")
        url = cfg["url"]

        if fmt == "pdf_quarterly":
            links = _scrape_pdf_links(url)
            articles.extend(_entries_from_pdf_links(links, cfg))

        else:  # blog, articles, substack — try RSS probe
            entries = _probe_rss(url)
            if entries:
                articles.extend(_entries_from_feedparser(entries, cfg))
            else:
                logger.debug(f"No RSS found for {cfg['name']} ({url}) — skipping")

    return articles


def fetch_all() -> list[dict]:
    """Fetch all RSS feeds, deduplicate, keyword-filter. Returns raw articles."""
    articles = []
    seen_titles: list[str] = []

    for feed_cfg in _sources()["rss_feeds"]:
        try:
            parsed = feedparser.parse(feed_cfg["url"])
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", feed_cfg['name'], e)
            continue

        feed_new = 0
        for entry in parsed.entries:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "") or ""

            if not title:
                continue

            # Dedup by URL
            if url and url_exists(url):
                continue

            # Dedup by title similarity
            if _title_seen(title, seen_titles):
                continue

            # Keyword filter — skip if no match at all
            combined = f"{title} {summary}"
            matched_terms, matched_groups = _match_keywords(combined)
            if not matched_groups:
                continue

            seen_titles.append(title)
            feed_new += 1
            articles.append({
                "source": feed_cfg["name"],
                "source_tier": feed_cfg.get("tier", 2),
                "trust_flag": feed_cfg.get("trust_flag"),
                "title": title,
                "url": url,
                "summary": summary[:500],
                "published_at": _parse_date(entry),
                "matched_keywords": matched_terms,
                "matched_groups": matched_groups,
            })

        if feed_new:
            logger.info("fetched %s — %d new items", feed_cfg["name"], feed_new)

    return articles
