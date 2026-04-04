"""SQLite storage for scored news articles."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "news_log.db"

logger = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scored_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_tier INTEGER,
                title TEXT NOT NULL,
                url TEXT,
                published_at DATETIME,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                matched_keywords TEXT,
                matched_groups TEXT,
                score INTEGER NOT NULL,
                category TEXT,
                affected_tickers TEXT,
                summary TEXT,
                portfolio_impact TEXT,
                suggested_action TEXT,
                confidence TEXT,
                alerted BOOLEAN DEFAULT 0,
                included_in_brief BOOLEAN DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_score ON scored_news(score);
            CREATE INDEX IF NOT EXISTS idx_fetched ON scored_news(fetched_at);
            CREATE INDEX IF NOT EXISTS idx_category ON scored_news(category);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_url ON scored_news(url) WHERE url IS NOT NULL;
        """)


def save_article(article: dict) -> int | None:
    """Save article. Returns the row id (new or existing), or None on error."""
    try:
        with _conn() as conn:
            cur = conn.execute("""
                INSERT OR IGNORE INTO scored_news
                  (source, source_tier, title, url, published_at,
                   matched_keywords, matched_groups, score, category,
                   affected_tickers, summary, portfolio_impact,
                   suggested_action, confidence)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                article.get("source"),
                article.get("source_tier"),
                article["title"],
                article.get("url"),
                article.get("published_at"),
                json.dumps(article.get("matched_keywords", [])),
                json.dumps(article.get("matched_groups", [])),
                article["score"],
                article.get("category"),
                json.dumps(article.get("affected_tickers", [])),
                article.get("summary"),
                article.get("portfolio_impact"),
                article.get("suggested_action"),
                article.get("confidence"),
            ))
            if cur.lastrowid:
                logger.debug("saved: [%d] %s", article["score"], article["title"][:80])
                return cur.lastrowid
            # Row already existed (INSERT OR IGNORE skipped) — look up by URL
            url = article.get("url")
            if url:
                row = conn.execute("SELECT id FROM scored_news WHERE url=?", (url,)).fetchone()
                if row:
                    return row["id"]
            return None
    except Exception as e:
        logger.error("failed to save article '%s': %s", article.get("title", "?")[:60], e)
        return None


def url_exists(url: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM scored_news WHERE url = ?", (url,)
        ).fetchone()
        return row is not None


def mark_alerted(article_id: int):
    with _conn() as conn:
        conn.execute("UPDATE scored_news SET alerted=1 WHERE id=?", (article_id,))


def try_mark_alerted(article_id: int) -> bool:
    """Atomically mark an article as alerted. Returns True if this call did the update (i.e. it wasn't already alerted)."""
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE scored_news SET alerted=1 WHERE id=? AND alerted=0",
            (article_id,),
        )
        return cur.rowcount > 0


def get_recent_titles(since_hours: int = 48) -> list[str]:
    """Return titles from the last *since_hours* for cross-cycle dedup."""
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT title FROM scored_news WHERE fetched_at >= ?",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    return [r["title"] for r in rows]


def get_recent_alerted_titles(since_hours: int = 24) -> list[str]:
    """Return titles of articles that were already alerted in the last *since_hours*."""
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT title FROM scored_news WHERE alerted=1 AND fetched_at >= ?",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    return [r["title"] for r in rows]


def get_recent(since_hours: int = 16, min_score: int = 5, limit: int = 10) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM scored_news
            WHERE fetched_at >= ? AND score >= ?
            ORDER BY score DESC, fetched_at DESC
            LIMIT ?
        """, (since.strftime("%Y-%m-%d %H:%M:%S"), min_score, limit)).fetchall()
    results = [dict(r) for r in rows]
    logger.debug("get_recent(%dh, score>=%d) → %d articles", since_hours, min_score, len(results))
    return results
