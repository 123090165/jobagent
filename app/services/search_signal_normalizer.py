from __future__ import annotations

from collections.abc import Iterable

SIGNAL_ALIAS_MAP: dict[str, list[str]] = {
    "璇煶璇嗗埆": ["speech recognition", "ASR", "automatic speech recognition"],
    "鐢熺悊淇″彿": ["physiological signal", "biosignal"],
    "鐢熺悊淇″彿澶勭悊": [
        "physiological signal processing",
        "biosignal processing",
        "biomedical signal processing",
    ],
    "鍙┛鎴?": ["wearable", "wearable devices"],
    "鍙┛鎴村仴搴?": ["wearable health", "digital health", "health sensing"],
    "蹇冪數": ["ECG", "electrocardiogram"],
    "鍏夌數瀹圭Н鑴夋悘娉?": ["PPG", "photoplethysmography"],
    "宓屽叆寮?": ["embedded systems", "embedded software", "firmware"],
    "鍗曠墖鏈?": ["MCU", "microcontroller"],
    "娣卞害瀛︿範": ["deep learning"],
    "鏈哄櫒瀛︿範": ["machine learning"],
    "閫氫俊": ["communication", "wireless communication"],
    "璇箟閫氫俊": ["semantic communication"],
    "绠楁硶": ["algorithm"],
    "鍚庣": ["backend"],
    "鍓嶇": ["frontend"],
    "鍏ㄦ爤": ["full stack"],
    "鏁版嵁": ["data"],
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

    normalized_signals = _dedupe([*source_terms, *zh_terms, *en_terms, *[alias for values in aliases.values() for alias in values]])
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
