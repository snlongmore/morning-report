"""Tests for curated French poetry loading and selection."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from morning_report.poems import load_poems, select_poem, _DEFAULT_POEMS_PATH


class TestLoadPoems:
    def test_loads_default_file(self):
        poems = load_poems()
        assert len(poems) >= 30

    def test_all_poems_have_required_keys(self):
        poems = load_poems()
        required = {"title", "author", "source", "excerpt"}
        for i, poem in enumerate(poems):
            missing = required - set(poem.keys())
            assert not missing, f"Poem {i} ({poem.get('title', '?')}) missing: {missing}"

    def test_all_excerpts_non_empty(self):
        poems = load_poems()
        for poem in poems:
            assert len(poem["excerpt"].strip()) > 0, f"Empty excerpt: {poem['title']}"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_poems(tmp_path / "nonexistent.json")

    def test_invalid_json_structure(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('{"not": "a list"}')
        with pytest.raises(ValueError, match="non-empty list"):
            load_poems(bad_file)

    def test_empty_list(self, tmp_path):
        bad_file = tmp_path / "empty.json"
        bad_file.write_text("[]")
        with pytest.raises(ValueError, match="non-empty list"):
            load_poems(bad_file)

    def test_missing_keys_raises(self, tmp_path):
        bad_file = tmp_path / "incomplete.json"
        bad_file.write_text(json.dumps([{"title": "Test"}]))
        with pytest.raises(ValueError, match="missing keys"):
            load_poems(bad_file)


class TestSelectPoem:
    def test_deterministic(self):
        poems = load_poems()
        date = datetime(2026, 3, 9)
        p1 = select_poem(date, poems)
        p2 = select_poem(date, poems)
        assert p1 == p2

    def test_consecutive_days_differ(self):
        poems = load_poems()
        p1 = select_poem(datetime(2026, 3, 9), poems)
        p2 = select_poem(datetime(2026, 3, 10), poems)
        assert p1 != p2

    def test_same_day_next_year_differs(self):
        poems = load_poems()
        p1 = select_poem(datetime(2026, 3, 9), poems)
        p2 = select_poem(datetime(2027, 3, 9), poems)
        # Different year shifts the index (unless len(poems) divides the year diff)
        # With 38 poems, year+1 shifts by 1 mod 38, so they should differ
        assert p1 != p2

    def test_returns_valid_poem(self):
        poems = load_poems()
        poem = select_poem(datetime(2026, 6, 15), poems)
        assert "title" in poem
        assert "author" in poem
        assert "excerpt" in poem
        assert "source" in poem

    def test_index_within_bounds(self):
        poems = load_poems()
        # Test a range of dates to ensure no index errors
        for day in range(1, 366):
            date = datetime(2026, 1, 1)
            from datetime import timedelta
            date = date + timedelta(days=day - 1)
            poem = select_poem(date, poems)
            assert poem in poems
