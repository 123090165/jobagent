from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENV_FILE = ".env.deepseek.local"
ENV_FILE_OVERRIDE = "JOBAGENT_ENV_FILE"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_env(env_file: str | Path | None = None) -> Path | None:
    path = _resolve_env_file(env_file)
    if not path.exists() or not path.is_file():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        key_value = _parse_env_line(raw_line)
        if key_value is None:
            continue
        key, value = key_value
        os.environ.setdefault(key, value)
    return path


def _resolve_env_file(env_file: str | Path | None) -> Path:
    raw_path = env_file or os.getenv(ENV_FILE_OVERRIDE) or DEFAULT_ENV_FILE
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    if not key:
        return None

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value
