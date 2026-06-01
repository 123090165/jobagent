from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.search import SearchResultItem, SearchResultSet
from app.services.search_providers.base import SearchProvider

MOCK_RETRIEVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class MockSearchProvider(SearchProvider):
    name = "mock"

    def search_jobs(self, query: str, limit: int = 5) -> SearchResultSet:
        items = [
            SearchResultItem(
                title="AI Agent Developer",
                company="Mock AI Labs",
                location="Remote",
                url="https://mock.example.com/jobs/ai-agent-developer",
                snippet=(
                    "Build agentic workflows with Python, FastAPI, and structured evaluation "
                    "for resume and JD analysis products."
                ),
                source=self.name,
                retrieved_at=MOCK_RETRIEVED_AT,
            ),
            SearchResultItem(
                title="Python Backend Engineer",
                company="Demo Hiring Platform",
                location="Shanghai",
                url="https://mock.example.com/jobs/python-backend-engineer",
                snippet=(
                    "Own backend services, APIs, database design, and testing for recruiting "
                    "and workflow automation products."
                ),
                source=self.name,
                retrieved_at=MOCK_RETRIEVED_AT,
            ),
            SearchResultItem(
                title="LLM Application Engineer",
                company="Prototype Studio",
                location="Beijing",
                url="https://mock.example.com/jobs/llm-application-engineer",
                snippet=(
                    "Ship LLM-powered product features with prompt engineering, guardrails, "
                    "fallback logic, and observability."
                ),
                source=self.name,
                retrieved_at=MOCK_RETRIEVED_AT,
            ),
        ]
        return SearchResultSet(
            query=query,
            provider=self.name,
            items=items[:limit],
        )
