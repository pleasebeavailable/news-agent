"""Telegram send/receive wrapper."""

import logging
import os
import requests

logger = logging.getLogger(__name__)


def _token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set")
    return token


def chat_id() -> int:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID env var not set")
    return int(chat_id)


def send(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to the configured chat. Returns True on success."""
    url = f"https://api.telegram.org/bot{_token()}/sendMessage"
    payload = {
        "chat_id": chat_id(),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.HTTPError as e:
        logger.error("Telegram send failed: %s %s", e.response.status_code, e.response.reason)
        return False
    except Exception as e:
        logger.error("Telegram send failed: %s: %s", type(e).__name__, e)
        return False


_poll_backoff = 0  # seconds — resets on success, grows on failure

def get_updates(offset: int = 0) -> list[dict]:
    """Poll for new messages. Pass offset = last_update_id + 1 to ack."""
    global _poll_backoff
    url = f"https://api.telegram.org/bot{_token()}/getUpdates"
    params = {"offset": offset, "timeout": 30, "limit": 10}
    try:
        resp = requests.get(url, params=params, timeout=35)
        if resp.status_code == 409:
            import time
            time.sleep(5)
            return []
        resp.raise_for_status()
        _poll_backoff = 0  # reset on success
        return resp.json().get("result", [])
    except Exception as e:
        _poll_backoff = min(_poll_backoff + 5, 60)  # 5s, 10s, 15s ... 60s max
        logger.error("getUpdates failed (retry in %ds): %s", _poll_backoff, e)
        import time
        time.sleep(_poll_backoff)
        return []
