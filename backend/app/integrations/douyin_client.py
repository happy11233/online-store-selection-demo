"""Production API port, intentionally not called by the local Demo.

The concrete client documents the boundary needed for a licensed精选联盟
integration. Credentials, endpoint signing, rate limits and field mapping stay
outside the AI modules. Keeping this port makes a production adapter replaceable
without changing FastAPI or the React contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CommerceDataSource(ABC):
    @abstractmethod
    def fetch_products(self, cursor: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_hotspots(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockCommerceDataSource(CommerceDataSource):
    """The only data source enabled by this repository."""

    def fetch_products(self, cursor: str | None = None) -> list[dict[str, Any]]:
        from ..data import load_mock_products
        return load_mock_products()

    def fetch_hotspots(self) -> list[dict[str, Any]]:
        from ..data import load_mock_hotspots
        return load_mock_hotspots()


class LicensedDouyinAllianceClient(CommerceDataSource):
    """Interface placeholder for an authorized production connector.

    No network request is implemented or invoked in Demo. A production backend
    should implement the two methods with the approved platform SDK/API, token
    rotation, request signing, pagination and audit logging.
    """

    def fetch_products(self, cursor: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Production only: connect through an approved精选联盟 API adapter")

    def fetch_hotspots(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Production only: connect through an approved热点数据 API adapter")
