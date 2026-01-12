from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .parser import load_power_spec, PowerSpecError, PowerSpecFormatError, PowerSpecSizeError
from .security import validate_file_path, validate_tool_pattern
from .spdx import is_spdx_license


@dataclass
class ValidationIssue:
    level: str
    message: str


@dataclass
class ValidationResult:
    issues: list[ValidationIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def validate_power(power_dir: Path) -> ValidationResult:
    issues: list[ValidationIssue] = []
    spec_path = power_dir / "POWER.md"
    if not spec_path.exists():
        issues.append(ValidationIssue("error", "Missing POWER.md"))
        return ValidationResult(issues)

    try:
        spec = load_power_spec(spec_path)
    except PowerSpecSizeError as exc:
        issues.append(ValidationIssue("error", f"POWER.md file too large: {exc}"))
        return ValidationResult(issues)
    except PowerSpecFormatError as exc:
        issues.append(ValidationIssue("error", f"POWER.md format error: {exc}"))
        return ValidationResult(issues)
    except FileNotFoundError as exc:
        issues.append(ValidationIssue("error", f"POWER.md not found: {exc}"))
        return ValidationResult(issues)
    except PermissionError as exc:
        issues.append(ValidationIssue("error", f"Cannot read POWER.md: {exc}"))
        return ValidationResult(issues)
    except PowerSpecError as exc:
        issues.append(ValidationIssue("error", f"Power specification error: {exc}"))
        return ValidationResult(issues)

    if not re.match(r"^\d+\.\d+\.\d+$", spec.meta.version):
        issues.append(
            ValidationIssue(
                "error",
                f"Invalid version (expected semver MAJOR.MINOR.PATCH): {spec.meta.version}",
            )
        )

    if spec.meta.license and not is_spdx_license(spec.meta.license):
        issues.append(
            ValidationIssue(
                "warning",
                f"License is not a known SPDX identifier: {spec.meta.license}",
            )
        )

    # Security: Validate test path for path traversal
    if spec.tests.tests_path:
        if not validate_file_path(power_dir, spec.tests.tests_path):
            issues.append(ValidationIssue(
                "error", 
                f"Tests path outside power directory: {spec.tests.tests_path}"
            ))
        elif not (power_dir / spec.tests.tests_path).exists():
            issues.append(
                ValidationIssue("error", f"Missing tests path: {spec.tests.tests_path}")
            )

    # Security: Validate all resource file paths for path traversal
    for rel_path in spec.resources.steering_files:
        if not validate_file_path(power_dir, rel_path):
            issues.append(ValidationIssue(
                "error", 
                f"Steering file path outside power directory: {rel_path}"
            ))
        elif not (power_dir / rel_path).exists():
            issues.append(ValidationIssue("error", f"Missing steering file: {rel_path}"))

    for rel_path in spec.resources.tools_files:
        if not validate_file_path(power_dir, rel_path):
            issues.append(ValidationIssue(
                "error", 
                f"Tools file path outside power directory: {rel_path}"
            ))
        elif not (power_dir / rel_path).exists():
            issues.append(ValidationIssue("error", f"Missing tools file: {rel_path}"))

    for rel_path in spec.resources.hooks_files:
        if not validate_file_path(power_dir, rel_path):
            issues.append(ValidationIssue(
                "error", 
                f"Hooks file path outside power directory: {rel_path}"
            ))
        elif not (power_dir / rel_path).exists():
            issues.append(ValidationIssue("error", f"Missing hooks file: {rel_path}"))

    for rel_path in spec.resources.assets:
        if not validate_file_path(power_dir, rel_path):
            issues.append(ValidationIssue(
                "error", 
                f"Asset path outside power directory: {rel_path}"
            ))
        elif not (power_dir / rel_path).exists():
            issues.append(ValidationIssue("error", f"Missing asset: {rel_path}"))

    # Security: Validate tool patterns using centralized security module
    for pattern in spec.constraints.allowed_tools:
        is_valid, error_msg = validate_tool_pattern(pattern)
        if not is_valid:
            issues.append(ValidationIssue("error" if "Suspicious" in error_msg else "warning", error_msg))
    
    for pattern in spec.constraints.denied_tools:
        is_valid, error_msg = validate_tool_pattern(pattern)
        if not is_valid:
            issues.append(ValidationIssue("error" if "Suspicious" in error_msg else "warning", error_msg))

    overlap = set(spec.constraints.allowed_tools) & set(spec.constraints.denied_tools)
    if overlap:
        issues.append(
            ValidationIssue(
                "warning",
                "Tool patterns appear in both allowed_tools and denied_tools.",
            )
        )

    return ValidationResult(issues)

# Agent and Collection Validation

from .parser import load_agent_spec, load_collection_spec, AgentSpecError, CollectionSpecError, normalize_power_reference
from .models import AgentSpec, CollectionSpec, DelegationSecurity
import yaml


def validate_agent(agent_dir: Path) -> ValidationResult:
    """Validate an agent module directory.
    
    Args:
        agent_dir: Path to agent directory
        
    Returns:
        ValidationResult: Validation results with issues
    """
    issues: list[ValidationIssue] = []
    
    # Check agent.yaml exists
    agent_yaml = agent_dir / "agent.yaml"
    if not agent_yaml.exists():
        issues.append(ValidationIssue("error", "Missing agent.yaml"))
        return ValidationResult(issues)
    
    try:
        spec = load_agent_spec(agent_dir)
    except AgentSpecError as exc:
        issues.append(ValidationIssue("error", f"Agent specification error: {exc}"))
        return ValidationResult(issues)
    except FileNotFoundError as exc:
        issues.append(ValidationIssue("error", f"Agent file not found: {exc}"))
        return ValidationResult(issues)
    except PermissionError as exc:
        issues.append(ValidationIssue("error", f"Cannot read agent files: {exc}"))
        return ValidationResult(issues)
    
    # Validate system prompt file exists
    prompt_file = agent_dir / spec.identity.prompt_file
    if not prompt_file.exists():
        issues.append(ValidationIssue("error", f"Missing system prompt file: {spec.identity.prompt_file}"))
    elif not validate_file_path(agent_dir, Path(spec.identity.prompt_file)):
        issues.append(ValidationIssue("error", f"System prompt file path outside agent directory: {spec.identity.prompt_file}"))
    
    # Validate power dependencies
    for power_ref in spec.powers:
        power_data = normalize_power_reference(power_ref)
        power_path = power_data["path"]
        power_dir = agent_dir / power_path
        
        if not validate_file_path(agent_dir, Path(power_path)):
            issues.append(ValidationIssue("error", f"Power path outside agent directory: {power_path}"))
            continue
            
        if not power_dir.exists():
            issues.append(ValidationIssue("error", f"Missing power directory: {power_path}"))
            continue
        
        # Validate power using existing power validator
        power_result = validate_power(power_dir)
        if not power_result.ok:
            for issue in power_result.issues:
                issues.append(ValidationIssue(issue.level, f"Power {power_path}: {issue.message}"))
    
    # Validate delegation security
    if spec.subagents:
        issues.extend(_validate_delegation_security(spec.subagents.delegation_security))
        issues.extend(_validate_subagent_resolution(agent_dir, spec.subagents.allowed_specialists))
    
    # Validate constraints
    issues.extend(_validate_agent_constraints(spec.constraints))
    
    # Validate test path
    if spec.tests.test_path:
        test_path = agent_dir / spec.tests.test_path
        if not validate_file_path(agent_dir, Path(spec.tests.test_path)):
            issues.append(ValidationIssue("error", f"Test path outside agent directory: {spec.tests.test_path}"))
        elif not test_path.exists():
            issues.append(ValidationIssue("warning", f"Test directory does not exist: {spec.tests.test_path}"))
    
    return ValidationResult(issues)


def validate_collection(collection_dir: Path) -> ValidationResult:
    """Validate a collection directory and all its agents.
    
    Args:
        collection_dir: Path to collection directory
        
    Returns:
        ValidationResult: Validation results with issues
    """
    issues: list[ValidationIssue] = []
    
    # Check collection.yaml exists
    collection_yaml = collection_dir / "collection.yaml"
    if not collection_yaml.exists():
        issues.append(ValidationIssue("error", "Missing collection.yaml"))
        return ValidationResult(issues)
    
    try:
        spec = load_collection_spec(collection_dir)
    except CollectionSpecError as exc:
        issues.append(ValidationIssue("error", f"Collection specification error: {exc}"))
        return ValidationResult(issues)
    except FileNotFoundError as exc:
        issues.append(ValidationIssue("error", f"Collection file not found: {exc}"))
        return ValidationResult(issues)
    except PermissionError as exc:
        issues.append(ValidationIssue("error", f"Cannot read collection files: {exc}"))
        return ValidationResult(issues)
    
    # Validate shared powers
    for power_path in spec.shared_context.powers:
        power_dir = collection_dir / power_path
        if not validate_file_path(collection_dir, Path(power_path)):
            issues.append(ValidationIssue("error", f"Shared power path outside collection directory: {power_path}"))
            continue
            
        if not power_dir.exists():
            issues.append(ValidationIssue("error", f"Missing shared power directory: {power_path}"))
            continue
        
        # Validate shared power
        power_result = validate_power(power_dir)
        if not power_result.ok:
            for issue in power_result.issues:
                issues.append(ValidationIssue(issue.level, f"Shared power {power_path}: {issue.message}"))
    
    # Validate shared steering files
    for steering_path in spec.shared_context.steering:
        steering_file = collection_dir / steering_path
        if not validate_file_path(collection_dir, Path(steering_path)):
            issues.append(ValidationIssue("error", f"Shared steering file path outside collection directory: {steering_path}"))
        elif not steering_file.exists():
            issues.append(ValidationIssue("error", f"Missing shared steering file: {steering_path}"))
    
    # Validate all referenced agents
    agent_names = set()
    for agent_ref in spec.agents:
        agent_path = collection_dir / agent_ref.path
        agent_name = Path(agent_ref.path).name
        
        if not validate_file_path(collection_dir, Path(agent_ref.path)):
            issues.append(ValidationIssue("error", f"Agent path outside collection directory: {agent_ref.path}"))
            continue
            
        if not agent_path.exists():
            issues.append(ValidationIssue("error", f"Missing agent directory: {agent_ref.path}"))
            continue
        
        # Check for duplicate agent names
        if agent_name in agent_names:
            issues.append(ValidationIssue("error", f"Duplicate agent name: {agent_name}"))
        agent_names.add(agent_name)
        
        # Validate individual agent
        agent_result = validate_agent(agent_path)
        if not agent_result.ok:
            for issue in agent_result.issues:
                issues.append(ValidationIssue(issue.level, f"Agent {agent_name}: {issue.message}"))
    
    # Validate coordination patterns reference valid roles
    if spec.coordination:
        valid_roles = {agent.role for agent in spec.agents}
        for pattern in spec.coordination.patterns:
            if " -> " in pattern:
                _, target = pattern.split(" -> ", 1)
                target = target.strip()
                if target not in valid_roles and "spawns subagents" not in target:
                    issues.append(ValidationIssue("warning", f"Coordination pattern references unknown role: {target}"))
    
    # Validate collection constraints
    if spec.shared_context.constraints:
        issues.extend(_validate_agent_constraints(spec.shared_context.constraints))
    
    return ValidationResult(issues)


def _validate_delegation_security(security: DelegationSecurity) -> list[ValidationIssue]:
    """Validate delegation security configuration.
    
    Args:
        security: DelegationSecurity configuration
        
    Returns:
        list[ValidationIssue]: List of validation issues
    """
    issues = []
    
    if not security.constraint_intersection:
        # Require explicit intent when disabling intersection
        if not security.allow_full_delegation and not security.allowed_elevations:
            issues.append(ValidationIssue(
                "error",
                "constraint_intersection: false requires either allow_full_delegation: true + justification or non-empty allowed_elevations"
            ))
        
        if security.allow_full_delegation and not security.justification:
            issues.append(ValidationIssue(
                "error", 
                "allow_full_delegation: true requires justification field"
            ))
        
        # Audit trail cannot be disabled when intersection is disabled
        if not security.audit_trail:
            issues.append(ValidationIssue(
                "error",
                "audit_trail cannot be disabled when constraint_intersection: false"
            ))
    
    # Validate elevations
    for elevation in security.allowed_elevations:
        if elevation.tool_pattern == "*":
            issues.append(ValidationIssue(
                "error",
                f"Elevation pattern '*' is too broad and dangerous"
            ))
        elif elevation.tool_pattern.count("*") > 2:
            issues.append(ValidationIssue(
                "warning",
                f"Elevation pattern '{elevation.tool_pattern}' may be too broad"
            ))
    
    return issues


def _validate_subagent_resolution(agent_dir: Path, specialists: list[str]) -> list[ValidationIssue]:
    """Validate subagent specialist resolution.
    
    Args:
        agent_dir: Path to agent directory
        specialists: List of specialist names to validate
        
    Returns:
        list[ValidationIssue]: List of validation issues
    """
    issues = []
    
    # Check if in collection context
    collection_yaml = agent_dir.parent.parent / "collection.yaml"
    if collection_yaml.exists():
        # Collection context: validate against collection registry
        issues.extend(_validate_collection_subagents(collection_yaml, specialists))
    else:
        # Standalone context: validate sibling directories
        issues.extend(_validate_standalone_subagents(agent_dir, specialists))
    
    return issues


def _validate_standalone_subagents(agent_dir: Path, specialists: list[str]) -> list[ValidationIssue]:
    """Validate subagents in standalone context (sibling directories).
    
    Args:
        agent_dir: Path to agent directory
        specialists: List of specialist names
        
    Returns:
        list[ValidationIssue]: List of validation issues
    """
    issues = []
    agents_dir = agent_dir.parent
    available_agents = []
    
    # Find available sibling agents
    if agents_dir.exists():
        for item in agents_dir.iterdir():
            if item.is_dir() and item != agent_dir and (item / "agent.yaml").exists():
                available_agents.append(item.name)
    
    for specialist in specialists:
        specialist_dir = agents_dir / specialist
        if not specialist_dir.exists():
            issues.append(ValidationIssue(
                "error",
                f"Sibling agent '{specialist}' not found at {specialist_dir.relative_to(agent_dir.parent.parent)}. Available: {', '.join(sorted(available_agents))}"
            ))
        elif not (specialist_dir / "agent.yaml").exists():
            issues.append(ValidationIssue(
                "error",
                f"Agent '{specialist}' found but missing agent.yaml"
            ))
    
    return issues


def _validate_collection_subagents(collection_yaml: Path, specialists: list[str]) -> list[ValidationIssue]:
    """Validate subagents in collection context.
    
    Args:
        collection_yaml: Path to collection.yaml file
        specialists: List of specialist names
        
    Returns:
        list[ValidationIssue]: List of validation issues
    """
    issues = []
    
    try:
        with collection_yaml.open("r") as f:
            collection_data = yaml.safe_load(f)
        
        # Extract agent names from collection registry
        registered_agents = set()
        for agent in collection_data.get("agents", []):
            agent_path = Path(agent["path"])
            agent_name = agent_path.name
            registered_agents.add(agent_name)
        
        for specialist in specialists:
            if specialist not in registered_agents:
                issues.append(ValidationIssue(
                    "error",
                    f"Agent '{specialist}' not found in collection registry. Available: {', '.join(sorted(registered_agents))}"
                ))
    
    except Exception as exc:
        issues.append(ValidationIssue("error", f"Failed to validate collection registry: {exc}"))
    
    return issues


def _validate_agent_constraints(constraints: 'AgentConstraints') -> list[ValidationIssue]:
    """Validate agent constraints.
    
    Args:
        constraints: AgentConstraints to validate
        
    Returns:
        list[ValidationIssue]: List of validation issues
    """
    issues = []
    
    # Validate tool patterns using existing security module
    for pattern in constraints.allowed_tools:
        is_valid, error_msg = validate_tool_pattern(pattern)
        if not is_valid:
            issues.append(ValidationIssue("error" if "Suspicious" in error_msg else "warning", error_msg))
    
    for pattern in constraints.denied_tools:
        is_valid, error_msg = validate_tool_pattern(pattern)
        if not is_valid:
            issues.append(ValidationIssue("error" if "Suspicious" in error_msg else "warning", error_msg))
    
    # Check for overlapping patterns
    overlap = set(constraints.allowed_tools) & set(constraints.denied_tools)
    if overlap:
        issues.append(ValidationIssue(
            "warning",
            f"Tool patterns appear in both allowed_tools and denied_tools: {', '.join(overlap)}"
        ))
    
    return issues