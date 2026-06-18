from __future__ import annotations

from collections.abc import Iterable

SIGNAL_ALIAS_MAP: dict[str, list[str]] = {
    "语音识别": ["speech recognition", "ASR", "automatic speech recognition"],
    "生理信号": ["physiological signal", "biosignal"],
    "生理信号处理": [
        "physiological signal processing",
        "biosignal processing",
        "biomedical signal processing",
    ],
    "可穿戴": ["wearable", "wearable devices"],
    "可穿戴健康": ["wearable health", "digital health", "health sensing"],
    "心电": ["ECG", "electrocardiogram"],
    "光电容积脉搏波": ["PPG", "photoplethysmography"],
    "嵌入式": ["embedded systems", "embedded software", "firmware"],
    "单片机": ["MCU", "microcontroller"],
    "深度学习": ["deep learning"],
    "机器学习": ["machine learning"],
    "通信": ["communication", "wireless communication"],
    "语义通信": ["semantic communication"],
    "算法": ["algorithm"],
    "后端": ["backend"],
    "前端": ["frontend"],
    "全栈": ["full stack"],
    "数据": ["data"],
}


def build_bilingual_search_signals(
    target_roles: list[str],
    keywords: list[str],
    core_skills: list[str],
) -> dict[str, object]:
    source_terms = _dedupe([*target_roles, *keywords, *core_skills])
    zh_terms = [term for term in source_terms if _contains_cjk(term)]
    en_terms = [term for term in source_terms if not _contains_cjk(term)]
    aliases: dict[str, list[str]] = {}

    for term in source_terms:
        mapped = SIGNAL_ALIAS_MAP.get(term, [])
        if mapped:
            aliases[term] = _dedupe(mapped)
            en_terms.extend(mapped)

    normalized_signals = _dedupe(
        [*source_terms, *zh_terms, *en_terms, *[alias for values in aliases.values() for alias in values]]
    )
    return {
        "zh_terms": _dedupe(zh_terms),
        "en_terms": _dedupe(en_terms),
        "aliases": aliases,
        "normalized_signals": normalized_signals,
    }


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _dedupe(values: Iterable[str]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items
