#!/usr/bin/env python3
"""Quick test: fetch each RSS feed and report status."""

import re
import sys
import feedparser
import requests
import yaml
from pathlib import Path
from urllib.parse import urljoin, urlparse

cfg = yaml.safe_load(open(Path(__file__).parent / "config" / "news_sources.yaml"))

# ── RSS feeds ────────────────────────────────────────────────────────────────
ok, fail = [], []

for feed in cfg["rss_feeds"]:
    name = feed["name"]
    url  = feed["url"]
    try:
        parsed = feedparser.parse(url)
        count  = len(parsed.entries)
        if parsed.bozo and count == 0:
            raise Exception(parsed.bozo_exception)
        ok.append(f"  ✓  {name:<35} {count} entries")
    except Exception as e:
        fail.append(f"  ✗  {name:<35} {e}")

print(f"\nRSS feed test — {len(ok)} ok, {len(fail)} failed\n")
for line in ok:
    print(line)
if fail:
    print()
    for line in fail:
        print(line)

# ── Research URLs (free only) ─────────────────────────────────────────────────
RSS_PROBE_PATHS = ["/feed", "/feed.xml", "/rss", "/rss.xml", "/atom.xml", "/?feed=rss2"]
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NemoClaw/1.0)"}

research_cfg = cfg.get("research_urls", {})
fetch_filter = research_cfg.get("fetch_filter", "free")
sources = research_cfg.get("sources", [])
free_sources = [s for s in sources if s.get("access") == fetch_filter]

rok, rfail, rskip = [], [], []

for src in free_sources:
    name = src["name"]
    url  = src["url"]
    fmt  = src.get("format", "articles")

    if fmt == "pdf_quarterly":
        try:
            resp = requests.get(url, timeout=15, headers=HTTP_HEADERS)
            resp.raise_for_status()
            pdfs = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', resp.text, re.IGNORECASE)
            if pdfs:
                rok.append(f"  ✓  {name:<35} {len(pdfs)} PDF link(s) found")
            else:
                rfail.append(f"  ✗  {name:<35} page ok but no PDF links found")
        except Exception as e:
            rfail.append(f"  ✗  {name:<35} {e}")

    else:  # blog / articles — probe RSS
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        found = None
        for path in RSS_PROBE_PATHS:
            try:
                parsed = feedparser.parse(root + path)
                if parsed.entries:
                    found = (root + path, len(parsed.entries))
                    break
            except Exception:
                pass
        if found:
            rok.append(f"  ✓  {name:<35} RSS at {found[0]}  ({found[1]} entries)")
        else:
            rskip.append(f"  -  {name:<35} no RSS found on common paths")

print(f"\nResearch URL test ({fetch_filter} only) — {len(rok)} ok, {len(rfail)} failed, {len(rskip)} no-RSS\n")
for line in rok:
    print(line)
if rskip:
    print()
    for line in rskip:
        print(line)
if rfail:
    print()
    for line in rfail:
        print(line)
print()
