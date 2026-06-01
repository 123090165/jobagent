from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.search import SearchResultSet


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search_jobs(self, query: str, limit: int = 5) -> SearchResultSet:
        raise NotImplementedError
