from __future__ import annotations

import os

from app.config.env_loader import load_local_env


def test_load_local_env_reads_key_values_without_overwriting(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env.deepseek.local"
    env_file.write_text(
        "\n".join(
            [
                "# local secrets",
                "DEEPSEEK_API_KEY=file-key",
                "DEEPSEEK_MODEL=\"deepseek-v4-flash\"",
                "export OLLAMA_MODEL='qwen2.5:1.5b'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    loaded_path = load_local_env(env_file)

    assert loaded_path == env_file
    assert loaded_path.name == ".env.deepseek.local"
    assert os.environ["DEEPSEEK_API_KEY"] == "existing-key"
    assert os.environ["DEEPSEEK_MODEL"] == "deepseek-v4-flash"
    assert os.environ["OLLAMA_MODEL"] == "qwen2.5:1.5b"


def test_load_local_env_missing_file_is_noop(tmp_path) -> None:
    assert load_local_env(tmp_path / "missing.env") is None
