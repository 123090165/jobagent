from app.services.live_job.parsers.cuhksz import (
    CUHKSZParser,
    DEFAULT_CUHKSZ_LIST_URL,
    DETAIL_BODY_SELECTORS,
    NAVIGATION_TERMS,
    extract_cuhksz_detail_text,
)

__all__ = [
    "CUHKSZParser",
    "DEFAULT_CUHKSZ_LIST_URL",
    "DETAIL_BODY_SELECTORS",
    "NAVIGATION_TERMS",
    "extract_cuhksz_detail_text",
]
