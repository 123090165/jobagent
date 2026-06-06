from __future__ import annotations

from urllib.parse import urlparse

import requests

from app.services.errors import JobAgentError

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_PUBLIC_HTML_BYTES = 3 * 1024 * 1024
USER_AGENT = "JobAgent/0.1 (+https://github.com/123090165/jobagent)"


class LiveJobFetchError(JobAgentError):
    def __init__(
        self,
        message: str,
        error_code: str = "live_job_fetch_failed",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, error_code=error_code, status_code=status_code)


def fetch_public_html(
    url: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_PUBLIC_HTML_BYTES,
) -> str:
    normalized_url = _validate_public_http_url(url)
    try:
        response = requests.get(
            normalized_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            },
            timeout=timeout_seconds,
            stream=True,
        )
    except requests.RequestException as exc:
        raise LiveJobFetchError(f"Failed to fetch public HTML page: {exc}") from exc

    try:
        response.raise_for_status()
        _validate_content_length(response.headers.get("Content-Length"), max_bytes)
        body = _read_response_body(response, max_bytes)
        encoding = response.encoding or response.apparent_encoding or "utf-8"
    except requests.RequestException as exc:
        raise LiveJobFetchError(f"Failed to fetch public HTML page: {exc}") from exc
    finally:
        response.close()

    return body.decode(encoding, errors="replace")


def _validate_public_http_url(url: str) -> str:
    normalized_url = (url or "").strip()
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise LiveJobFetchError(
            "Public URL must use http or https",
            error_code="live_job_url_invalid",
            status_code=400,
        )
    if not parsed.netloc:
        raise LiveJobFetchError(
            "Public URL is invalid",
            error_code="live_job_url_invalid",
            status_code=400,
        )
    return normalized_url


def _validate_content_length(content_length: str | None, max_bytes: int) -> None:
    if content_length is None:
        return
    try:
        total_bytes = int(content_length)
    except (TypeError, ValueError):
        return
    if total_bytes > max_bytes:
        raise LiveJobFetchError(
            "Public HTML response is too large",
            error_code="live_job_response_too_large",
            status_code=400,
        )


def _read_response_body(response: requests.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise LiveJobFetchError(
                "Public HTML response is too large",
                error_code="live_job_response_too_large",
                status_code=400,
            )
        chunks.append(chunk)
    return b"".join(chunks)
