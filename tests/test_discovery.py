"""Tests for skill auto-discovery and command routing."""

import os
import re
import sys
import tempfile
import threading
from unittest.mock import MagicMock, patch
from types import ModuleType

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py has module-level side effects (lock file, /sandbox dirs, logging).
# Set env vars and mock before importing so it can load in a test environment.
_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("NEMOCLAW_LOG_DIR", _tmpdir)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

# Remove stale lock file so main.py can acquire it
_lock_path = "/tmp/nemoclaw.lock"
try:
    os.remove(_lock_path)
except FileNotFoundError:
    pass

import main  # noqa: E402 — must come after env setup


# ── Discovery ────────────────────────────────────────────────────────

class TestDiscovery:
    """Verify _discover_skills finds all skill modules and their metadata."""

    def setup_method(self):
        main._COMMANDS = None
        main._SCHEDULES = None

    def test_discovers_all_commands(self):
        main._ensure_discovered()
        assert len(main._COMMANDS) >= 15
        patterns = [cmd["pattern"] for cmd, _ in main._COMMANDS]
        assert "watchlist" in patterns
        assert "news" in patterns
        assert "geo" in patterns
        assert "earnings" in patterns

    def test_discovers_schedules(self):
        main._ensure_discovered()
        assert len(main._SCHEDULES) >= 4
        funcs = [s["func"] for s, _ in main._SCHEDULES]
        assert "run_news_cycle" in funcs
        assert "run_geo_scan" in funcs
        assert "send_morning_brief" in funcs
        assert "send_weekly_summary" in funcs

    def test_exact_before_prefix_before_regex(self):
        main._ensure_discovered()
        types_in_order = [cmd["type"] for cmd, _ in main._COMMANDS]
        first_prefix = next((i for i, t in enumerate(types_in_order) if t == "prefix"), None)
        first_regex = next((i for i, t in enumerate(types_in_order) if t == "regex"), None)
        last_exact = max(i for i, t in enumerate(types_in_order) if t == "exact")
        if first_prefix is not None:
            assert last_exact < first_prefix
        if first_regex is not None and first_prefix is not None:
            assert first_prefix < first_regex

    def test_priority_within_regex(self):
        """Lower priority number should come first within regex type."""
        main._ensure_discovered()
        regex_cmds = [(cmd, mod) for cmd, mod in main._COMMANDS if cmd["type"] == "regex"]
        priorities = [cmd.get("priority", 50) for cmd, _ in regex_cmds]
        assert priorities == sorted(priorities)

    def test_startup_schedule_exists(self):
        main._ensure_discovered()
        startup = [s for s, _ in main._SCHEDULES if s.get("run_at_startup")]
        assert len(startup) >= 1
        assert startup[0]["func"] == "run_news_cycle"


# ── Command routing ──────────────────────────────────────────────────

class TestTryCommand:
    """Verify _try_command matches correctly for each type."""

    def setup_method(self):
        self.mock_mod = ModuleType("skills.fake")
        self.mock_mod.do_thing = MagicMock(return_value="result")
        self.mock_mod.threaded_thing = MagicMock(return_value="threaded result")

    def test_exact_match(self):
        cmd = {"type": "exact", "pattern": "watchlist", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "watchlist", "watchlist")
        assert result == "result"
        self.mock_mod.do_thing.assert_called_once_with()

    def test_exact_no_match(self):
        cmd = {"type": "exact", "pattern": "watchlist", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "watchlis", "watchlis")
        assert result is None
        self.mock_mod.do_thing.assert_not_called()

    def test_exact_case_insensitive(self):
        cmd = {"type": "exact", "pattern": "watchlist", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "Watchlist", "watchlist")
        assert result == "result"

    def test_prefix_match(self):
        cmd = {"type": "prefix", "pattern": "news ", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "news AI chips", "news ai chips")
        assert result == "result"
        self.mock_mod.do_thing.assert_called_once_with("AI chips")

    def test_prefix_no_match(self):
        cmd = {"type": "prefix", "pattern": "news ", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "earnings", "earnings")
        assert result is None

    def test_regex_upper(self):
        cmd = {"type": "regex", "pattern": r"(?i)research\s+(\w[\w.]+)",
               "call": "do_thing", "args": "upper"}
        result = main._try_command(cmd, self.mock_mod, "research nvda", "research nvda")
        assert result == "result"
        self.mock_mod.do_thing.assert_called_once_with("NVDA")

    def test_regex_raw(self):
        cmd = {"type": "regex", "pattern": r"(?i)any\s+news\s+on\s+(.+?)\??$",
               "call": "do_thing", "args": "raw"}
        result = main._try_command(cmd, self.mock_mod, "any news on chip shortage?",
                                     "any news on chip shortage?")
        assert result == "result"
        self.mock_mod.do_thing.assert_called_once_with("chip shortage")

    def test_regex_no_match(self):
        cmd = {"type": "regex", "pattern": r"(?i)research\s+(\w[\w.]+)",
               "call": "do_thing", "args": "upper"}
        result = main._try_command(cmd, self.mock_mod, "hello", "hello")
        assert result is None

    def test_threaded_command(self):
        cmd = {"type": "exact", "pattern": "brief", "call": "threaded_thing",
               "thread": True, "ack": "Working..."}
        with patch.object(threading.Thread, "start"):
            result = main._try_command(cmd, self.mock_mod, "brief", "brief")
        assert result == "Working..."

    def test_unknown_type_returns_none(self):
        cmd = {"type": "unknown", "pattern": "x", "call": "do_thing"}
        result = main._try_command(cmd, self.mock_mod, "x", "x")
        assert result is None


# ── Help text ────────────────────────────────────────────────────────

class TestHelpText:
    """Verify help text assembly and ordering."""

    def setup_method(self):
        main._COMMANDS = None
        main._SCHEDULES = None

    def test_help_contains_all_sections(self):
        text = main._help_text()
        assert "*Prices*" in text
        assert "*Portfolio*" in text
        assert "*News*" in text
        assert "*Geopolitics*" in text
        assert "*Earnings*" in text
        assert "*Research*" in text
        assert "*Briefs*" in text
        assert "*System*" in text

    def test_help_ordering(self):
        """Sections should appear in HELP_ORDER sequence."""
        text = main._help_text()
        briefs_pos = text.index("*Briefs*")
        prices_pos = text.index("*Prices*")
        geo_pos = text.index("*Geopolitics*")
        news_pos = text.index("*News*")
        earnings_pos = text.index("*Earnings*")
        research_pos = text.index("*Research*")
        portfolio_pos = text.index("*Portfolio*")
        system_pos = text.index("*System*")
        assert briefs_pos < prices_pos < geo_pos < news_pos < earnings_pos < research_pos < portfolio_pos < system_pos
