from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schemas.job_import_candidate import JobImportCandidate
from app.services.errors import JobAgentError


def _load_demo_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "demo_job_import_candidate.py"
    spec = importlib.util.spec_from_file_location("demo_job_import_candidate", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = _load_demo_module()


def _build_candidate(*, include_full_jd: bool) -> JobImportCandidate:
    return JobImportCandidate(
        candidate_id="cand12345678",
        source="brief_run",
        source_run_id="run123456",
        source_item_id=1,
        title="AI Platform Engineer",
        company="Example Tech",
        location="Shenzhen",
        source_url="https://example.com/jobs/ai-platform-engineer",
        job_type=None,
        education=None,
        deadline=None,
        snippet="Build AI platform APIs.",
        jd_text_preview="Responsibilities: Build AI platform APIs."[:500],
        jd_text=("Responsibilities: Build AI platform APIs.\n" + ("detail " * 120)) if include_full_jd else None,
        quality_label="full_jd",
        quality_score=0.91,
        quality_warnings=[],
        external_links=[],
        fit_score=87.0,
        advice="Apply after highlighting platform projects.",
        fit_reasons=["Strong backend alignment"],
        risk_points=["Need more production ML examples"],
        status="reviewed",
        user_notes=None,
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc).isoformat(),
        updated_at=datetime(2026, 6, 3, tzinfo=timezone.utc).isoformat(),
    )


def test_run_demo_writes_raw_and_sanitized_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(demo, "create_candidate_from_brief_run", lambda run_id, rank=1: _build_candidate(include_full_jd=False))
    monkeypatch.setattr(demo, "update_candidate", lambda candidate_id, status: _build_candidate(include_full_jd=False))
    monkeypatch.setattr(
        demo,
        "get_candidate",
        lambda candidate_id, include_full_jd=False: _build_candidate(include_full_jd=include_full_jd),
    )
    args = demo.build_parser().parse_args(
        [
            "--run-id",
            "run123456",
            "--rank",
            "1",
            "--status",
            "reviewed",
            "--output-dir",
            str(tmp_path / "demo_runs"),
            "--publish-docs-dir",
            str(tmp_path / "docs_demo_runs"),
            "--publish-sanitized",
        ]
    )

    result = demo.run_demo(args, timestamp="20260603T070707Z")

    assert (result.output_dir / "candidate.json").exists()
    assert result.publish_dir is not None
    preview = json.loads((result.publish_dir / "candidate_preview.json").read_text(encoding="utf-8"))
    assert "jd_text" not in preview
    assert preview["jd_text_preview"]
    assert len(preview["jd_text_preview"]) <= 500


def test_run_demo_raises_clear_error_when_creation_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        demo,
        "create_candidate_from_brief_run",
        lambda run_id, rank=1: (_ for _ in ()).throw(JobAgentError("Brief run not found", "brief_run_not_found")),
    )
    args = demo.build_parser().parse_args(
        [
            "--run-id",
            "missing-run",
            "--output-dir",
            str(tmp_path / "demo_runs"),
        ]
    )

    with pytest.raises(ValueError, match="Brief run not found"):
        demo.run_demo(args, timestamp="20260603T080808Z")
