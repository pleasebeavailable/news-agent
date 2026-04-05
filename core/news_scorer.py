"""LLM-based news relevance scoring via Nemotron."""

import logging
from pathlib import Path

from core import llm_client, config_loader

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "news_scoring.txt"
_prompt_template = None


def clear_cache():
    global _prompt_template
    _prompt_template = None


def _prompt() -> str:
    global _prompt_template
    if _prompt_template is None:
        with open(PROMPT_PATH) as f:
            _prompt_template = f.read()
    return _prompt_template


def score_article(article: dict) -> dict | None:
    """Score a single article. Returns the article dict enriched with score fields, or None on failure."""
    # Inject portfolio context via replace() before .format() to avoid brace conflicts in thesis text
    portfolio_ctx = config_loader.portfolio_scoring_context()
    safe_ctx = portfolio_ctx.replace("{", "{{").replace("}", "}}")
    raw = _prompt().replace("{portfolio_context}", safe_ctx)
    prompt = raw.format(
        source_name=article["source"],
        source_tier=article["source_tier"],
        title=article["title"],
        summary=article.get("summary", ""),
        pub_date=article.get("published_at", "unknown"),
        matched_keywords=", ".join(article.get("matched_keywords", [])),
        matched_groups=", ".join(article.get("matched_groups", [])),
    )

    messages = [{"role": "user", "content": prompt}]

    try:
        result = llm_client.json_chat(messages, temperature=0.1, max_tokens=1024)
    except Exception as e:
        logger.error("Scoring failed for '%s': %s", article['title'][:80], e)
        return None

    if not isinstance(result, dict):
        logger.error("Scorer returned non-dict for '%s': %s", article['title'][:80], type(result).__name__)
        return None

    # Trust adjustment: editorial sources capped at 7
    if article.get("trust_flag") == "editorial" and result.get("score", 0) > 7:
        result["score"] = 7

    article.update({
        "score": result.get("score", 0),
        "category": result.get("category"),
        "affected_tickers": result.get("affected_tickers", []),
        "summary": result.get("summary", article.get("summary", "")),
        "portfolio_impact": result.get("portfolio_impact"),
        "suggested_action": result.get("suggested_action"),
        "kill_switch_triggered": result.get("kill_switch_triggered", False),
        "confidence": result.get("confidence", "low"),
    })
    return article


def score_batch(articles: list[dict]) -> list[dict]:
    """Score a list of articles, returning only those with score >= 5."""
    scored = []
    for article in articles:
        result = score_article(article)
        if result and result["score"] >= 5:
            scored.append(result)
    return sorted(scored, key=lambda x: x["score"], reverse=True)
