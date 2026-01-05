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
