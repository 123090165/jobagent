"""把浏览器扩展提取的职位页转换为标准候选和可追踪的分析报告。"""

from __future__ import annotations

from app.schemas.job_search import (
    BROWSER_CAPTURE_PREVIEW_LENGTH,
    BrowserJobCaptureReport,
    BrowserJobCaptureRequest,
    BrowserJobCaptureSummary,
    BrowserHelperJobCandidate,
    JobSearchResult,
    JobSearchTraceStep,
)
from app.services.job_search_providers.base import RawJobCandidate


def browser_job_capture_to_candidate(payload: BrowserJobCaptureRequest) -> BrowserHelperJobCandidate:
    warnings = _browser_capture_warnings(payload)
    title = payload.title or payload.page_title or "Untitled captured role"
    snippet = payload.jd_text[:BROWSER_CAPTURE_PREVIEW_LENGTH]
    source_provider = f"browser_capture_{payload.source}"
    return BrowserHelperJobCandidate(
        title=title,
        company=payload.company,
        location=payload.location,
        source_url=payload.source_url,
        source_provider=source_provider,
        snippet=snippet,
        raw_description=payload.jd_text,
        discovery_query=title,
        discovery_rank=1,
        detail_status="browser_job_capture_payload",
        provider_warnings=warnings,
    )


def _browser_helper_candidate_to_raw(candidate: BrowserHelperJobCandidate) -> RawJobCandidate:
    source_provider = candidate.source_provider.strip() or "browser_helper"
    warnings = [
        *candidate.provider_warnings,
        "Candidate came from browser helper payload; platform cookies are not stored by backend.",
    ]
    return RawJobCandidate(
        title=candidate.title.strip(),
        company=(candidate.company or "").strip() or None,
        location=(candidate.location or "").strip() or None,
        source_url=(candidate.source_url or "").strip() or None,
        source_provider=source_provider,
        snippet=candidate.snippet.strip(),
        raw_description=(candidate.raw_description or "").strip() or candidate.snippet.strip(),
        discovery_query=(candidate.discovery_query or "").strip() or None,
        discovery_rank=candidate.discovery_rank,
        detail_status=(candidate.detail_status or "").strip() or "browser_helper_payload",
        provider_warnings=_clean_list(warnings),
    )


def _capture_summary(payload: BrowserJobCaptureRequest) -> BrowserJobCaptureSummary:
    return BrowserJobCaptureSummary(
        source=payload.source,
        source_url=payload.source_url,
        page_title=payload.page_title,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        salary=payload.salary,
        jd_text_preview=payload.jd_text[:BROWSER_CAPTURE_PREVIEW_LENGTH],
        captured_at=payload.captured_at,
        extractor_version=payload.extractor_version,
    )


def _browser_capture_report(result: JobSearchResult) -> BrowserJobCaptureReport:
    return BrowserJobCaptureReport(
        overall_score=result.match_score,
        recommendation=result.recommended_action,
        matched_strengths=_clean_list(result.match_reasons + result.matched_keywords),
        critical_gaps=result.risks,
        resume_actions=[result.recommended_action] if result.recommended_action else [],
        interview_questions=[],
        confidence_label=result.confidence_label,
        analysis_mode=result.analysis_mode,
    )


def _browser_capture_warnings(payload: BrowserJobCaptureRequest) -> list[str]:
    warnings = list(payload.warnings)
    if payload.title is None:
        warnings.append("Job title was not confidently extracted from the browser page.")
    if payload.company is None:
        warnings.append("Company was not confidently extracted from the browser page.")
    if payload.location is None:
        warnings.append("Location was not confidently extracted from the browser page.")
    warnings.append(f"Browser capture page title: {payload.page_title}")
    warnings.append(f"Browser capture extractor version: {payload.extractor_version}")
    warnings.append(f"Browser capture captured_at: {payload.captured_at.isoformat()}")
    return _clean_list(warnings)


def _trace_quality_warnings(steps: list[JobSearchTraceStep]) -> list[str]:
    warnings: list[str] = []
    for step in steps:
        warnings.extend(step.quality_warnings)
        if step.status == "failed" and step.summary:
            warnings.append(step.summary)
    return _clean_list(warnings)


def _clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
