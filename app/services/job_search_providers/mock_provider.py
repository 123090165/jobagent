from __future__ import annotations

from app.services.job_search_providers.base import RawJobCandidate


class MockJobSearchProvider:
    provider_name = "mock"
    provider_kind = "mock"

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        base_location = location or "Remote"
        catalog = [
            {
                "title": "Backend Engineer",
                "company": "Maple Stack",
                "snippet": "Python FastAPI APIs, SQL services, backend workflows, and developer tooling.",
            },
            {
                "title": "AI Application Engineer",
                "company": "Northstar Agents",
                "snippet": "LLM application delivery, prompt tooling, retrieval, and agent workflow testing.",
            },
            {
                "title": "Data Engineer",
                "company": "Riverlane Metrics",
                "snippet": "Python ETL, analytics datasets, warehouse modeling, and SQL quality checks.",
            },
            {
                "title": "Full Stack Developer",
                "company": "Cedar Product Studio",
                "snippet": "Vue, TypeScript, Python APIs, and customer-facing product iteration.",
            },
            {
                "title": "Platform Engineer",
                "company": "Granite Cloud",
                "snippet": "CI pipelines, Docker workflows, internal platform reliability, and automation.",
            },
        ]
        items: list[RawJobCandidate] = []
        for index, item in enumerate(catalog[: max(1, limit)]):
            title = item["title"]
            company = item["company"]
            snippet = f"{item['snippet']} Search query context: {query}."
            items.append(
                RawJobCandidate(
                    title=title,
                    company=company,
                    location=base_location if index % 2 == 0 else "Remote",
                    source_url=f"https://example.com/jobs/{company.lower().replace(' ', '-')}/{title.lower().replace(' ', '-')}",
                    source_provider=self.provider_name,
                    snippet=snippet,
                    raw_description=snippet,
                    discovery_query=query,
                    discovery_rank=index + 1,
                    detail_status="mock_inline",
                )
            )
        return items
