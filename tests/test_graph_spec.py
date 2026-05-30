from __future__ import annotations

import pytest

from app.workflows.graph_spec import (
    WorkflowEdgeSpec,
    get_job_analysis_graph_spec,
    validate_graph_spec,
)
from app.workflows.job_analysis_workflow import run_job_analysis_workflow
from tests.test_mock_pipeline import SAMPLE_JD, SAMPLE_RESUME


def test_graph_spec_matches_workflow_step_order() -> None:
    spec = get_job_analysis_graph_spec()
    workflow_result = run_job_analysis_workflow(SAMPLE_RESUME, SAMPLE_JD)

    validate_graph_spec(spec)
    assert spec.agent_names() == [step.name for step in workflow_result.state.steps]
    assert spec.node_ids() == [
        "resume_parse",
        "jd_analysis",
        "match",
        "resume_optimize",
        "project_interview",
        "report",
    ]
    assert spec.edge_pairs() == [
        ("resume_parse", "jd_analysis"),
        ("jd_analysis", "match"),
        ("match", "resume_optimize"),
        ("resume_optimize", "project_interview"),
        ("project_interview", "report"),
    ]


def test_graph_spec_documents_state_reads_and_writes() -> None:
    spec = get_job_analysis_graph_spec()
    node_by_id = {node.node_id: node for node in spec.nodes}

    assert node_by_id["resume_parse"].reads == ["resume_text"]
    assert node_by_id["resume_parse"].writes == ["resume_profile"]
    assert node_by_id["jd_analysis"].allows_llm is True
    assert node_by_id["jd_analysis"].fallback_policy == "mock"
    assert "markdown_report" in node_by_id["report"].writes
    assert any("Do not write database" in note for note in spec.contract_notes)


def test_graph_spec_mermaid_is_stable() -> None:
    spec = get_job_analysis_graph_spec()
    mermaid = spec.to_mermaid()

    assert "flowchart TD" in mermaid
    assert "resume_parse[ResumeParseAgent]" in mermaid
    assert "project_interview --> report" in mermaid
    assert "report --> finish([FinalReport])" in mermaid


def test_graph_spec_validation_rejects_non_linear_edges() -> None:
    spec = get_job_analysis_graph_spec()
    spec.edges = [WorkflowEdgeSpec(source="resume_parse", target="match")]

    with pytest.raises(ValueError, match="must stay linear"):
        validate_graph_spec(spec)
