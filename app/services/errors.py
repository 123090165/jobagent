from __future__ import annotations


class JobAgentError(ValueError):
    """Base user-facing business error for JobAgent services and routes."""

    def __init__(
        self,
        message: str,
        error_code: str = "jobagent_error",
        status_code: int = 400,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)
