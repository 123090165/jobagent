"""返回当前用户的 RAG 服务、同步队列和索引资源状态，供知识库状态页展示。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_authenticated_user
from app.repositories.rag_sync_repository import rag_sync_enabled
from app.schemas.auth import UserAccount
from app.schemas.rag_sync import RAGServiceStatus
from app.services.mcp import MCPClientError
from app.services.mcp.modular_rag import resolve_modular_rag_service
from app.services.rag_admin import RAGAdminService


router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.get("/status", response_model=RAGServiceStatus)
async def get_rag_status_endpoint(
    current_user: UserAccount = Depends(get_authenticated_user),
) -> RAGServiceStatus:
    overview = RAGAdminService().overview(user_id=current_user.user_id)
    try:
        service = resolve_modular_rag_service()
        inspection = await service.inspect() if service is not None else None
    except (MCPClientError, RuntimeError) as exc:
        return RAGServiceStatus(
            sync_enabled=rag_sync_enabled(),
            mcp_configured=True,
            reachable=False,
            reason=type(exc).__name__,
            overview=overview,
        )
    return RAGServiceStatus(
        sync_enabled=rag_sync_enabled(),
        mcp_configured=service is not None,
        reachable=inspection is not None,
        server_name=inspection.server_name if inspection else None,
        server_version=inspection.server_version if inspection else None,
        reason=None if service is not None else "not_configured",
        overview=overview,
    )
