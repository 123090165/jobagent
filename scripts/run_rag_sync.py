"""启动 RAG outbox worker；可单次处理待同步资源，也可持续轮询并更新重试状态。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Sequence

from app.config.env_loader import load_local_env
from app.services.rag_management import resolve_rag_management_client
from app.services.rag_sync_worker import RAGSyncWorker


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process pending JobAgent RAG sync events."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum events to process (1-100).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling the durable outbox until interrupted.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("JOBAGENT_RAG_WORKER_POLL_SECONDS", "2")),
        help="Seconds between active polling attempts.",
    )
    parser.add_argument(
        "--max-idle-interval",
        type=float,
        default=float(os.getenv("JOBAGENT_RAG_WORKER_MAX_IDLE_SECONDS", "30")),
        help="Maximum empty-outbox backoff in seconds.",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be positive")
    if args.max_idle_interval < args.poll_interval:
        parser.error("--max-idle-interval must be at least --poll-interval")
    return args


async def _run(
    limit: int,
    *,
    watch: bool,
    poll_interval: float,
    max_idle_interval: float,
) -> int:
    client = resolve_rag_management_client()
    if client is None:
        raise RuntimeError(
            "JOBAGENT_RAG_MANAGEMENT_URL is required to run RAG synchronization"
        )
    worker = RAGSyncWorker(client)
    if not watch:
        result = await worker.run_once(limit=limit)
        print(
            f"claimed={result.claimed} completed={result.completed} failed={result.failed}"
        )
        return 1 if result.failed else 0
    print(
        "RAG sync worker started "
        f"limit={limit} poll_interval={poll_interval} "
        f"max_idle_interval={max_idle_interval}"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        result = await worker.run_forever(
            limit=limit,
            poll_interval_seconds=poll_interval,
            max_idle_interval_seconds=max_idle_interval,
        )
    except asyncio.CancelledError:
        raise
    finally:
        print("RAG sync worker stopped")
    return 1 if result.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    load_local_env()
    args = parse_args(argv)
    try:
        return asyncio.run(
            _run(
                args.limit,
                watch=args.watch,
                poll_interval=args.poll_interval,
                max_idle_interval=args.max_idle_interval,
            )
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
