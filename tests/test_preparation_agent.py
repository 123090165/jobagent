from __future__ import annotations

from app.schemas.interview_preparation import (
    PreparationAnswer,
    PreparationAnswerOption,
    PreparationQuestion,
)
from app.services.preparation_agent import PreparationAgent


def _question() -> PreparationQuestion:
    return PreparationQuestion(
        question_id="q1",
        skill="Python",
        prompt="Choose the closest level.",
        why_asked="The role requires Python.",
        options=[
            PreparationAnswerOption(
                option_id="python_project",
                value="project_experience",
                label="Used Python in a project",
                description="Implemented a bounded project.",
                evidence_transition="partial",
                route="ask_evidence",
                detail_policy="required",
                follow_up_prompt="What did you implement and how did you evaluate it?",
            ),
            PreparationAnswerOption(
                option_id="python_practice",
                value="practice_only",
                label="Practised Python",
                description="Used it in guided exercises.",
                evidence_transition="partial",
                route="learning",
                detail_policy="optional",
            ),
            PreparationAnswerOption(
                option_id="python_none",
                value="no_experience",
                label="No Python experience",
                description="Have not learned or used it.",
                evidence_transition="missing",
                route="capability_gap",
                detail_policy="not_needed",
            ),
            PreparationAnswerOption(
                option_id="python_uncertain",
                value="uncertain",
                label="None of these fits",
                description="The boundary is unclear.",
                evidence_transition="unknown",
                route="clarify",
                detail_policy="required",
                follow_up_prompt="What boundary do the choices miss?",
            ),
        ],
    )


def test_agent_uses_learning_and_capability_routes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = _question()
    agent.start("prep-learning", [question])

    paused = agent.resume(
        "prep-learning",
        [PreparationAnswer(question_id="q1", selected_option_id="python_practice")],
        "save",
        questions=[question],
    )
    assert paused["status"] == "paused"
    assert paused["transitions"][0]["route"] == "learning"

    completed = agent.resume(
        "prep-learning",
        [PreparationAnswer(question_id="q1", selected_option_id="python_none")],
        "complete",
        questions=[question],
    )
    assert completed["status"] == "completed"
    assert completed["transitions"][-1]["route"] == "capability_gap"


def test_agent_advance_commits_or_pauses_one_answer(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = _question()
    agent.start("prep-advance", [question])

    advanced = agent.resume(
        "prep-advance",
        [PreparationAnswer(question_id="q1", selected_option_id="python_practice")],
        "advance",
        questions=[question],
    )
    assert advanced["status"] == "questions_ready"
    assert advanced["answers"][0]["committed"] is True

    agent.start("prep-advance-follow-up", [question])
    paused = agent.resume(
        "prep-advance-follow-up",
        [PreparationAnswer(question_id="q1", selected_option_id="python_project")],
        "advance",
        questions=[question],
    )
    assert paused["status"] == "paused"
    assert paused["answers"][0]["pending_prompt"]
    assert paused["answers"][0]["committed"] is False


def test_agent_reasks_vague_evidence_then_closes_partial(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = _question()
    agent.start("prep-vague", [question])

    paused = agent.resume(
        "prep-vague",
        [PreparationAnswer(
            question_id="q1",
            selected_option_id="python_project",
            detail="I have some Python project experience.",
        )],
        "complete",
        questions=[question],
    )
    assert paused["status"] == "paused"
    assert paused["pending_question_ids"] == ["q1"]
    assert paused["answers"][0]["route"] == "ask_evidence"
    assert paused["answers"][0]["evidence_transition"] == "partial"
    assert paused["answers"][0]["follow_up_count"] == 1

    completed = agent.resume(
        "prep-vague",
        [PreparationAnswer.model_validate(paused["answers"][0])],
        "complete",
        questions=[question],
    )
    assert completed["status"] == "completed"
    assert completed["answers"][0]["route"] == "next_skill"
    assert completed["answers"][0]["evidence_transition"] == "partial"


def test_agent_upgrades_specific_evidence_to_supported(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = _question()
    agent.start("prep-specific", [question])

    completed = agent.resume(
        "prep-specific",
        [PreparationAnswer(
            question_id="q1",
            selected_option_id="python_project",
            detail=(
                "I implemented a Python ingestion pipeline, used pytest for validation, "
                "and evaluated it on 2,000 records."
            ),
        )],
        "complete",
        questions=[question],
    )
    assert completed["status"] == "completed"
    assert completed["answers"][0]["input_mode"] == "option_with_detail"
    assert completed["answers"][0]["detail_quality"] == "specific"
    assert completed["answers"][0]["route"] == "next_skill"
    assert completed["answers"][0]["evidence_transition"] == "supported"


def test_agent_clarifies_once_then_preserves_unknown(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JOBAGENT_LANGGRAPH_DB_PATH", str(tmp_path / "graph.sqlite3"))
    agent = PreparationAgent()
    question = _question()
    agent.start("prep-clarify", [question])

    paused = agent.resume(
        "prep-clarify",
        [PreparationAnswer(
            question_id="q1",
            selected_option_id="python_uncertain",
            detail="My situation is different.",
        )],
        "complete",
        questions=[question],
    )
    assert paused["status"] == "paused"
    assert paused["answers"][0]["route"] == "clarify"

    completed = agent.resume(
        "prep-clarify",
        [PreparationAnswer.model_validate(paused["answers"][0])],
        "complete",
        questions=[question],
    )
    assert completed["status"] == "completed"
    assert completed["answers"][0]["evidence_transition"] == "unknown"
