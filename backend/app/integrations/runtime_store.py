"""Runtime persistence ports.

The Demo uses the JSON implementation. Production can provide a MySQL-backed
implementation without changing the service or HTTP contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RuntimeStore(ABC):
    @abstractmethod
    def load_feedback(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def append_feedback(self, sample: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_training_snapshots(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def append_training_snapshot(self, snapshot: dict[str, Any]) -> None:
        raise NotImplementedError


class JsonRuntimeStore(RuntimeStore):
    """Local JSON persistence used by the standalone Demo."""

    def load_feedback(self) -> list[dict[str, Any]]:
        from ..data import load_feedback
        return load_feedback()

    def append_feedback(self, sample: dict[str, Any]) -> None:
        from ..data import append_feedback
        append_feedback(sample)

    def load_training_snapshots(self) -> list[dict[str, Any]]:
        from ..data import load_training_snapshots
        return load_training_snapshots()

    def append_training_snapshot(self, snapshot: dict[str, Any]) -> None:
        from ..data import append_training_snapshot
        append_training_snapshot(snapshot)


class MySQLRuntimeStore(RuntimeStore):
    """Production port; database implementation is intentionally out of Demo scope."""

    def load_feedback(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Production only: query the MySQL feedback table")

    def append_feedback(self, sample: dict[str, Any]) -> None:
        raise NotImplementedError("Production only: insert the MySQL feedback event")

    def load_training_snapshots(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Production only: query the MySQL snapshot table")

    def append_training_snapshot(self, snapshot: dict[str, Any]) -> None:
        raise NotImplementedError("Production only: insert the MySQL snapshot record")
