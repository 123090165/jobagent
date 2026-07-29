from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from app.config.env_loader import load_local_env
from app.schemas.knowledge import KnowledgeQueryResult
from app.services.mcp import (
    MCPClientError,
    resolve_modular_rag_service,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and exercise the configured Modular RAG MCP service."
    )
    parser.add_argument(
        "--query",
        help="Optional knowledge query used to exercise query_knowledge_hub.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of query results to request (1-20).",
    )
    parser.add_argument(
        "--doc-id",
        help="Optional document id used to exercise get_document_summary.",
    )
    return parser.parse_args()


async def _inspect(args: argparse.Namespace) -> int:
    load_local_env()
    service = resolve_modular_rag_service()
    if service is None:
        print(
            "JOBAGENT_RAG_MCP_URL is not configured.",
            file=sys.stderr,
        )
        return 2

    try:
        inspection = await service.inspect()
        collections = await service.list_collections()
        query_result = (
            await service.query(args.query, top_k=args.top_k)
            if args.query
            else None
        )
        doc_id = args.doc_id or _first_document_id(query_result)
        document_summary = (
            await service.get_document_summary(doc_id)
            if doc_id
            else None
        )
    except MCPClientError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output = {
        "inspection": asdict(inspection),
        "collections": collections.model_dump(mode="json"),
        "query": (
            query_result.model_dump(mode="json")
            if query_result is not None
            else None
        ),
        "document_summary": (
            document_summary.model_dump(mode="json")
            if document_summary is not None
            else None
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _first_document_id(
    query_result: KnowledgeQueryResult | None,
) -> str | None:
    if query_result is None:
        return None
    for item in query_result.results:
        for key in ("document_id", "source_path"):
            value = item.metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def main() -> int:
    return asyncio.run(_inspect(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
