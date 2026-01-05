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
