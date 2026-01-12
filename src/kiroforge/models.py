from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class PowerMeta(BaseModel):
    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=10)
    version: str
    author: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None


class PowerTrigger(BaseModel):
    phrases: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)


class PowerConstraints(BaseModel):
    allowed_tools: List[str] = Field(default_factory=list)
    denied_tools: List[str] = Field(default_factory=list)
    sandbox_notes: Optional[str] = None
    requires_network: Optional[bool] = None


class PowerResources(BaseModel):
    steering_files: List[Path] = Field(default_factory=list)
    tools_files: List[Path] = Field(default_factory=list)
    hooks_files: List[Path] = Field(default_factory=list)
    assets: List[Path] = Field(default_factory=list)


class PowerTests(BaseModel):
    tests_path: Optional[Path] = None
    expected_behaviors: List[str] = Field(default_factory=list)


class PowerCompatibility(BaseModel):
    kiro_version: Optional[str] = None
    platforms: List[str] = Field(default_factory=list)


class PowerSpec(BaseModel):
    meta: PowerMeta
    triggers: PowerTrigger = Field(default_factory=PowerTrigger)
    constraints: PowerConstraints = Field(default_factory=PowerConstraints)
    resources: PowerResources = Field(default_factory=PowerResources)
    tests: PowerTests = Field(default_factory=PowerTests)
    compatibility: PowerCompatibility = Field(default_factory=PowerCompatibility)


# Agent Models

class AgentMeta(BaseModel):
    name: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")
    description: str = Field(..., min_length=10, max_length=500)
    version: str = Field(..., pattern="^\\d+\\.\\d+\\.\\d+$")
    author: Optional[str] = None


class AgentIdentity(BaseModel):
    prompt_file: str = Field(..., pattern="\\.md$")
    expertise: List[str] = Field(default_factory=list)


class AgentConstraints(BaseModel):
    allowed_tools: List[str] = Field(default_factory=list)
    denied_tools: List[str] = Field(default_factory=list)
    requires_network: bool = False
    opt_out_collection_constraints: bool = False
    opt_out_justification: Optional[str] = None

    @field_validator('opt_out_justification')
    @classmethod
    def validate_opt_out_justification(cls, v, info):
        if info.data.get('opt_out_collection_constraints') and not v:
            raise ValueError('opt_out_justification required when opt_out_collection_constraints is True')
        return v


class DelegationElevation(BaseModel):
    tool_pattern: str
    justification: str
    audit_level: str = Field(default="medium", pattern="^(low|medium|high)$")

    @field_validator('tool_pattern')
    @classmethod
    def validate_tool_pattern(cls, v):
        if v == "*":
            raise ValueError("Tool pattern '*' is too broad and dangerous")
        return v


class DelegationSecurity(BaseModel):
    constraint_intersection: bool = True
    audit_trail: bool = True
    require_justification: bool = False
    allow_full_delegation: bool = False
    justification: Optional[str] = None
    allowed_elevations: List[DelegationElevation] = Field(default_factory=list)

    @field_validator('justification')
    @classmethod
    def validate_justification(cls, v, info):
        if not info.data.get('constraint_intersection'):
            allow_full = info.data.get('allow_full_delegation', False)
            elevations = info.data.get('allowed_elevations', [])
            
            if allow_full and not v:
                raise ValueError('justification required when allow_full_delegation is True')
            elif not allow_full and not elevations:
                raise ValueError('constraint_intersection: false requires either allow_full_delegation: true + justification or non-empty allowed_elevations')
        return v


class AgentSubagents(BaseModel):
    allowed_specialists: List[str] = Field(default_factory=list)
    max_concurrent: int = Field(default=3, ge=1, le=10)
    delegation_rules: List[str] = Field(default_factory=list)
    delegation_security: DelegationSecurity = Field(default_factory=DelegationSecurity)

    @field_validator('allowed_specialists')
    @classmethod
    def validate_specialists(cls, v):
        for specialist in v:
            if not specialist.replace('-', '').replace('_', '').isalnum():
                raise ValueError(f"Invalid specialist name '{specialist}'. Use only letters, numbers, hyphens, and underscores.")
        return v


class AgentTests(BaseModel):
    test_path: str = "tests/"
    expected_behaviors: List[str] = Field(default_factory=list)


class AgentCompatibility(BaseModel):
    kiro_version: Optional[str] = Field(None, pattern="^>=\\d+\\.\\d+$")
    platforms: List[str] = Field(default_factory=list)


class PowerReference(BaseModel):
    """Enhanced power reference with collision resolution."""
    path: str = Field(..., pattern="^\\./.*")
    exclude_tools: List[str] = Field(default_factory=list)
    tool_aliases: dict[str, str] = Field(default_factory=dict)
    server_aliases: dict[str, str] = Field(default_factory=dict)
    exclude_steering_sections: List[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    meta: AgentMeta
    identity: AgentIdentity
    powers: List[Union[str, PowerReference]] = Field(min_length=1)
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)
    subagents: Optional[AgentSubagents] = None
    tests: AgentTests = Field(default_factory=AgentTests)
    compatibility: AgentCompatibility = Field(default_factory=AgentCompatibility)


# Collection Models

class CollectionMeta(BaseModel):
    name: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")
    description: str = Field(..., min_length=10)
    version: str = Field(..., pattern="^\\d+\\.\\d+\\.\\d+$")
    author: Optional[str] = None


class CollectionSharedContext(BaseModel):
    powers: List[str] = Field(default_factory=list)
    steering: List[str] = Field(default_factory=list)
    constraints: Optional[AgentConstraints] = None


class CollectionAgent(BaseModel):
    path: str = Field(..., pattern="^\\./.*")
    role: str = Field(..., pattern="^[a-zA-Z0-9_]+$")
    description: Optional[str] = None
    can_spawn_subagents: bool = False


class SharedMemoryConfig(BaseModel):
    enabled: bool = True
    scope: str = Field(default="collection", pattern="^(collection|workspace|global)$")


class CollectionCoordination(BaseModel):
    patterns: List[str] = Field(default_factory=list)
    shared_memory: Optional[SharedMemoryConfig] = None

    @field_validator('patterns')
    @classmethod
    def validate_patterns(cls, v):
        for pattern in v:
            if " -> " not in pattern:
                raise ValueError(f"Coordination pattern '{pattern}' must contain ' -> ' arrow")
        return v


class CollectionTestScenario(BaseModel):
    name: str
    description: str
    prompt: Optional[str] = None
    expected_flow: List[dict] = Field(default_factory=list)
    expected_outcomes: List[str] = Field(default_factory=list)
    subagent_calls: List[dict] = Field(default_factory=list)


class CollectionTests(BaseModel):
    test_path: str = "tests/"
    scenarios: List[CollectionTestScenario] = Field(default_factory=list)


class CollectionSpec(BaseModel):
    meta: CollectionMeta
    shared_context: CollectionSharedContext = Field(default_factory=CollectionSharedContext)
    agents: List[CollectionAgent] = Field(min_length=1)
    coordination: Optional[CollectionCoordination] = None
    tests: CollectionTests = Field(default_factory=CollectionTests)
    compatibility: AgentCompatibility = Field(default_factory=AgentCompatibility)