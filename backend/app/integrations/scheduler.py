"""Scheduled synchronization port.

No scheduler is started by the local Demo. Production may implement this port
with APScheduler/Airflow and an authorized data source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class SyncScheduler(ABC):
    @abstractmethod
    def start(self, sync_job: Callable[[], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class DemoSyncScheduler(SyncScheduler):
    """No-op scheduler to keep the local Demo deterministic and offline."""

    def start(self, sync_job: Callable[[], None]) -> None:
        return None

    def stop(self) -> None:
        return None


class APSchedulerSyncScheduler(SyncScheduler):
    """Production port for interval jobs; APScheduler is not imported in Demo."""

    def start(self, sync_job: Callable[[], None]) -> None:
        raise NotImplementedError("Production only: register an APScheduler job")

    def stop(self) -> None:
        raise NotImplementedError("Production only: stop the APScheduler scheduler")
