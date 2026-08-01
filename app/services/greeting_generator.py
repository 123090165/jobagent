from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.schemas.job_search import BrowserJobCaptureRecord
from app.schemas.resume_profile import ResumeProfile
from app.services.llm_provider import JSONChatLLM


MAX_GREETING_ATTEMPTS = 2


class GreetingGeneration(BaseModel):
    content: str = Field(min_length=1)
    evidence_used: list[str] = Field(default_factory=list)
    avoid_claims: list[str] = Field(default_factory=list)


class GreetingReview(BaseModel):
    approved: bool
    naturalness: int = Field(ge=1, le=10)
    relevance: int = Field(ge=1, le=10)
    differentiation: int = Field(ge=1, le=10)
    issues: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class GreetingGenerationFailure(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def generate_initial_greeting(
    capture: BrowserJobCaptureRecord,
    profile: ResumeProfile,
    *,
    llm_service: JSONChatLLM,
) -> GreetingGeneration:
    """生成并复核沟通词；任何环节失败都不保存未完成草稿。"""
    source = _candidate_source(profile)
    base_prompt = _generation_prompt(capture, profile)
    prompt = base_prompt

    for attempt in range(MAX_GREETING_ATTEMPTS):
        try:
            response = llm_service.chat_completion_json(
                system_prompt=_generation_system_prompt(),
                user_prompt=prompt,
            )
            generation = _clean_generation(GreetingGeneration.model_validate(response))
        except Exception as exc:
            raise GreetingGenerationFailure(
                "generation_failed",
                "Greeting generation failed. Check the model configuration and try again.",
            ) from exc

        hard_issues = _hard_issues(generation, source, capture)
        review: GreetingReview | None = None
        if not hard_issues:
            try:
                review = GreetingReview.model_validate(
                    llm_service.chat_completion_json(
                        system_prompt=_review_system_prompt(),
                        user_prompt=json.dumps(
                            {
                                "job_title": capture.title,
                                "company": capture.company,
                                "job_description": capture.jd_text[:3000],
                                "greeting": generation.content,
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
            except Exception as exc:
                raise GreetingGenerationFailure(
                    "generation_failed",
                    "Greeting quality review failed. Please try again.",
                ) from exc

        review_issues = [] if review is None else review.issues
        review_passed = review is not None and review.approved and _review_average(review) >= 7
        if not hard_issues and review_passed:
            return generation

        issues = list(dict.fromkeys([*hard_issues, *review_issues]))
        if review is not None and not review_passed and not issues:
            issues.append("The greeting did not meet the required quality score.")
        if attempt == 0:
            prompt = _correction_prompt(base_prompt, generation.content, issues)
            continue
        raise GreetingGenerationFailure(
            "generation_validation_failed",
            "The greeting did not pass review after one correction: " + "; ".join(issues[:6]),
        )

    raise AssertionError("unreachable")


def _generation_system_prompt() -> str:
    return (
        "为用户生成一条招聘平台首次沟通的中文短消息。只使用输入中明确提供的候选人事实，不得虚构公司、"
        "年限、成绩、部署经验或项目结果，不得把 JD 写成候选人经历。内容自然、具体，突出一到两个匹配点，"
        "避免群发模板口吻，控制在 50 到 150 个中文字符。返回 JSON，且只包含 content、evidence_used、avoid_claims。"
    )


def _review_system_prompt() -> str:
    return (
        "复核一条招聘平台首次沟通词。分别从自然度、岗位相关性、差异化按 1 到 10 分评分。"
        "只有事实安全、表达自然、岗位相关且不是明显群发模板时 approved 才为 true。"
        "返回 JSON：approved、naturalness、relevance、differentiation、issues。"
    )


def _generation_prompt(capture: BrowserJobCaptureRecord, profile: ResumeProfile) -> str:
    return json.dumps(
        {
            "job": {
                "title": capture.title,
                "company": capture.company,
                "salary": capture.salary,
                "description": capture.jd_text[:4000],
            },
            "candidate": {
                "summary": profile.summary,
                "core_skills": profile.core_skills,
                "supporting_skills": profile.supporting_skills,
                "strengths": profile.strengths,
                "risks": profile.risks,
                "source_resume": profile.raw_resume_text,
            },
        },
        ensure_ascii=False,
    )


def _correction_prompt(base_prompt: str, previous: str, issues: list[str]) -> str:
    return (
        base_prompt
        + "\n\n上一次沟通词："
        + previous
        + "\n检查问题：\n- "
        + "\n- ".join(issues[:8])
        + "\n请只纠正这些问题并重新返回完整 JSON。"
    )


def _clean_generation(generation: GreetingGeneration) -> GreetingGeneration:
    return generation.model_copy(
        update={
            "content": generation.content.strip(),
            "evidence_used": list(
                dict.fromkeys(item.strip() for item in generation.evidence_used if item.strip())
            )[:5],
            "avoid_claims": list(
                dict.fromkeys(item.strip() for item in generation.avoid_claims if item.strip())
            )[:5],
        }
    )


def _hard_issues(
    generation: GreetingGeneration,
    source: str,
    capture: BrowserJobCaptureRecord,
) -> list[str]:
    issues: list[str] = []
    normalized_source = _normalize(source)
    if len(generation.content) < 20:
        issues.append("Greeting is too short.")
    if len(generation.content) > 300:
        issues.append("Greeting is longer than 300 characters.")
    for evidence in generation.evidence_used:
        if _normalize(evidence) not in normalized_source:
            issues.append(f"Evidence is absent from the source resume: {evidence}")
    allowed_numbers = set(_number_tokens(source + "\n" + capture.jd_text))
    new_numbers = sorted(set(_number_tokens(generation.content)) - allowed_numbers)
    if new_numbers:
        issues.append("Greeting introduces unsupported numbers: " + ", ".join(new_numbers))
    return issues


def _review_average(review: GreetingReview) -> float:
    return (review.naturalness + review.relevance + review.differentiation) / 3


def _candidate_source(profile: ResumeProfile) -> str:
    return "\n".join(
        [
            profile.raw_resume_text or "",
            profile.summary,
            *profile.core_skills,
            *profile.supporting_skills,
            *profile.strengths,
        ]
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _number_tokens(value: str) -> list[str]:
    return re.findall(r"(?<![\w.])(?:\d{1,4}(?:[./-]\d{1,2}){0,2}|\d+(?:\.\d+)?%)(?!\w)", value)
