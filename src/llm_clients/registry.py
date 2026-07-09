# registry.py — loads models.yaml into ModelConfig objects. Pure data
# loading, no network calls, so it's testable without any model running.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_VALID_BACKENDS = {"openai_compatible", "anthropic"}


@dataclass
class ModelConfig:
    name: str                          # display name used in the CSV's `model` column
    backend: str                       # "openai_compatible" | "anthropic"
    model_id: str                      # the id sent to the API (e.g. "gemma4", "claude-sonnet-5")
    base_url: str | None = None        # required for openai_compatible; ignored for anthropic
    api_key_env: str | None = None     # env var name holding the API key; None for keyless local servers
    supports_tool_calling: bool = True  # default interaction_mode: tool_call vs text_block

    def __post_init__(self):
        if self.backend not in _VALID_BACKENDS:
            raise ValueError(f"{self.name}: unknown backend {self.backend!r}, "
                              f"must be one of {_VALID_BACKENDS}")
        if self.backend == "openai_compatible" and not self.base_url:
            raise ValueError(f"{self.name}: openai_compatible backend requires base_url")


def load_model_registry(path: str | Path) -> list[ModelConfig]:
    data = yaml.safe_load(Path(path).read_text())
    return [ModelConfig(**entry) for entry in data["models"]]
