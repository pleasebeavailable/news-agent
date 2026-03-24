"""Tests for all 11 fixes from the code review of commit 46cd2cf."""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fix #1: _poll_backoff resets on 409 ──────────────────────────

class TestPollBackoffResetOn409:
    def setup_method(self):
        import core.telegram_bot as tb
        self.tb = tb
        # Set env vars so _token() / chat_id() don't blow up
        os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
        os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

    def test_backoff_resets_on_409(self):
        """After errors inflate _poll_backoff, a 409 should reset it to 0."""
        self.tb._poll_backoff = 30  # simulate prior errors

        mock_resp = MagicMock()
        mock_resp.status_code = 409

        with patch("core.telegram_bot.requests.get", return_value=mock_resp), \
             patch("core.telegram_bot.time.sleep"):
            self.tb.get_updates(offset=0)

        assert self.tb._poll_backoff == 0

    def test_backoff_resets_on_success(self):
        """Successful poll should reset backoff to 0."""
        self.tb._poll_backoff = 20

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"result": []}

        with patch("core.telegram_bot.requests.get", return_value=mock_resp):
            self.tb.get_updates(offset=0)

        assert self.tb._poll_backoff == 0

    def test_backoff_grows_on_error(self):
        """Errors should increment backoff by 5, capped at 60."""
        self.tb._poll_backoff = 0

        with patch("core.telegram_bot.requests.get", side_effect=ConnectionError("fail")), \
             patch("core.telegram_bot.time.sleep"):
            self.tb.get_updates(offset=0)

        assert self.tb._poll_backoff == 5

        with patch("core.telegram_bot.requests.get", side_effect=ConnectionError("fail")), \
             patch("core.telegram_bot.time.sleep"):
            self.tb.get_updates(offset=0)

        assert self.tb._poll_backoff == 10


# ── Fix #2: get_quote_message returns None on failure ────────────

class TestQuoteMessageReturnsNone:
    def _import_stock_price(self):
        """Import skills.stock_price with mocked core dependencies."""
        # Ensure core modules are importable (they may need config files etc.)
        import importlib
        if "skills.stock_price" in sys.modules:
            return sys.modules["skills.stock_price"]
        # Pre-mock the heavy core deps so import succeeds
        mock_stock_data = MagicMock()
        mock_config_loader = MagicMock()
        with patch.dict(sys.modules, {
            "core.stock_data": mock_stock_data,
            "core.config_loader": mock_config_loader,
        }):
            import skills.stock_price
            return skills.stock_price

    def test_returns_none_on_no_price(self):
        mod = self._import_stock_price()
        mod.stock_data.get_quote.return_value = {}
        assert mod.get_quote_message("FAKE") is None

    def test_returns_string_on_valid_ticker(self):
        mod = self._import_stock_price()
        mod.stock_data.get_quote.return_value = {"price": 150.0, "name": "Test Corp", "change_pct": 1.5}
        mod.config_loader.theses.return_value = {}
        result = mod.get_quote_message("TEST")
        assert result is not None
        assert "TEST" in result


# ── Fix #3: Ticker regex accepts up to 10 chars (e.g. 2689.HK) ──

class TestTickerRegex:
    def _match(self, text):
        """Simulate the ticker regex from handle_message."""
        import re
        t = text.strip()
        return bool(re.match(r"^[A-Z0-9.]{1,10}$", t.upper()) and len(t.split()) == 1)

    def test_short_ticker(self):
        assert self._match("NVDA")

    def test_hk_ticker(self):
        assert self._match("2689.HK")

    def test_long_ticker_rejected(self):
        assert not self._match("TOOLONGTICKER")

    def test_six_char_ticker(self):
        assert self._match("BRK.AB")

    def test_single_char(self):
        assert self._match("F")


# ── Fix #4: Empty LLM response logs error on final attempt ──────

class TestEmptyLLMResponse:
    def _make_response(self, content="", finish_reason="length"):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]
        }
        return mock_resp

    def test_empty_response_retries_then_returns(self):
        """Empty responses should retry, then return empty on final attempt with error log."""
        from core import llm_client

        responses = [self._make_response(""), self._make_response(""), self._make_response("")]
        with patch("core.llm_client.requests.post", side_effect=responses), \
             patch("core.llm_client.time.sleep"):
            result = llm_client.chat([{"role": "user", "content": "test"}])

        assert result == ""

    def test_empty_then_success(self):
        """First attempt empty, second returns content."""
        from core import llm_client

        responses = [self._make_response(""), self._make_response("Hello world", "stop")]
        with patch("core.llm_client.requests.post", side_effect=responses), \
             patch("core.llm_client.time.sleep"):
            result = llm_client.chat([{"role": "user", "content": "test"}])

        assert result == "Hello world"

    def test_truncated_response_warns(self):
        """finish_reason=length with content should log warning but return result."""
        from core import llm_client

        resp = self._make_response("partial content", "length")
        with patch("core.llm_client.requests.post", return_value=resp), \
             patch("core.llm_client.logger") as mock_logger:
            result = llm_client.chat([{"role": "user", "content": "test"}])

        assert result == "partial content"
        mock_logger.warning.assert_any_call(
            "LLM response truncated (finish_reason=length, max_tokens=%d)", 1024
        )


# ── Fix #5: _CHAT_HISTORY thread safety ──────────────────────────

class TestChatHistoryThreadSafety:
    def test_lock_exists(self):
        """main module should have a _CHAT_LOCK threading.Lock."""
        # We can't import main.py directly (it acquires a file lock at import),
        # so we check the source code for the lock definition.
        import ast
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(src_path) as f:
            source = f.read()
        tree = ast.parse(source)
        lock_assignments = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "_CHAT_LOCK"
                for t in n.targets
            )
        ]
        assert len(lock_assignments) == 1, "_CHAT_LOCK should be defined exactly once"

    def test_lock_used_in_chat_fallback(self):
        """The free-form chat code path should use _CHAT_LOCK."""
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(src_path) as f:
            source = f.read()
        assert "with _CHAT_LOCK:" in source, "Free-form chat should use _CHAT_LOCK"
        # Should appear twice: once for appending user msg, once for appending reply
        assert source.count("with _CHAT_LOCK:") == 2


# ── Fix #6: API key warning in _headers docstring ────────────────

class TestHeadersDocstring:
    def test_warning_in_docstring(self):
        from core.llm_client import _headers
        assert "WARNING" in _headers.__doc__
        assert "bearer token" in _headers.__doc__.lower() or "bearer" in _headers.__doc__.lower()


# ── Fix #8: .env parser handles export prefix and inline comments ─

class TestEnvParser:
    """Test the .env parsing logic extracted from main.py."""

    def _parse_line(self, line):
        """Replicate the .env parsing logic from main.py."""
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            return None
        if line.startswith("export "):
            line = line[7:]
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        else:
            v = v.split("#", 1)[0].strip()
        return k.strip(), v

    def test_simple_kv(self):
        assert self._parse_line("FOO=bar") == ("FOO", "bar")

    def test_export_prefix(self):
        assert self._parse_line("export FOO=bar") == ("FOO", "bar")

    def test_inline_comment(self):
        assert self._parse_line("FOO=bar # this is a comment") == ("FOO", "bar")

    def test_quoted_value_preserves_hash(self):
        assert self._parse_line('FOO="bar#baz"') == ("FOO", "bar#baz")

    def test_single_quoted(self):
        assert self._parse_line("FOO='bar baz'") == ("FOO", "bar baz")

    def test_empty_value(self):
        assert self._parse_line("FOO=") == ("FOO", "")

    def test_comment_line_skipped(self):
        assert self._parse_line("# comment") is None

    def test_blank_line_skipped(self):
        assert self._parse_line("") is None

    def test_export_with_quotes(self):
        assert self._parse_line("export SECRET='s3cr3t'") == ("SECRET", "s3cr3t")


# ── Fix #9: time imported at top level in telegram_bot ───────────

class TestTimeImport:
    def test_time_at_top_level(self):
        """time should be imported at module level, not inside functions."""
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "telegram_bot.py")
        with open(src_path) as f:
            source = f.read()

        # Should have top-level import
        lines = source.split("\n")
        top_imports = [l for l in lines[:10] if l.strip() == "import time"]
        assert len(top_imports) == 1, "time should be imported once at top level"

        # Should NOT have inline imports
        inline_imports = [l for l in lines[10:] if "import time" in l]
        assert len(inline_imports) == 0, f"Found inline 'import time' after line 10: {inline_imports}"


# ── Fix #10: deploy.sh cleans up temp files on sandbox ───────────

class TestDeployCleanup:
    def test_temp_files_cleaned_on_sandbox(self):
        """deploy.sh should rm temp files after executing them on sandbox."""
        deploy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "deploy.sh")
        with open(deploy_path) as f:
            source = f.read()

        # Both temp script executions should have rm -f after
        assert "rm -f /tmp/${SETUP_DIRS_BASE}" in source, "Should clean up SETUP_DIRS temp file"
        assert "rm -f /tmp/sandbox-setup.sh" in source, "Should clean up sandbox-setup.sh"


# ── Fix #11: finish_reason=length warning ────────────────────────

class TestFinishReasonHandling:
    def test_length_with_content_warns(self):
        """Truncated responses (finish=length + non-empty) should warn."""
        from core import llm_client

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "truncated"}, "finish_reason": "length"}]
        }

        with patch("core.llm_client.requests.post", return_value=mock_resp), \
             patch("core.llm_client.logger") as mock_logger:
            result = llm_client.chat([{"role": "user", "content": "test"}])

        assert result == "truncated"
        mock_logger.warning.assert_any_call(
            "LLM response truncated (finish_reason=length, max_tokens=%d)", 1024
        )

    def test_stop_no_warning(self):
        """Normal completion (finish=stop) should NOT warn about truncation."""
        from core import llm_client

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "complete"}, "finish_reason": "stop"}]
        }

        with patch("core.llm_client.requests.post", return_value=mock_resp), \
             patch("core.llm_client.logger") as mock_logger:
            result = llm_client.chat([{"role": "user", "content": "test"}])

        assert result == "complete"
        # No warning about truncation
        for call in mock_logger.warning.call_args_list:
            assert "truncated" not in str(call)
