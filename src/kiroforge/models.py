from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


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
