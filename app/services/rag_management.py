"""调用 Modular RAG 管理接口执行 upsert/delete，并统一配置与连接错误。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas.rag_sync import FormattedRAGResource


class RAGManagementError(RuntimeError):
    """表示 RAGManagementError 对应的可识别失败。"""
    pass


class RAGManagementConfigurationError(RAGManagementError):
    """表示 RAGManagementConfigurationError 对应的可识别失败。"""
    pass


@dataclass(frozen=True)
class RAGUpsertResult:
    document_id: str
    resource_version: int
    status: str
    chunk_count: int
    replayed: bool


class RAGManagementClient:
    def __init__(
        self,
        base_url: str,
        *,
        service_token: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        parsed = urlparse(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RAGManagementConfigurationError(
                "RAG management URL must be an absolute HTTP(S) URL"
            )
        if parsed.username or parsed.password or parsed.fragment:
            raise RAGManagementConfigurationError(
                "RAG management URL must not contain credentials or fragments"
            )
        if not service_token.strip():
            raise RAGManagementConfigurationError("RAG service token is required")
        if not 0 < timeout_seconds <= 60:
            raise RAGManagementConfigurationError(
                "RAG management timeout must be between 0 and 60 seconds"
            )
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    async def upsert(
        self,
        *,
        event_id: str,
        user_id: str,
        resource: FormattedRAGResource,
    ) -> RAGUpsertResult:
        payload = {
            "schema_version": "1",
            "index_schema_version": 1,
            "operation_id": event_id,
            "resource": {
                "tenant_id": "default",
                "owner_user_id": user_id,
                "resource_type": resource.resource_type,
                "resource_id": resource.resource_id,
                "resource_version": resource.resource_version,
                "visibility": "private",
                "source_updated_at": resource.source_updated_at.isoformat(),
            },
            "content": {
                "content_type": "text/plain",
                "text": resource.text,
            },
            "metadata": {
                "title": resource.title,
                "language": "zh-CN",
                "source_kind": "jobagent",
            },
        }
        data = await self._request(
            "POST",
            "/internal/v1/resources/upsert",
            json=payload,
        )
        return RAGUpsertResult(
            document_id=_required_string(data, "document_id"),
            resource_version=int(data.get("resource_version", 0)),
            status=_required_string(data, "status"),
            chunk_count=int(data.get("chunk_count", 0)),
            replayed=bool(data.get("replayed", False)),
        )

    async def delete(
        self,
        *,
        event_id: str,
        document_id: str,
    ) -> None:
        await self._request(
            "POST",
            "/internal/v1/resources/delete",
            json={"operation_id": event_id, "document_id": document_id},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(self.timeout_seconds, 2.0),
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                headers={"Authorization": f"Bearer {self.service_token}"},
            ) as client:
                response = await client.request(
                    method,
                    self.base_url + path,
                    json=json,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise RAGManagementError("RAG management service is unavailable") from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                error = payload.get("error", {}) if isinstance(payload, dict) else {}
                code = str(error.get("code", "HTTP_ERROR"))
            except ValueError:
                code = "HTTP_ERROR"
            raise RAGManagementError(
                f"RAG management request failed: {code} ({response.status_code})"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RAGManagementError("RAG management response must be an object")
        return payload


def resolve_rag_management_client() -> RAGManagementClient | None:
    base_url = os.getenv("JOBAGENT_RAG_MANAGEMENT_URL", "").strip()
    if not base_url:
        return None
    token = os.getenv("JOBAGENT_RAG_SERVICE_TOKEN", "").strip()
    raw_timeout = os.getenv("JOBAGENT_RAG_MANAGEMENT_TIMEOUT_SECONDS", "15")
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise RAGManagementConfigurationError(
            "JOBAGENT_RAG_MANAGEMENT_TIMEOUT_SECONDS must be numeric"
        ) from exc
    return RAGManagementClient(
        base_url,
        service_token=token,
        timeout_seconds=timeout,
    )


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise RAGManagementError(f"RAG management response missing {field}")
    return value
