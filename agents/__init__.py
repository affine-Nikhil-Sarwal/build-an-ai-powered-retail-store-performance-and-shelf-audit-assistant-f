"""Minimal agent_library framework seeded into generated codegen repos.

!!! BEST-EFFORT RECONSTRUCTION — NOT A VERIFIED COPY OF THE REAL FRAMEWORK !!!

The real ``agent_library`` base framework was NOT located anywhere in this
monorepo (searched repo-wide for ``class BaseAgent``, ``AgentExecutor``,
``AgentRegistry``, ``WorkflowExecutor``, ``AgentLoader``, ``ServiceContainer``,
``StubLLMClient``, ``get_logger`` — the only match is this file itself). The
symbols/signatures below were reconstructed from *observed usage* in the four
dependent catalog packages (document_ingestion, entity_extraction,
kyc_validator, missing_information_email_drafter). Treat this as a scaffolding
placeholder, not a source of truth.

Scope: this stub is import-only. It provides just enough for reuse agents to
``import`` and construct ``AgentMetadata`` after seeding under
``agent_library/reuse/<id>/``. It does NOT reproduce the runtime contract the
agents and their test suites actually exercise. Known-missing surface (proven
by running the packages' own tests/test_agent.py against this stub — all four
fail at collection with ``ImportError: cannot import name 'AgentExecutor'``):

  * Executor/registry/loader:   AgentExecutor, AgentRegistry, AgentLoader,
                                WorkflowExecutor, ExecutionStatus, WorkflowStatus
  * DI / config / logging:      Settings, get_logger, ServiceContainer
                                (agent_library.shared.container), StubLLMClient
                                (agent_library.shared.llm.azure_openai)
  * BaseAgent runtime methods:  .structured(context, system=, prompt=, schema=),
                                ._resolve_config(context)
  * ExecutionContext fields:    .logger, .settings, .correlation_id, .services
                                as a real ServiceContainer (not a plain dict)
  * AgentInput.of(**data)       constructor helper

Do not "fix" the tests by loosening them to match this stub. If the real
framework becomes available, replace this file wholesale.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from agents.base.metadata import IOField, IOFieldType

T = TypeVar("T")


class AgentKind(str, Enum):
    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"
    TOOL = "tool"


class Capability(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    question: str
    type: str = "string"
    required: bool = False
    maps_to: str | None = None


class ConfigurationParameter(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: IOFieldType = IOFieldType.STRING
    default: Any = None
    required: bool = False
    description: str = ""


class TriggerCondition(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str = ""
    when_keywords: list[str] = Field(default_factory=list)
    when_inputs_present: list[str] = Field(default_factory=list)


class WorkflowPattern(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    sequence: list[str] = Field(default_factory=list)


class Integration(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    required: bool = False


class AgentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_name: str
    version: str = "1.0"
    category: str = ""
    description: str = ""
    kind: AgentKind = AgentKind.RULE_BASED
    capabilities: list[Capability] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    business_use_cases: list[str] = Field(default_factory=list)
    required_inputs: list[Any] = Field(default_factory=list)
    produced_outputs: list[Any] = Field(default_factory=list)
    trigger_conditions: list[TriggerCondition] = Field(default_factory=list)
    compatible_agents: list[str] = Field(default_factory=list)
    enables_agents: list[str] = Field(default_factory=list)
    workflow_patterns: list[WorkflowPattern] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    configuration_parameters: list[ConfigurationParameter] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    integrations: list[Integration] = Field(default_factory=list)


class AgentInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    services: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentException(Exception):
    def __init__(self, message: str, *, agent: str | None = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.agent = agent
        self.details = kwargs


class ValidationException(AgentException):
    def __init__(
        self,
        message: str,
        *,
        phase: str | None = None,
        agent: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, agent=agent, phase=phase, **kwargs)
        self.phase = phase


class BaseAgent(Generic[T]):
    """Minimal base agent — subclasses override lifecycle hooks."""

    metadata: AgentMetadata

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config = kwargs.get("config")

    async def validate_input(self, agent_input: AgentInput) -> T:  # pragma: no cover
        raise NotImplementedError

    async def execute(self, payload: T, context: ExecutionContext) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    async def validate_output(self, result: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return result

    async def run(self, agent_input: AgentInput, context: ExecutionContext | None = None) -> dict[str, Any]:
        ctx = context or ExecutionContext()
        payload = await self.validate_input(agent_input)
        result = await self.execute(payload, ctx)
        return await self.validate_output(result, ctx)


class LLMAgent(BaseAgent[T]):
    """LLM-backed agent base (same surface as BaseAgent for seeding)."""


__all__ = [
    "AgentException",
    "AgentInput",
    "AgentKind",
    "AgentMetadata",
    "BaseAgent",
    "Capability",
    "ClarificationQuestion",
    "ConfigurationParameter",
    "ExecutionContext",
    "Integration",
    "IOField",
    "IOFieldType",
    "LLMAgent",
    "TriggerCondition",
    "ValidationException",
    "WorkflowPattern",
]
