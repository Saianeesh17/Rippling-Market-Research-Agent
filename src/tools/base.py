from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.schemas import ToolInput, ToolResult, ToolSpec


class BaseSourceTool(ABC):
    name: str
    description: str
    source_category: str
    reliability_weight: float
    requires_api_key: bool = False
    allowed_agents: List[str] = []

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            source_category=self.source_category,
            requires_api_key=self.requires_api_key,
            reliability_weight=self.reliability_weight,
            allowed_agents=self.allowed_agents,
        )

    @abstractmethod
    def run(self, tool_input: ToolInput) -> ToolResult:
        raise NotImplementedError

