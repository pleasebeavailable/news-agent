"""Nemotron inference client — wraps the local OpenAI-compatible endpoint."""

import json
import logging
import time

import requests

ENDPOINT = "https://inference.local/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds between retries

logger = logging.getLogger(__name__)


def chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """Send a chat completion request with retry. Returns the assistant message text."""
    logger.info("LLM call — %d messages, max_tokens=%d", len(messages), max_tokens)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            resp = requests.post(
                f"{ENDPOINT}/chat/completions",
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=90,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"]
            logger.info("LLM response — %.1fs, %d chars", time.time() - t0, len(result))
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
    return json.loads(text)
