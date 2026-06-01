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
                responsibilities=[
                    "Design agentic workflow services for job search and analysis flows.",
                    "Build backend APIs for resume parsing, JD analysis, and reporting.",
                ],
                requirements=[
                    "Strong Python backend engineering experience.",
                    "Experience with API design, testing, and structured data models.",
                ],
                skills=["Python", "FastAPI", "Pydantic", "LLM"],
                jd_text=(
                    "Title: AI Agent Developer\n"
                    "Company: Mock AI Labs\n"
                    "Location: Remote\n"
                    "Responsibilities:\n"
                    "- Design agentic workflow services for job search and analysis flows.\n"
                    "- Build backend APIs for resume parsing, JD analysis, and reporting.\n"
                    "Requirements:\n"
                    "- Strong Python backend engineering experience.\n"
                    "- Experience with API design, testing, and structured data models.\n"
                    "Skills: Python, FastAPI, Pydantic, LLM\n"
                    "Source URL: https://mock.example.com/jobs/ai-agent-developer"
                ),
                is_full_jd=True,
                confidence=0.94,
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
                responsibilities=[
                    "Own backend services for recruiting workflows.",
                    "Maintain APIs, data models, and integration tests.",
                ],
                requirements=[
                    "Production Python backend experience.",
                    "Experience with SQL databases and API observability.",
                ],
                skills=["Python", "SQL", "REST API", "Testing"],
                jd_text=(
                    "Title: Python Backend Engineer\n"
                    "Company: Demo Hiring Platform\n"
                    "Location: Shanghai\n"
                    "Responsibilities:\n"
                    "- Own backend services for recruiting workflows.\n"
                    "- Maintain APIs, data models, and integration tests.\n"
                    "Requirements:\n"
                    "- Production Python backend experience.\n"
                    "- Experience with SQL databases and API observability.\n"
                    "Skills: Python, SQL, REST API, Testing\n"
                    "Source URL: https://mock.example.com/jobs/python-backend-engineer"
                ),
                is_full_jd=True,
                confidence=0.91,
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
                responsibilities=[
                    "Ship LLM-powered product features and prompt flows.",
                    "Design guardrails, fallback logic, and runtime observability.",
                ],
                requirements=[
                    "Experience building LLM application features in production or prototypes.",
                    "Comfort with evaluation, prompt iteration, and API integration.",
                ],
                skills=["LLM", "Prompt Engineering", "Python", "Observability"],
                jd_text=(
                    "Title: LLM Application Engineer\n"
                    "Company: Prototype Studio\n"
                    "Location: Beijing\n"
                    "Responsibilities:\n"
                    "- Ship LLM-powered product features and prompt flows.\n"
                    "- Design guardrails, fallback logic, and runtime observability.\n"
                    "Requirements:\n"
                    "- Experience building LLM application features in production or prototypes.\n"
                    "- Comfort with evaluation, prompt iteration, and API integration.\n"
                    "Skills: LLM, Prompt Engineering, Python, Observability\n"
                    "Source URL: https://mock.example.com/jobs/llm-application-engineer"
                ),
                is_full_jd=True,
                confidence=0.9,
                source=self.name,
                retrieved_at=MOCK_RETRIEVED_AT,
            ),
        ]
        return SearchResultSet(
            query=query,
            provider=self.name,
            items=items[:limit],
        )
