from __future__ import annotations

from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent


class PromptNotFoundError(FileNotFoundError):
    """Raised when a registered prompt file cannot be found."""


class PromptPathError(ValueError):
    """Raised when a prompt path is outside the prompt registry."""


def load_prompt(relative_path: str) -> str:
    """Load a UTF-8 prompt from app/prompts with basic path restrictions."""
    if not relative_path or Path(relative_path).is_absolute():
        raise PromptPathError("Prompt path must be a relative path inside app/prompts.")

    candidate = (PROMPTS_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(PROMPTS_ROOT)
    except ValueError as exc:
        raise PromptPathError("Prompt path must stay inside app/prompts.") from exc

    if not candidate.is_file():
        raise PromptNotFoundError(f"Prompt file not found: {relative_path}")
    return candidate.read_text(encoding="utf-8").strip()
