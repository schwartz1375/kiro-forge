from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class SteeringIssue:
    level: str
    message: str


@dataclass
class SteeringValidationResult:
    issues: list[SteeringIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def validate_steering(path: Path) -> SteeringValidationResult:
    issues: list[SteeringIssue] = []

    if not path.exists():
        issues.append(SteeringIssue("error", "Steering file not found"))
        return SteeringValidationResult(issues)

    if path.suffix.lower() != ".md":
        issues.append(SteeringIssue("warning", "Steering file should be .md"))

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        issues.append(SteeringIssue("error", "Steering file is empty"))
        return SteeringValidationResult(issues)

    has_heading = any(line.startswith("# ") for line in content.splitlines())
    if not has_heading:
        issues.append(SteeringIssue("warning", "Missing top-level heading (# ...)"))

    filename = path.name
    if not re.match(r"^[a-z0-9]+([-.][a-z0-9]+)*\\.md$", filename):
        issues.append(
            SteeringIssue(
                "warning",
                "Filename should be clear and kebab-case (e.g., api-standards.md)",
            )
        )

    lowered = content.lower()
    if not any(token in lowered for token in ["because", "why", "reason"]):
        issues.append(
            SteeringIssue(
                "warning",
                "Include context (why decisions were made), not just rules.",
            )
        )

    if "```" not in content:
        issues.append(
            SteeringIssue(
                "warning",
                "Provide examples (add code snippets or before/after comparisons).",
            )
        )

    if any(token in lowered for token in ["api key", "password", "secret", "token"]):
        issues.append(
            SteeringIssue(
                "error",
                "Potential secrets detected. Remove credentials from steering files.",
            )
        )

    return SteeringValidationResult(issues)
