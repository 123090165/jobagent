from __future__ import annotations

import pytest

from app.services.jd_url_service import (
    DEFAULT_MAX_JD_URL_BYTES,
    JDUrlImportError,
    extract_text_from_html,
    get_max_jd_url_bytes,
    import_jd_from_url,
    validate_jd_url,
)


class FakeHTTPResponse:
    def __init__(self, body: bytes, *, content_type: str = "text/html", content_length: int | None = None):
        self._body = body
        self._offset = 0
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_validate_jd_url_accepts_http_and_https() -> None:
    assert validate_jd_url("https://example.com/job") == "https://example.com/job"
    assert validate_jd_url("http://example.com/jobs/123") == "http://example.com/jobs/123"


def test_validate_jd_url_rejects_empty_url() -> None:
    with pytest.raises(JDUrlImportError, match="JD URL cannot be empty") as exc_info:
        validate_jd_url("  ")
    assert exc_info.value.error_code == "jd_url_invalid"


def test_validate_jd_url_rejects_non_http_scheme() -> None:
    with pytest.raises(JDUrlImportError, match="JD URL must use http or https") as exc_info:
        validate_jd_url("ftp://example.com/job")
    assert exc_info.value.error_code == "jd_url_scheme_unsupported"


def test_extract_text_from_html_removes_script_and_style() -> None:
    html = """
    <html>
      <head>
        <style>body { display:none; }</style>
        <script>window.alert("x")</script>
      </head>
      <body>
        <h1>Python Backend Engineer</h1>
        <p>Build FastAPI services and APIs for hiring workflows.</p>
        <noscript>ignore this</noscript>
      </body>
    </html>
    """

    extracted = extract_text_from_html(html)

    assert "window.alert" not in extracted
    assert "display:none" not in extracted
    assert "ignore this" not in extracted
    assert "Python Backend Engineer" in extracted


def test_import_jd_from_url_accepts_html(monkeypatch) -> None:
    html = (
        "<html><body><h1>AI Engineer</h1><p>"
        + ("Build FastAPI and Python services for JD analysis. " * 8)
        + "</p></body></html>"
    ).encode("utf-8")

    monkeypatch.setattr(
        "app.services.jd_url_service.urlopen",
        lambda request, timeout: FakeHTTPResponse(html, content_type="text/html; charset=utf-8"),
    )

    extracted = import_jd_from_url("https://example.com/job")

    assert "AI Engineer" in extracted
    assert "FastAPI" in extracted


def test_import_jd_from_url_accepts_plain_text(monkeypatch) -> None:
    text = ("Python backend role. " * 12).encode("utf-8")

    monkeypatch.setattr(
        "app.services.jd_url_service.urlopen",
        lambda request, timeout: FakeHTTPResponse(text, content_type="text/plain; charset=utf-8"),
    )

    extracted = import_jd_from_url("https://example.com/job.txt")

    assert extracted.startswith("Python backend role.")


def test_import_jd_from_url_rejects_short_text(monkeypatch) -> None:
    html = b"<html><body><p>Too short</p></body></html>"

    monkeypatch.setattr(
        "app.services.jd_url_service.urlopen",
        lambda request, timeout: FakeHTTPResponse(html, content_type="text/html"),
    )

    with pytest.raises(JDUrlImportError, match="too short") as exc_info:
        import_jd_from_url("https://example.com/job")
    assert exc_info.value.error_code == "jd_url_text_too_short"


def test_import_jd_from_url_rejects_oversized_response(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_MAX_JD_URL_BYTES", "32")
    body = b"a" * 64

    monkeypatch.setattr(
        "app.services.jd_url_service.urlopen",
        lambda request, timeout: FakeHTTPResponse(body, content_type="text/plain", content_length=64),
    )

    with pytest.raises(JDUrlImportError, match="too large") as exc_info:
        import_jd_from_url("https://example.com/job")
    assert exc_info.value.error_code == "jd_url_response_too_large"


def test_import_jd_from_url_rejects_unsupported_content_type(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.jd_url_service.urlopen",
        lambda request, timeout: FakeHTTPResponse(b"{}", content_type="application/json"),
    )

    with pytest.raises(JDUrlImportError, match="text/html or text/plain") as exc_info:
        import_jd_from_url("https://example.com/job")
    assert exc_info.value.error_code == "jd_url_content_type_unsupported"


def test_import_jd_from_url_rejects_network_failure(monkeypatch) -> None:
    def failing_urlopen(request, timeout):
        raise OSError("network down")

    monkeypatch.setattr("app.services.jd_url_service.urlopen", failing_urlopen)

    with pytest.raises(JDUrlImportError, match="Please paste the JD manually") as exc_info:
        import_jd_from_url("https://example.com/job")
    assert exc_info.value.error_code == "jd_url_fetch_failed"


def test_get_max_jd_url_bytes_uses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("JOBAGENT_MAX_JD_URL_BYTES", "2048")
    assert get_max_jd_url_bytes() == 2048


def test_get_max_jd_url_bytes_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("JOBAGENT_MAX_JD_URL_BYTES", raising=False)
    assert get_max_jd_url_bytes() == DEFAULT_MAX_JD_URL_BYTES
