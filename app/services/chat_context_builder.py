from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.repositories.chat_repository import ChatRepository, chat_repository
from app.repositories.browser_job_capture_repository import (
    BrowserJobCaptureRepository,
    browser_job_capture_repository,
)
from app.repositories.job_search_repository import JobSearchRepository, job_search_repository
from app.repositories.resume_profile_repository import ResumeProfileRepository, resume_profile_repository
from app.repositories.saved_job_repository import SavedJobRepository, saved_job_repository
from app.schemas.chat import ChatCitation, ChatConversation, ChatSource
from app.services.chat_intent_rules import requests_highest_saved_job_score


MAX_EVIDENCE_RESOURCES = 12
MAX_EVIDENCE_CHARS = 24_000


@dataclass(frozen=True)
class ChatEvidence:
    citation: ChatCitation
    content: dict[str, object]


def build_chat_evidence(
    question: str,
    *,
    user_id: str,
    conversation: ChatConversation,
    requested_sources: list[ChatSource],
    active_refs: list[str] | None = None,
    profiles: ResumeProfileRepository = resume_profile_repository,
    searches: JobSearchRepository = job_search_repository,
    saved_jobs: SavedJobRepository = saved_job_repository,
    chats: ChatRepository = chat_repository,
    captures: BrowserJobCaptureRepository = browser_job_capture_repository,
) -> tuple[list[ChatEvidence], list[str]]:
    evidence: list[ChatEvidence] = []
    warnings: list[str] = []
    scope = conversation.data_scope
    active_refs = active_refs or []

    if "profile" in requested_sources:
        active_profile_ids = [item.removeprefix("profile:") for item in active_refs if item.startswith("profile:")]
        profile_id = active_profile_ids[0] if active_profile_ids else scope.resume_profile_id
        profile = (
            profiles.get(user_id=user_id, resume_profile_id=profile_id)
            if profile_id
            else next(iter(profiles.list_by_user(user_id)), None)
        )
        if profile is None:
            warnings.append("No accessible resume profile was available.")
        else:
            evidence.append(ChatEvidence(
                citation=ChatCitation(
                    citation_id=f"profile:{profile.resume_profile_id}",
                    source_type="profile",
                    resource_id=profile.resume_profile_id,
                    label=profile.name,
                    excerpt=profile.summary[:300],
                    href="/resume-profiles",
                ),
                content={
                    "name": profile.name,
                    "summary": profile.summary,
                    "target_roles": profile.target_roles,
                    "target_directions": profile.target_directions,
                    "core_skills": profile.core_skills,
                    "supporting_skills": profile.supporting_skills,
                    "preferred_locations": profile.preferred_locations,
                    "work_arrangements": profile.work_arrangements,
                    "strengths": profile.strengths,
                    "risks": profile.risks,
                },
            ))

    if "saved_jobs" in requested_sources:
        active_saved_job_ids = [
            item.removeprefix("saved_job:") for item in active_refs if item.startswith("saved_job:")
        ]
        if requests_highest_saved_job_score(question):
            selected_saved_job_ids = active_saved_job_ids
        else:
            selected_saved_job_ids = list(dict.fromkeys([
                *active_saved_job_ids,
                *scope.saved_job_ids,
            ]))
        if selected_saved_job_ids:
            candidates = [
                item for saved_job_id in selected_saved_job_ids
                if (item := saved_jobs.get(user_id=user_id, saved_job_id=saved_job_id)) is not None
            ]
        else:
            candidates = saved_jobs.list_by_user(user_id)
        for job in _select_saved_jobs(question, candidates):
            analysis = job.latest_analysis
            evidence.append(ChatEvidence(
                citation=ChatCitation(
                    citation_id=f"saved_job:{job.saved_job_id}",
                    source_type="saved_jobs",
                    resource_id=job.saved_job_id,
                    label=f"{job.title} · {job.company or 'Unknown company'}",
                    excerpt=_saved_job_excerpt(job)[:300],
                    href=f"/saved-jobs/{job.saved_job_id}",
                ),
                content={
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "status": job.status,
                    "tags": job.tags,
                    "notes": job.notes,
                    "jd_excerpt": job.raw_jd_text[:1400],
                    "match_score": analysis.match_score if analysis else None,
                    "recommendation": analysis.recommendation if analysis else None,
                    "matched_strengths": analysis.matched_strengths if analysis else [],
                    "critical_gaps": analysis.critical_gaps if analysis else [],
                },
            ))

    if "search_results" in requested_sources:
        active_search_refs = [item.split(":", 2) for item in active_refs if item.startswith("search_result:")]
        active_capture_ids = list(dict.fromkeys([
            *scope.browser_capture_ids,
            *(
            item[2] for item in active_search_refs
            if len(item) == 3 and item[1] == "browser_capture"
            ),
        ]))
        for capture_id in active_capture_ids:
            capture = captures.get(user_id=user_id, capture_id=capture_id)
            if capture is None:
                warnings.append("An attached browser JD capture is no longer available.")
                continue
            evidence.append(ChatEvidence(
                citation=ChatCitation(
                    citation_id=f"search_result:browser_capture:{capture.capture_id}",
                    source_type="search_results",
                    resource_id=capture.capture_id,
                    label=f"{capture.title or capture.page_title} 路 {capture.company or 'Unknown company'}",
                    excerpt=capture.jd_text[:300],
                    href=capture.source_url,
                ),
                content={
                    "source": "browser_capture",
                    "title": capture.title or capture.page_title,
                    "company": capture.company,
                    "location": capture.location,
                    "salary": capture.salary,
                    "source_url": capture.source_url,
                    "jd_text": capture.jd_text[:12_000],
                },
            ))
        active_search_refs = [
            item for item in active_search_refs
            if len(item) == 3 and item[1] != "browser_capture"
        ]
        active_run_ids = list(dict.fromkeys(item[1] for item in active_search_refs))
        active_result_ids_by_run: dict[str, set[str]] = {}
        for item in active_search_refs:
            if len(item) == 3:
                active_result_ids_by_run.setdefault(item[1], set()).add(item[2])
        scoped_run_ids = list(dict.fromkeys(
            ref.job_search_run_id for ref in scope.job_search_result_refs
        ))
        scoped_result_ids_by_run: dict[str, set[str]] = {}
        for ref in scope.job_search_result_refs:
            scoped_result_ids_by_run.setdefault(ref.job_search_run_id, set()).add(ref.job_result_id)
        selected_result_ids_by_run = active_result_ids_by_run or scoped_result_ids_by_run
        selected_run_ids = active_run_ids or list(dict.fromkeys([
            *scoped_run_ids,
            *scope.job_search_run_ids,
        ]))
        if selected_run_ids:
            runs = [
                item for run_id in selected_run_ids
                if (item := searches.get(run_id, user_id=user_id)) is not None
            ]
        elif active_capture_ids:
            runs = []
        else:
            runs = [item for item in searches.list_recent_by_user(user_id, limit=5) if item.status == "completed"]
        candidates = [
            (run, result) for run in runs for result in run.results
            if run.job_search_run_id not in selected_result_ids_by_run
            or result.job_result_id in selected_result_ids_by_run[run.job_search_run_id]
        ]
        for run, result in _rank(question, candidates, lambda item: _search_result_text(item[1]))[:6]:
            evidence.append(ChatEvidence(
                citation=ChatCitation(
                    citation_id=f"search_result:{run.job_search_run_id}:{result.job_result_id}",
                    source_type="search_results",
                    resource_id=result.job_result_id,
                    label=f"{result.title} · {result.company}",
                    excerpt=(result.match_reasons[0] if result.match_reasons else result.description)[:300],
                    href=f"/jobs/{run.job_search_run_id}",
                ),
                content={
                    "run_id": run.job_search_run_id,
                    "query": run.query,
                    "title": result.title,
                    "company": result.company,
                    "location": result.location,
                    "description_excerpt": result.description[:1400],
                    "match_score": result.match_score,
                    "final_match_score": getattr(result, "final_match_score", None),
                    "match_reasons": result.match_reasons,
                    "risks": result.risks,
                    "evidence_quotes": result.evidence_quotes,
                    "unknowns": getattr(result, "unknowns", []),
                    "recommended_action": result.recommended_action,
                },
            ))

    if "chat_history" in requested_sources:
        active_turn_ids = {item.removeprefix("chat_turn:") for item in active_refs if item.startswith("chat_turn:")}
        turns = [item for item in chats.list_turns(
            user_id=user_id, conversation_id=conversation.conversation_id, limit=30
        ) if item.status == "completed" and (not active_turn_ids or item.turn_id in active_turn_ids)]
        history_candidates = turns if active_turn_ids else turns[:-4]
        for turn in _rank(question, history_candidates, lambda item: f"{item.question} {item.answer or ''}")[:3]:
            evidence.append(ChatEvidence(
                citation=ChatCitation(
                    citation_id=f"chat_turn:{turn.turn_id}",
                    source_type="chat_history",
                    resource_id=turn.turn_id,
                    label=f"Conversation turn {turn.sequence}",
                    excerpt=(turn.answer or turn.question)[:300],
                ),
                content={"question": turn.question, "answer": (turn.answer or "")[:1200]},
            ))

    return apply_evidence_budget(evidence), warnings


def evidence_packet(evidence: list[ChatEvidence]) -> list[dict[str, object]]:
    return [
        {"citation_id": item.citation.citation_id, "source_type": item.citation.source_type, "content": item.content}
        for item in evidence
    ]


def apply_evidence_budget(items: list[ChatEvidence]) -> list[ChatEvidence]:
    selected: list[ChatEvidence] = []
    chars = 0
    for item in items[:MAX_EVIDENCE_RESOURCES]:
        size = len(json.dumps(item.content, ensure_ascii=False))
        if selected and chars + size > MAX_EVIDENCE_CHARS:
            break
        selected.append(item)
        chars += size
    return selected


def _rank(question: str, items: list, text_builder) -> list:
    terms = _terms(question)
    scored = []
    for index, item in enumerate(items):
        text = text_builder(item).casefold()
        score = sum(1 for term in terms if term in text)
        scored.append((score, -index, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in scored]


def _select_saved_jobs(question: str, candidates: list) -> list:
    if requests_highest_saved_job_score(question):
        scored = [
            item for item in candidates
            if item.latest_analysis is not None and item.latest_analysis.match_score is not None
        ]
        if scored:
            return [max(scored, key=lambda item: item.latest_analysis.match_score)]
    return _rank(question, candidates, _saved_job_text)[:6]


def _saved_job_excerpt(job) -> str:
    analysis = job.latest_analysis
    if analysis is None:
        return job.raw_jd_text
    parts = []
    if analysis.match_score is not None:
        parts.append(f"Match score: {analysis.match_score}/100.")
    if analysis.recommendation:
        parts.append(analysis.recommendation)
    return " ".join(parts) or job.raw_jd_text


def _terms(value: str) -> set[str]:
    normalized = value.casefold()
    words = set(re.findall(r"[a-z0-9+#.]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    words.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in words if item}


def _saved_job_text(job) -> str:
    analysis = job.latest_analysis
    return " ".join(filter(None, [job.title, job.company, job.location, job.raw_jd_text,
        analysis.recommendation if analysis else None]))


def _search_result_text(result) -> str:
    return " ".join([result.title, result.company, result.location, result.description,
        *result.match_reasons, *result.risks, *result.matched_keywords])
