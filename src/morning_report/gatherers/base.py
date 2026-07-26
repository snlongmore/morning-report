"""Base gatherer interface."""

from __future__ import annotations

import logging
import signal
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

_GATHERER_TIMEOUT = 60  # seconds — safety net per gatherer


class GathererTimeoutError(Exception):
    """Raised when a gatherer exceeds its time limit."""


class BaseGatherer(ABC):
    """Abstract base class for all data gatherers.

    Each gatherer collects data from a single source and returns
    a JSON-serialisable dictionary.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this gatherer (e.g. 'email', 'calendar')."""
        ...

    @abstractmethod
    def gather(self) -> dict[str, Any]:
        """Collect data from the source.

        Returns:
            Dictionary with gathered data. Must be JSON-serialisable.
            Should include a 'status' key ('ok' or 'error') and
            an 'error' key if status is 'error'.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this gatherer can run (dependencies met, config present).

        Override in subclasses that need specific setup. Default: True.
        """
        return True

    def safe_gather(self) -> dict[str, Any]:
        """Run gather() with error handling and timeout. Always returns a valid dict."""
        if not self.is_available():
            return {
                "status": "skipped",
                "reason": f"{self.name} gatherer is not available",
            }

        old_handler = signal.getsignal(signal.SIGALRM)

        def _timeout_handler(signum, frame):
            raise GathererTimeoutError(
                f"Gatherer '{self.name}' timed out after {_GATHERER_TIMEOUT}s"
            )

        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(_GATHERER_TIMEOUT)
            result = self.gather()
            signal.alarm(0)
            result.setdefault("status", "ok")
            return result
        except GathererTimeoutError as e:
            logger.error(str(e))
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.exception("Gatherer '%s' failed", self.name)
            return {
                "status": "error",
                "error": str(e),
            }
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
