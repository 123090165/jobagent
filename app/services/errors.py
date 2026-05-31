from __future__ import annotations


class JobAgentError(ValueError):
    """Base user-facing business error for JobAgent services and routes."""

    def __init__(self, message: str, error_code: str = "jobagent_error") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)
