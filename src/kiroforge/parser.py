from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .models import PowerSpec

# Security: Maximum file size for YAML files (1MB)
MAX_YAML_SIZE = 1024 * 1024


class PowerSpecError(Exception):
    """Base exception for power specification errors."""
    pass


class PowerSpecFormatError(PowerSpecError):
    """Raised when POWER.md has invalid format or structure."""
    pass


class PowerSpecSizeError(PowerSpecError):
    """Raised when POWER.md file is too large."""
    pass


def load_power_spec(path: Path) -> PowerSpec:
    """Load and validate a power specification from POWER.md file.
    
    Args:
        path: Path to the POWER.md file
        
    Returns:
        PowerSpec: Validated power specification
        
    Raises:
        PowerSpecSizeError: If file is too large
        PowerSpecFormatError: If YAML is invalid or schema validation fails
        FileNotFoundError: If file doesn't exist
        PermissionError: If file is not readable
    """
    if not path.exists():
        raise FileNotFoundError(f"POWER.md not found: {path}")
    
    if not path.is_file():
        raise PowerSpecFormatError(f"POWER.md is not a file: {path}")
    
    # Security: Check file size to prevent DoS attacks
    try:
        file_size = path.stat().st_size
    except (OSError, PermissionError) as exc:
        raise PermissionError(f"Cannot read POWER.md file: {exc}") from exc
    
    if file_size > MAX_YAML_SIZE:
        raise PowerSpecSizeError(
            f"POWER.md file too large: {file_size} bytes (max {MAX_YAML_SIZE})"
        )
    
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PowerSpecFormatError(f"Cannot read POWER.md as UTF-8: {exc}") from exc
    
    # Security: Additional check on content length after reading
    if len(raw) > MAX_YAML_SIZE:
        raise PowerSpecSizeError(
            f"POWER.md content too large: {len(raw)} characters (max {MAX_YAML_SIZE})"
        )
    
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise PowerSpecFormatError(f"Invalid YAML format: {exc}") from exc
    
    if not isinstance(data, dict):
        raise PowerSpecFormatError("POWER.md must contain a YAML object/dictionary")
    
    try:
        return PowerSpec.model_validate(data)
    except Exception as exc:
        raise PowerSpecFormatError(f"Invalid power specification schema: {exc}") from exc


def list_power_files(base: Path, patterns: Iterable[str]) -> list[Path]:
    """List files matching glob patterns, with security validation.
    
    Args:
        base: Base directory to search in
        patterns: Glob patterns to match
        
    Returns:
        List of matching file paths
    """
    if not base.exists() or not base.is_dir():
        return []
    
    results: list[Path] = []
    for pattern in patterns:
        # Security: Validate glob patterns to prevent path traversal
        if ".." in pattern or pattern.startswith("/"):
            continue
        try:
            results.extend(base.glob(pattern))
        except (OSError, ValueError):
            # Skip invalid patterns
            continue
    return results

# Agent and Collection Parsing

from .models import AgentSpec, CollectionSpec
import yaml
from pydantic import ValidationError

# Maximum file sizes for security
MAX_AGENT_SPEC_SIZE = 1024 * 1024  # 1MB
MAX_COLLECTION_SPEC_SIZE = 2 * 1024 * 1024  # 2MB


class AgentSpecError(Exception):
    """Base exception for agent specification errors."""
    pass


class AgentSpecFormatError(AgentSpecError):
    """Agent specification format error."""
    pass


class AgentSpecSizeError(AgentSpecError):
    """Agent specification size error."""
    pass


class CollectionSpecError(Exception):
    """Base exception for collection specification errors."""
    pass


class CollectionSpecFormatError(CollectionSpecError):
    """Collection specification format error."""
    pass


class CollectionSpecSizeError(CollectionSpecError):
    """Collection specification size error."""
    pass


def load_agent_spec(agent_dir: Path) -> AgentSpec:
    """Load and validate an agent specification from agent.yaml file.
    
    Args:
        agent_dir: Path to agent directory containing agent.yaml
        
    Returns:
        AgentSpec: Validated agent specification
        
    Raises:
        AgentSpecError: If specification is invalid
        AgentSpecFormatError: If YAML format is invalid
        AgentSpecSizeError: If file is too large
        FileNotFoundError: If agent.yaml doesn't exist
        PermissionError: If file cannot be read
    """
    agent_yaml = agent_dir / "agent.yaml"
    
    if not agent_yaml.exists():
        raise FileNotFoundError(f"Missing agent.yaml in {agent_dir}")
    
    # Security: Validate file size
    file_size = agent_yaml.stat().st_size
    if file_size > MAX_AGENT_SPEC_SIZE:
        raise AgentSpecSizeError(f"agent.yaml too large: {file_size} bytes (max: {MAX_AGENT_SPEC_SIZE})")
    
    try:
        with agent_yaml.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise AgentSpecFormatError("agent.yaml must contain a YAML object")
            
        return AgentSpec.model_validate(data)
        
    except yaml.YAMLError as exc:
        raise AgentSpecFormatError(f"Invalid YAML in agent.yaml: {exc}")
    except ValidationError as exc:
        raise AgentSpecError(f"Agent specification validation failed: {exc}")
    except PermissionError as exc:
        raise PermissionError(f"Cannot read agent.yaml: {exc}")


def load_collection_spec(collection_dir: Path) -> CollectionSpec:
    """Load and validate a collection specification from collection.yaml file.
    
    Args:
        collection_dir: Path to collection directory containing collection.yaml
        
    Returns:
        CollectionSpec: Validated collection specification
        
    Raises:
        CollectionSpecError: If specification is invalid
        CollectionSpecFormatError: If YAML format is invalid
        CollectionSpecSizeError: If file is too large
        FileNotFoundError: If collection.yaml doesn't exist
        PermissionError: If file cannot be read
    """
    collection_yaml = collection_dir / "collection.yaml"
    
    if not collection_yaml.exists():
        raise FileNotFoundError(f"Missing collection.yaml in {collection_dir}")
    
    # Security: Validate file size
    file_size = collection_yaml.stat().st_size
    if file_size > MAX_COLLECTION_SPEC_SIZE:
        raise CollectionSpecSizeError(f"collection.yaml too large: {file_size} bytes (max: {MAX_COLLECTION_SPEC_SIZE})")
    
    try:
        with collection_yaml.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise CollectionSpecFormatError("collection.yaml must contain a YAML object")
            
        return CollectionSpec.model_validate(data)
        
    except yaml.YAMLError as exc:
        raise CollectionSpecFormatError(f"Invalid YAML in collection.yaml: {exc}")
    except ValidationError as exc:
        raise CollectionSpecError(f"Collection specification validation failed: {exc}")
    except PermissionError as exc:
        raise PermissionError(f"Cannot read collection.yaml: {exc}")


def normalize_power_reference(power_ref: str | dict) -> dict:
    """Normalize power reference to standard format.
    
    Args:
        power_ref: Either a string path or PowerReference dict
        
    Returns:
        dict: Normalized power reference
    """
    if isinstance(power_ref, str):
        return {"path": power_ref}
    return power_ref