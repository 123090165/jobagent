from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict

from app.config.env_loader import load_local_env
from app.services.rag_admin import rag_admin_service


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and manage JobAgent's durable RAG synchronization queue."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backfill = commands.add_parser(
        "backfill",
        help="Enqueue missing active Resume Profiles and Saved Jobs.",
    )
    backfill.add_argument("--user-id")
    backfill.add_argument(
        "--resource-type",
        action="append",
        choices=("resume_profile", "saved_job"),
        dest="resource_types",
    )
    backfill.add_argument(
        "--force",
        action="store_true",
        help="Enqueue a new version even when the current index is ready.",
    )

    reindex = commands.add_parser("reindex", help="Reindex one active resource.")
    reindex.add_argument("--user-id", required=True)
    reindex.add_argument(
        "--resource-type",
        required=True,
        choices=("resume_profile", "saved_job"),
    )
    reindex.add_argument("--resource-id", required=True)

    status = commands.add_parser("status", help="Show durable sync status as JSON.")
    status.add_argument("--user-id")

    reconcile = commands.add_parser(
        "reconcile",
        help="Repair active/deleted drift between business resources and sync state.",
    )
    reconcile.add_argument("--user-id")

    retry = commands.add_parser(
        "retry-failed",
        help="Reset current failed events for another bounded attempt cycle.",
    )
    retry.add_argument("--user-id")
    retry.add_argument("--limit", type=int, default=100)

    args = parser.parse_args(argv)
    if args.command == "retry-failed" and not 1 <= args.limit <= 1_000:
        parser.error("--limit must be between 1 and 1000")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    load_local_env()
    args = parse_args(argv)
    if args.command == "backfill":
        result = rag_admin_service.backfill(
            user_id=args.user_id,
            resource_types=tuple(
                args.resource_types or ("resume_profile", "saved_job")
            ),
            force=args.force,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    if args.command == "reindex":
        event_id = rag_admin_service.reindex(
            user_id=args.user_id,
            resource_type=args.resource_type,
            resource_id=args.resource_id,
        )
        print(json.dumps({"event_id": event_id}, indent=2))
        return 0
    if args.command == "status":
        overview = rag_admin_service.overview(user_id=args.user_id)
        print(overview.model_dump_json(indent=2))
        return 1 if overview.failed_resource_count else 0
    if args.command == "reconcile":
        result = rag_admin_service.reconcile(user_id=args.user_id)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    retried = rag_admin_service.retry_failed(
        user_id=args.user_id,
        limit=args.limit,
    )
    print(json.dumps({"events_retried": retried}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
