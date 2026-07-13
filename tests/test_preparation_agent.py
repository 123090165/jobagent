from __future__ import annotations

from app.schemas.interview_preparation import PreparationAnswer, PreparationQuestion
from app.services.preparation_agent import PreparationAgent


def test_agent_pauses_resumes_and_completes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = PreparationQuestion(
        question_id="q1",
        skill="Python",
        prompt="Choose the closest level.",
        why_asked="The role requires Python.",
    )
    agent.start("prep-1", [question])

    paused = agent.resume(
        "prep-1",
        [PreparationAnswer(question_id="q1", experience_level="practice_only")],
        "save",
        questions=[question],
    )
    assert paused["status"] == "paused"

    completed = agent.resume(
        "prep-1",
        [PreparationAnswer(question_id="q1", experience_level="project_experience")],
        "complete",
        questions=[question],
    )
    assert completed["status"] == "completed"
