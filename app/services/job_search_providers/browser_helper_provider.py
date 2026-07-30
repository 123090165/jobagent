"""把浏览器扩展返回的候选包装为普通 Provider，使其复用后端分析流水线。"""

from __future__ import annotations

from app.services.job_search_providers.base import RawJobCandidate

BROWSER_HELPER_PROVIDER_PREFIX = "browser_helper"


class BrowserHelperPayloadProvider:
    """把浏览器助手payload接入统一 Provider 协议。"""
    provider_kind = "browser_helper"
    detail_strategy = "browser_helper_payload"

    def __init__(
        self,
        *,
        candidates: list[RawJobCandidate],
        platforms: list[str] | None = None,
        helper_version: str | None = None,
    ) -> None:
        self.candidates = candidates
        self.platforms = _clean_list(platforms or [])
        self.helper_version = (helper_version or "").strip() or None
        suffix = ",".join(self.platforms) if self.platforms else "manual"
        self.provider_name = f"{BROWSER_HELPER_PROVIDER_PREFIX}:{suffix}"
        self.source_names = self.platforms or [BROWSER_HELPER_PROVIDER_PREFIX]
        self._consumed = False

    def search_jobs(self, *, query: str, location: str | None, limit: int) -> list[RawJobCandidate]:
        if self._consumed:
            return []
        self._consumed = True
        normalized: list[RawJobCandidate] = []
        for index, candidate in enumerate(self.candidates[: max(1, limit)], start=1):
            warnings = [
                "Fetched via JobAgent Browser Helper; platform cookies were not sent to backend.",
                *candidate.provider_warnings,
            ]
            normalized.append(
                candidate.model_copy(
                    update={
                        "discovery_query": candidate.discovery_query or query,
                        "discovery_rank": candidate.discovery_rank or index,
                        "detail_status": candidate.detail_status or "browser_helper_payload",
                        "provider_warnings": _clean_list(warnings),
                    }
                )
            )
        return normalized


def _clean_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
