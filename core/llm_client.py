"""Nemotron inference client — wraps the local OpenAI-compatible endpoint."""

import json
import logging
import os
import time

import requests

ENDPOINT = "https://inference.local/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds between retries

logger = logging.getLogger(__name__)


def _headers() -> dict:
    """Build request headers — includes API key as safety net outside gateway routing.
    WARNING: Do not log the returned dict — it may contain the bearer token."""
    h = {"Content-Type": "application/json", "User-Agent": "NemoClaw/2.0"}
    api_key = os.environ.get("NVIDIA_API_KEY")
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """Send a chat completion request with retry. Returns the assistant message text."""
    logger.info("LLM call — %d messages, max_tokens=%d", len(messages), max_tokens)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            resp = requests.post(
                f"{ENDPOINT}/chat/completions",
                headers=_headers(),
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=90,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"] or ""
            finish = data["choices"][0].get("finish_reason", "unknown")
            logger.info("LLM response — %.1fs, %d chars, finish=%s", time.time() - t0, len(result), finish)
            if finish == "length" and result.strip():
                logger.warning("LLM response truncated (finish_reason=length, max_tokens=%d)", max_tokens)
            if not result.strip():
                if attempt < MAX_RETRIES - 1:
                    logger.warning("LLM returned empty (attempt %d/%d, finish=%s), retrying",
                                   attempt + 1, MAX_RETRIES, finish)
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                    continue
                logger.error("LLM returned empty after all %d attempts (finish=%s)", MAX_RETRIES, finish)
            return result
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            logger.warning("LLM timeout/connection error (attempt %d/%d), retrying in %ds: %s",
                           attempt + 1, MAX_RETRIES, wait, e)
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code >= 500:
                last_error = e
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                logger.warning("LLM server error %d (attempt %d/%d), retrying in %ds",
                               e.response.status_code, attempt + 1, MAX_RETRIES, wait)
                time.sleep(wait)
            else:
                raise  # 4xx errors are not retryable

    raise last_error  # all retries exhausted


def json_chat(messages: list[dict], temperature: float = 0.1, max_tokens: int = 1024) -> dict:
    """Like chat(), but parses and returns the JSON response body."""
    text = chat(messages, temperature=temperature, max_tokens=max_tokens)
    # Strip markdown code fences if model wraps response
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s | raw: %.200s", e, text)
        raise
