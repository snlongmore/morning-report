"""Tests for the BaseGatherer safe_gather timeout mechanism."""

import signal
import time

from morning_report.gatherers.base import BaseGatherer, _GATHERER_TIMEOUT


class _SlowGatherer(BaseGatherer):
    """Test gatherer that sleeps longer than the timeout."""

    @property
    def name(self) -> str:
        return "slow"

    def gather(self):
        time.sleep(_GATHERER_TIMEOUT + 10)
        return {"status": "ok"}


class _FastGatherer(BaseGatherer):
    """Test gatherer that returns immediately."""

    @property
    def name(self) -> str:
        return "fast"

    def gather(self):
        return {"value": 42}


class _FailGatherer(BaseGatherer):
    """Test gatherer that raises an exception."""

    @property
    def name(self) -> str:
        return "fail"

    def gather(self):
        raise ValueError("something broke")


class TestSafeGatherTimeout:
    def test_slow_gatherer_times_out(self, monkeypatch):
        monkeypatch.setattr("morning_report.gatherers.base._GATHERER_TIMEOUT", 1)
        result = _SlowGatherer().safe_gather()
        assert result["status"] == "error"
        assert "timed out" in result["error"]

    def test_fast_gatherer_succeeds(self):
        result = _FastGatherer().safe_gather()
        assert result["status"] == "ok"
        assert result["value"] == 42

    def test_failing_gatherer_returns_error(self):
        result = _FailGatherer().safe_gather()
        assert result["status"] == "error"
        assert "something broke" in result["error"]

    def test_signal_handler_restored_after_success(self):
        original = signal.getsignal(signal.SIGALRM)
        _FastGatherer().safe_gather()
        assert signal.getsignal(signal.SIGALRM) is original

    def test_signal_handler_restored_after_timeout(self, monkeypatch):
        monkeypatch.setattr("morning_report.gatherers.base._GATHERER_TIMEOUT", 1)
        original = signal.getsignal(signal.SIGALRM)
        _SlowGatherer().safe_gather()
        assert signal.getsignal(signal.SIGALRM) is original

    def test_signal_handler_restored_after_exception(self):
        original = signal.getsignal(signal.SIGALRM)
        _FailGatherer().safe_gather()
        assert signal.getsignal(signal.SIGALRM) is original
