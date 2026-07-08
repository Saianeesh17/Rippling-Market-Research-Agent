from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, prompt: str, *, system_prompt: str | None = None, json_mode: bool = False) -> str:
        raise NotImplementedError
