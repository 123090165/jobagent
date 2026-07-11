from __future__ import annotations

from app.application.profile_session_usecases import get_profile_session
from app.repositories.confirmed_profile_repository import (
    ConfirmedProfileRepository,
    confirmed_profile_repository,
)
from app.repositories.profile_session_repository import (
    ProfileSessionRepository,
    profile_session_repository,
)
from app.repositories.search_mission_repository import (
    SearchMissionRepository,
    search_mission_repository,
)
from app.schemas.search_mission import SearchMission, SearchMissionInput
from app.services.errors import JobAgentError
from app.services.llm_provider import JSONChatLLM, resolve_llm_provider
from app.services.search_mission_interpreter import interpret_search_mission


def get_search_mission(
    session_id: str,
    *,
    user_id: str,
    sessions: ProfileSessionRepository = profile_session_repository,
    missions: SearchMissionRepository = search_mission_repository,
) -> SearchMission:
    get_profile_session(session_id, repository=sessions, user_id=user_id)
    mission = missions.get(user_id=user_id, session_id=session_id)
    if mission is None:
        raise _not_found()
    return mission


def save_search_mission_input(
    session_id: str,
    payload: SearchMissionInput,
    *,
    user_id: str,
    sessions: ProfileSessionRepository = profile_session_repository,
    missions: SearchMissionRepository = search_mission_repository,
) -> SearchMission:
    session = get_profile_session(session_id, repository=sessions, user_id=user_id)
    if session.confirmed_profile_id is None:
        raise JobAgentError(
            message="Confirmed profile is required before defining a search mission.",
            error_code="confirmed_profile_required",
            status_code=409,
        )
    return missions.save_input(
        user_id=user_id,
        session_id=session_id,
        confirmed_profile_id=session.confirmed_profile_id,
        payload=payload,
    )


def interpret_saved_search_mission(
    session_id: str,
    *,
    user_id: str,
    use_llm: bool,
    llm_provider: str,
    missions: SearchMissionRepository = search_mission_repository,
    profiles: ConfirmedProfileRepository = confirmed_profile_repository,
    llm_service: JSONChatLLM | None = None,
) -> SearchMission:
    mission = get_search_mission(session_id, user_id=user_id, missions=missions)
    profile = profiles.get(mission.confirmed_profile_id, user_id=user_id)
    if profile is None:
        raise JobAgentError(
            message="Confirmed profile not found.",
            error_code="confirmed_profile_not_found",
            status_code=404,
        )
    provider: str | None = None
    effective_llm = llm_service
    if use_llm and effective_llm is None:
        resolution = resolve_llm_provider(llm_provider)
        provider = resolution.provider
        effective_llm = resolution.service
    interpretation, mode, fallback_reason = interpret_search_mission(
        mission.input,
        profile,
        llm_service=effective_llm if use_llm else None,
    )
    return missions.save_interpretation(
        mission,
        interpretation=interpretation,
        analysis_mode=mode,
        analysis_provider=provider if mode in {"llm", "fallback"} else None,
        fallback_reason=fallback_reason,
    )


def confirm_search_mission(
    session_id: str,
    *,
    user_id: str,
    missions: SearchMissionRepository = search_mission_repository,
) -> SearchMission:
    mission = get_search_mission(session_id, user_id=user_id, missions=missions)
    if not mission.mission.target_roles:
        raise JobAgentError(
            message="At least one target role is required before confirmation.",
            error_code="search_mission_target_role_required",
            status_code=409,
        )
    return missions.confirm(mission)


def _not_found() -> JobAgentError:
    return JobAgentError(
        message="Search mission not found.",
        error_code="search_mission_not_found",
        status_code=404,
    )
