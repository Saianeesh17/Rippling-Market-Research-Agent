from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        raise NotImplementedError

