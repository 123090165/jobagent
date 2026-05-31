from __future__ import annotations

import os
import re
from html import unescape
from pathlib import PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.services.errors import JobAgentError

DEFAULT_MAX_JD_URL_BYTES = 512 * 1024
DEFAULT_JD_URL_TIMEOUT_SECONDS = 8
MIN_EXTRACTED_JD_TEXT_LENGTH = 100
SUPPORTED_JD_CONTENT_TYPES = {"text/html", "text/plain"}


class JDUrlImportError(JobAgentError):
    """User-facing error for safe JD URL imports."""


def import_jd_from_url(url: str) -> str:
    normalized_url = validate_jd_url(url)
    max_bytes = get_max_jd_url_bytes()
    request = Request(
        normalized_url,
        headers={
            "User-Agent": "JobAgent/0.3",
            "Accept": "text/html, text/plain;q=0.9",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=DEFAULT_JD_URL_TIMEOUT_SECONDS) as response:
            content_type = get_response_content_type(response)
            if content_type not in SUPPORTED_JD_CONTENT_TYPES:
                raise JDUrlImportError(
                    "JD URL must return text/html or text/plain content",
                    "jd_url_content_type_unsupported",
                )

            content_length = get_response_content_length(response)
            if content_length is not None and content_length > max_bytes:
                raise JDUrlImportError(
                    "JD URL response is too large",
                    "jd_url_response_too_large",
                )

            body = read_response_body(response, max_bytes=max_bytes)
    except JDUrlImportError:
        raise
    except Exception as exc:
        raise JDUrlImportError(
            "Failed to fetch JD URL. Please paste the JD manually.",
            "jd_url_fetch_failed",
        ) from exc

    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JDUrlImportError(
            "Failed to decode JD URL content. Please paste the JD manually.",
            "jd_url_fetch_failed",
        ) from exc

    extracted_text = (
        extract_text_from_html(decoded)
        if content_type == "text/html"
        else normalize_plain_text(decoded)
    )
    if len(extracted_text) < MIN_EXTRACTED_JD_TEXT_LENGTH:
        raise JDUrlImportError(
            "Imported JD text is too short. Please paste the JD manually.",
            "jd_url_text_too_short",
        )
    return extracted_text


def validate_jd_url(url: str) -> str:
    normalized_url = (url or "").strip()
    if not normalized_url:
        raise JDUrlImportError("JD URL cannot be empty", "jd_url_invalid")

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise JDUrlImportError(
            "JD URL must use http or https",
            "jd_url_scheme_unsupported",
        )
    if not parsed.netloc:
        raise JDUrlImportError("JD URL is invalid", "jd_url_invalid")

    normalized_path = str(PurePosixPath(parsed.path or "/"))
    return parsed._replace(path=normalized_path).geturl()


def extract_text_from_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|section|article|li|ul|ol|h[1-6]|tr|td|th)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return normalize_plain_text(unescape(text))


def normalize_plain_text(text: str) -> str:
    collapsed = re.sub(r"\r\n?", "\n", text)
    collapsed = re.sub(r"[ \t\f\v]+", " ", collapsed)
    collapsed = re.sub(r"\n\s*\n+", "\n\n", collapsed)
    return collapsed.strip()


def get_max_jd_url_bytes() -> int:
    raw_value = os.getenv("JOBAGENT_MAX_JD_URL_BYTES")
    if not raw_value:
        return DEFAULT_MAX_JD_URL_BYTES
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_MAX_JD_URL_BYTES
    return parsed if parsed > 0 else DEFAULT_MAX_JD_URL_BYTES


def get_response_content_type(response) -> str:
    raw_value = ""
    if getattr(response, "headers", None) is not None:
        raw_value = response.headers.get("Content-Type", "")
    return raw_value.split(";", 1)[0].strip().lower()


def get_response_content_length(response) -> int | None:
    raw_value = ""
    if getattr(response, "headers", None) is not None:
        raw_value = response.headers.get("Content-Length", "")
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def read_response_body(response, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise JDUrlImportError(
                "JD URL response is too large",
                "jd_url_response_too_large",
            )
        chunks.append(chunk)
    return b"".join(chunks)
