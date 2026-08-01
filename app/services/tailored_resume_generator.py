from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.schemas.resume_profile import ResumeProfile
from app.schemas.saved_job import SavedJob
from app.schemas.tailored_resume import ResumeFactValidation
from app.services.llm_provider import JSONChatLLM


RESUME_COMPLETION_MARKER = "<!-- JOBAGENT_RESUME_DONE -->"
MAX_GENERATION_ATTEMPTS = 2
DEFAULT_MAX_RESUME_CHARS = 12_000

_FACT_PATTERNS = (
    re.compile(r"(?<![\w.])(?:\d{1,4}(?:[./-]\d{1,2}){0,2}|\d+(?:\.\d+)?%)(?!\w)"),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"https?://[^\s)]+"),
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
)
_PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\n]{1,80}\]|【[^】\n]{1,80}】|<[^>\n]{1,80}>")
_PROCESS_PHRASES = ("根据JD", "根据 JD", "岗位匹配亮点", "简历优化说明", "优化建议")


class TailoredResumeGeneration(BaseModel):
    content: str = Field(min_length=1)


@dataclass(frozen=True)
class ResumeGenerationFailure(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def generate_tailored_resume(
    job: SavedJob,
    profile: ResumeProfile,
    *,
    llm_service: JSONChatLLM,
) -> tuple[TailoredResumeGeneration, ResumeFactValidation]:
    """完整生成并校验简历；失败时不返回半成品，也不执行降级。"""
    source_resume = _candidate_source(profile).strip()
    if not source_resume:
        raise ResumeGenerationFailure("resume_source_empty", "The source resume is empty.")

    base_prompt = _generation_prompt(job, source_resume)
    prompt = base_prompt
    last_issues: list[str] = []
    for attempt in range(MAX_GENERATION_ATTEMPTS):
        try:
            response = llm_service.chat_completion_json(
                system_prompt=_system_prompt(),
                user_prompt=prompt,
            )
            raw_content = str(response.get("content") or "")
        except Exception as exc:
            raise ResumeGenerationFailure(
                "generation_failed",
                "Tailored resume generation failed. Check the model configuration and try again.",
            ) from exc

        candidate, completion_issue = _strip_completion_marker(raw_content)
        if candidate is None:
            blocking_issues = [completion_issue or "Generated resume is empty."]
            warnings: list[str] = []
        else:
            validation = validate_resume_facts(candidate, profile)
            blocking_issues = list(validation.issues)
            warnings = list(validation.warnings)
            if completion_issue:
                blocking_issues.insert(0, completion_issue)

        retry_for_length = any(item.startswith("Resume content is too long") for item in warnings)
        if not blocking_issues and not retry_for_length and candidate is not None:
            return TailoredResumeGeneration(content=candidate), validation

        last_issues = list(dict.fromkeys([*blocking_issues, *warnings]))
        if attempt == 0:
            prompt = _retry_prompt(base_prompt, last_issues)

    raise ResumeGenerationFailure(
        "generation_validation_failed",
        "The generated resume did not pass validation after one correction: "
        + "; ".join(last_issues[:6]),
    )


def validate_resume_facts(content: str, profile: ResumeProfile) -> ResumeFactValidation:
    """沿用 BossHunter 的高风险事实检查，语义真实性仍由用户最终确认。"""
    source = _candidate_source(profile)
    issues: list[str] = []
    warnings: list[str] = []
    stripped = content.strip()

    if not stripped:
        issues.append("Resume content is empty.")
        return ResumeFactValidation(is_valid=False, issues=issues, warnings=warnings)

    missing_facts = _missing_source_facts(stripped, source)
    if missing_facts:
        issues.append(
            "Core facts from the source resume are missing: " + ", ".join(missing_facts[:8])
        )

    new_facts = _new_fact_tokens(stripped, source)
    if new_facts:
        issues.append(
            "The resume introduces facts absent from the source: " + ", ".join(new_facts[:8])
        )

    new_placeholders = _new_placeholders(stripped, source)
    if new_placeholders:
        issues.append(
            "The resume introduces or changes placeholders: "
            + ", ".join(new_placeholders[:8])
        )

    if not stripped.startswith("#"):
        warnings.append("Generated content does not start like a Markdown resume.")
    if len(stripped) > DEFAULT_MAX_RESUME_CHARS:
        warnings.append(
            f"Resume content is too long ({len(stripped)} characters; target {DEFAULT_MAX_RESUME_CHARS})."
        )
    for heading in _source_headings(source):
        if heading not in stripped:
            warnings.append(f"A source resume section is missing: {heading.lstrip('# ').strip()}")
    if _looks_abrupt(stripped):
        warnings.append("The resume ending may be truncated.")
    if _is_nearly_unchanged(stripped, source):
        warnings.append("The generated resume is nearly identical to the source resume.")
    for phrase in _PROCESS_PHRASES:
        if phrase.casefold() in stripped.casefold():
            warnings.append(f"The resume contains process text that should be removed: {phrase}")

    return ResumeFactValidation(
        is_valid=not issues,
        issues=list(dict.fromkeys(issues)),
        warnings=list(dict.fromkeys(warnings)),
    )


def _system_prompt() -> str:
    return (
        "你是求职简历编辑器。只能使用基础简历中已有的候选人事实，可以调整顺序、强调程度、措辞和篇幅，"
        "不能新增技能、公司、学校、项目、年限、数字或成果。JD 只能决定强调顺序，不能成为候选人经历。"
        "必须输出完整 Markdown 简历，不要输出分析、修改说明或代码围栏。"
        "最后单独输出完成标记。返回 JSON，且只包含 content。"
    )


def _generation_prompt(job: SavedJob, source_resume: str) -> str:
    return json.dumps(
        {
            "task": "为目标岗位生成完整、可直接审阅的 Markdown 简历。",
            "rules": [
                "保留基础身份信息和基础简历中的常规栏目。",
                "项目和经历按岗位相关度排序，弱相关内容可以压缩。",
                "不得把岗位职责写成候选人经历。",
                "不得输出岗位匹配亮点、优化说明或其他过程文字。",
                f"最后单独输出 {RESUME_COMPLETION_MARKER}",
            ],
            "job": {
                "title": job.title,
                "company": job.company,
                "description": job.raw_jd_text[:6000],
            },
            "source_resume": source_resume,
        },
        ensure_ascii=False,
    )


def _retry_prompt(base_prompt: str, issues: list[str]) -> str:
    return (
        base_prompt
        + "\n\n上一次结果未通过检查。只纠正下面的问题，然后重新输出完整简历：\n- "
        + "\n- ".join(issues[:10])
    )


def _strip_completion_marker(value: str) -> tuple[str | None, str | None]:
    content = _strip_code_fence(value).strip()
    if RESUME_COMPLETION_MARKER not in content:
        return (content or None), "Generated resume is missing the completion marker."
    body = content.split(RESUME_COMPLETION_MARKER, 1)[0].strip()
    if not body:
        return None, "Generated resume is empty."
    return body + "\n", None


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1])
    return stripped


def _candidate_source(profile: ResumeProfile) -> str:
    if profile.raw_resume_text and profile.raw_resume_text.strip():
        return profile.raw_resume_text
    return "\n".join(
        [profile.summary, *profile.core_skills, *profile.supporting_skills, *profile.strengths]
    )


def _fact_tokens(value: str) -> list[str]:
    return [match.group(0) for pattern in _FACT_PATTERNS for match in pattern.finditer(value)]


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _new_fact_tokens(content: str, source: str) -> list[str]:
    source_tokens = {_normalized(token) for token in _fact_tokens(source)}
    return list(
        dict.fromkeys(
            token for token in _fact_tokens(content) if _normalized(token) not in source_tokens
        )
    )


def _missing_source_facts(content: str, source: str) -> list[str]:
    core_source = _core_source_text(source)
    content_tokens = {_normalized(token) for token in _fact_tokens(content)}
    return list(
        dict.fromkeys(
            token
            for token in _fact_tokens(core_source)
            if _normalized(token) not in content_tokens
        )
    )


def _core_source_text(source: str) -> str:
    """优先检查基本信息区；无结构文本只强制保留联系方式。"""
    heading = re.search(
        r"(?im)^##\s*(?:基本信息|个人信息|basic information|contact)\s*$",
        source,
    )
    if heading:
        following = source[heading.end() :]
        next_heading = re.search(r"(?m)^##\s+", following)
        return following[: next_heading.start()] if next_heading else following
    contact_patterns = _FACT_PATTERNS[1:]
    return "\n".join(
        match.group(0)
        for pattern in contact_patterns
        for match in pattern.finditer(source)
    )


def _new_placeholders(content: str, source: str) -> list[str]:
    source_placeholders = {_normalized(item) for item in _PLACEHOLDER_PATTERN.findall(source)}
    return list(
        dict.fromkeys(
            item
            for item in _PLACEHOLDER_PATTERN.findall(content)
            if _normalized(item) not in source_placeholders
        )
    )


def _source_headings(source: str) -> list[str]:
    return list(
        dict.fromkeys(
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith("## ")
        )
    )


def _looks_abrupt(content: str) -> bool:
    last_line = next((line.strip() for line in reversed(content.splitlines()) if line.strip()), "")
    return bool(last_line) and last_line[-1] in {",", ";", "，", "；", ":", "：", "、", "("}


def _is_nearly_unchanged(content: str, source: str) -> bool:
    if not source.strip():
        return False
    return SequenceMatcher(None, _normalized(content), _normalized(source)).ratio() >= 0.985
