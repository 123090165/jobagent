from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowNodeSpec(BaseModel):
    node_id: str
    agent_name: str
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    allows_llm: bool = False
    fallback_policy: str = "none"
    migration_note: str


class WorkflowEdgeSpec(BaseModel):
    source: str
    target: str
    condition: str = "always"


class WorkflowGraphSpec(BaseModel):
    workflow_name: str
    state_model: str
    result_model: str
    entrypoint: str
    finish: str
    nodes: list[WorkflowNodeSpec]
    edges: list[WorkflowEdgeSpec]
    contract_notes: list[str] = Field(default_factory=list)

    def node_ids(self) -> list[str]:
        return [node.node_id for node in self.nodes]

    def agent_names(self) -> list[str]:
        return [node.agent_name for node in self.nodes]

    def edge_pairs(self) -> list[tuple[str, str]]:
        return [(edge.source, edge.target) for edge in self.edges]

    def to_mermaid(self) -> str:
        lines = [f"flowchart TD", f"    start([{self.entrypoint}])"]
        for node in self.nodes:
            lines.append(f"    {node.node_id}[{node.agent_name}]")
        for edge in self.edges:
            lines.append(f"    {edge.source} --> {edge.target}")
        lines.append(f"    {self.finish} --> finish([{self.result_model}])")
        return "\n".join(lines)


JOB_ANALYSIS_GRAPH_SPEC = WorkflowGraphSpec(
    workflow_name="job_analysis",
    state_model="JobAnalysisWorkflowState",
    result_model="FinalReport",
    entrypoint="resume_parse",
    finish="report",
    nodes=[
        WorkflowNodeSpec(
            node_id="resume_parse",
            agent_name="ResumeParseAgent",
            reads=["resume_text"],
            writes=["resume_profile"],
            migration_note="Normalize and parse the raw resume text into ResumeProfile.",
        ),
        WorkflowNodeSpec(
            node_id="jd_analysis",
            agent_name="JDAnalysisAgent",
            reads=["jd_text", "use_llm_jd"],
            writes=["job_analysis"],
            allows_llm=True,
            fallback_policy="mock",
            migration_note="Analyze JD with optional LLM and mock fallback.",
        ),
        WorkflowNodeSpec(
            node_id="match",
            agent_name="MatchAgent",
            reads=["resume_profile", "job_analysis"],
            writes=["match_report"],
            migration_note="Compare structured resume and JD into a MatchReport.",
        ),
        WorkflowNodeSpec(
            node_id="resume_optimize",
            agent_name="ResumeOptimizeAgent",
            reads=["resume_text", "resume_profile", "job_analysis", "match_report"],
            writes=["optimization_result"],
            migration_note="Suggest truthful resume improvements without inventing experience.",
        ),
        WorkflowNodeSpec(
            node_id="project_interview",
            agent_name="ProjectInterviewAgent",
            reads=["resume_profile", "job_analysis"],
            writes=["project_challenge_report"],
            migration_note="Generate project interview questions from resume and JD evidence.",
        ),
        WorkflowNodeSpec(
            node_id="report",
            agent_name="ReportAgent",
            reads=[
                "resume_profile",
                "job_analysis",
                "match_report",
                "optimization_result",
                "project_challenge_report",
            ],
            writes=["markdown_report"],
            migration_note="Aggregate structured state into the final Markdown report.",
        ),
    ],
    edges=[
        WorkflowEdgeSpec(source="resume_parse", target="jd_analysis"),
        WorkflowEdgeSpec(source="jd_analysis", target="match"),
        WorkflowEdgeSpec(source="match", target="resume_optimize"),
        WorkflowEdgeSpec(source="resume_optimize", target="project_interview"),
        WorkflowEdgeSpec(source="project_interview", target="report"),
    ],
    contract_notes=[
        "Keep run_job_analysis_workflow as the stable public entrypoint during migration.",
        "Do not change FastAPI, Streamlit, storage, or run_mock_pipeline contracts in the prep step.",
        "Keep fallback inside Agent boundaries rather than graph routing until the main path is stable.",
        "Do not write database records from graph nodes.",
    ],
)


def get_job_analysis_graph_spec() -> WorkflowGraphSpec:
    return JOB_ANALYSIS_GRAPH_SPEC.model_copy(deep=True)


def validate_graph_spec(spec: WorkflowGraphSpec) -> None:
    node_ids = spec.node_ids()
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("workflow node ids must be unique")
    if spec.entrypoint not in node_ids:
        raise ValueError("workflow entrypoint must be a node id")
    if spec.finish not in node_ids:
        raise ValueError("workflow finish must be a node id")

    node_id_set = set(node_ids)
    for edge in spec.edges:
        if edge.source not in node_id_set:
            raise ValueError(f"edge source is not a node id: {edge.source}")
        if edge.target not in node_id_set:
            raise ValueError(f"edge target is not a node id: {edge.target}")

    expected_linear_edges = list(zip(node_ids, node_ids[1:]))
    if spec.edge_pairs() != expected_linear_edges:
        raise ValueError("job analysis graph spec must stay linear during migration prep")

    finish_node = next(node for node in spec.nodes if node.node_id == spec.finish)
    if "markdown_report" not in finish_node.writes:
        raise ValueError("workflow finish node must write markdown_report")
