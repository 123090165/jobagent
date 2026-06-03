from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import scripts.collect_cuhksz_jobs as collector
from app.schemas.cuhksz_career import CUHKSZJobDetail, CUHKSZJobListItem
from app.services.public_job_storage_service import (
    get_public_job_post,
    list_public_job_posts,
    save_public_job_post,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def make_detail(*, jd_text: str | None = None, title: str = "AI 平台实习生") -> CUHKSZJobDetail:
    text = jd_text or (
        "岗位职责：使用 Python、SQL 和数据分析能力建设 AI 平台。\n"
        "任职要求：熟悉机器学习、LLM 应用和基础算法。"
    )
    return CUHKSZJobDetail(
        list_item=CUHKSZJobListItem(
            external_id="468293",
            title=title,
            company="深圳示例科技有限公司",
            location="广东省 - 深圳市",
            job_type="实习",
            education="不限",
            published_at="2026-05-30",
            deadline="2026-07-01",
            detail_url="https://career.cuhk.edu.cn/job/view/id/468293",
        ),
        jd_text=text,
        snippet=text[:80],
        is_full_jd=False,
        confidence=0.55,
        quality_label="partial_jd",
        warnings=["jd_text_too_short"],
        external_links=[],
    )


def test_save_public_job_post_inserts_and_gets_record(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"

    post_id = save_public_job_post(make_detail(), database_path=database_path)
    stored = get_public_job_post(post_id, database_path=database_path)

    assert post_id == 1
    assert stored is not None
    assert stored["source"] == "cuhksz_career"
    assert stored["external_id"] == "468293"
    assert stored["title"] == "AI 平台实习生"
    assert stored["source_url"] == "https://career.cuhk.edu.cn/job/view/id/468293"
    assert stored["content_hash"]
    assert stored["quality_label"] == "partial_jd"
    assert stored["quality_score"] == 0.55
    assert stored["quality_warnings"] == ["jd_text_too_short"]


def test_save_public_job_post_upserts_by_source_and_external_id(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"

    first_id = save_public_job_post(make_detail(), database_path=database_path)
    second_id = save_public_job_post(
        make_detail(jd_text="岗位职责：更新后的 Python 数据平台实习 JD。任职要求：SQL。"),
        database_path=database_path,
    )
    posts = list_public_job_posts(database_path=database_path)

    assert first_id == second_id
    assert len(posts) == 1
    assert "更新后的" in posts[0]["jd_text"]


def test_ensure_public_job_posts_table_adds_missing_quality_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-public-jobs.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE public_job_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            job_type TEXT,
            education TEXT,
            published_at TEXT,
            deadline TEXT,
            snippet TEXT,
            jd_text TEXT NOT NULL,
            is_full_jd INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,
            extraction_method TEXT,
            content_hash TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source, external_id)
        )
        """
    )
    connection.commit()
    connection.close()

    from app.services.public_job_storage_service import ensure_public_job_posts_table

    ensure_public_job_posts_table(database_path=database_path)

    connection = sqlite3.connect(database_path)
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(public_job_posts)").fetchall()
    }
    connection.close()

    assert "quality_label" in columns
    assert "quality_score" in columns
    assert "quality_warnings" in columns
    assert "external_links" in columns


def test_list_public_job_posts_filters_by_keyword(tmp_path: Path) -> None:
    database_path = tmp_path / "public-jobs.sqlite3"
    save_public_job_post(make_detail(), database_path=database_path)
    save_public_job_post(
        make_detail(
            title="后端工程师",
            jd_text="岗位职责：维护后端服务和内部管理系统。任职要求：熟悉 HTTP、数据库和单元测试。",
        ).model_copy(
            update={
                "list_item": make_detail(title="后端工程师").list_item.model_copy(
                    update={
                        "external_id": "468294",
                        "detail_url": "https://career.cuhk.edu.cn/job/view/id/468294",
                    }
                )
            }
        ),
        database_path=database_path,
    )

    results = list_public_job_posts(keyword="AI 平台", database_path=database_path)

    assert len(results) == 1
    assert results[0]["title"] == "AI 平台实习生"


def test_collect_script_dry_run_does_not_write_database(tmp_path: Path, monkeypatch) -> None:
    list_html = (FIXTURES_DIR / "cuhksz_job_list_sample.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "cuhksz_job_detail_sample.html").read_text(encoding="utf-8")
    database_path = tmp_path / "dry-run.sqlite3"
    output_dir = tmp_path / "runs"
    publish_base_dir = tmp_path / "docs_runs"

    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    monkeypatch.setattr(collector, "DOCS_DEMO_RUNS_DIR", str(publish_base_dir))
    monkeypatch.setattr(collector, "fetch_public_html", lambda url, timeout_seconds=15: list_html)
    monkeypatch.setattr(collector, "fetch_cuhksz_job_detail", lambda url, timeout_seconds=15: detail_html)
    monkeypatch.setattr(collector.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        collector,
        "save_public_job_post",
        lambda detail: (_ for _ in ()).throw(AssertionError("dry-run should not save")),
    )

    args = collector.build_parser().parse_args(
        [
            "--limit",
            "1",
            "--dry-run",
            "--publish-sanitized",
            "--output-dir",
            str(output_dir),
        ]
    )
    result = collector.run_collection(args, timestamp="20260602T000000Z")

    assert result.summary.fetched_count == 1
    assert result.summary.detail_success_count == 1
    assert result.summary.saved_count == 0
    assert result.summary.skipped_count == 1
    assert not database_path.exists()

    raw_jobs = json.loads((result.output_dir / "collected_jobs.json").read_text(encoding="utf-8"))
    assert "jd_text" in raw_jobs[0]
    assert "岗位职责" in raw_jobs[0]["jd_text"]

    assert result.publish_dir is not None
    preview_jobs = json.loads(
        (result.publish_dir / "collected_jobs_preview.json").read_text(encoding="utf-8")
    )
    assert "jd_text" not in preview_jobs[0]
    assert len(preview_jobs[0]["jd_text_preview"]) <= 500


def test_collect_script_writes_database_when_not_dry_run(tmp_path: Path, monkeypatch) -> None:
    list_html = (FIXTURES_DIR / "cuhksz_job_list_sample.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "cuhksz_job_detail_sample.html").read_text(encoding="utf-8")
    database_path = tmp_path / "collector-write.sqlite3"
    output_dir = tmp_path / "runs"

    monkeypatch.setenv("JOBAGENT_DB_PATH", str(database_path))
    monkeypatch.setattr(collector, "fetch_public_html", lambda url, timeout_seconds=15: list_html)
    monkeypatch.setattr(collector, "fetch_cuhksz_job_detail", lambda url, timeout_seconds=15: detail_html)
    monkeypatch.setattr(collector.time, "sleep", lambda seconds: None)

    args = collector.build_parser().parse_args(["--limit", "1", "--output-dir", str(output_dir)])
    result = collector.run_collection(args, timestamp="20260602T010000Z")
    stored_jobs = list_public_job_posts(database_path=database_path)

    assert result.summary.saved_count == 1
    assert result.summary.skipped_count == 0
    assert len(stored_jobs) == 1
    assert stored_jobs[0]["external_id"] == "468293"
    assert stored_jobs[0]["is_full_jd"] is True
