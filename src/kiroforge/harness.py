from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PowerContext:
    __test__ = False
    name: str
    steering_files: list[str]
    tools_files: list[str]
    hooks_files: list[str]
    allowed_tools: list[str]
    denied_tools: list[str]
    requires_network: bool | None


@dataclass
class TestCase:
    __test__ = False
    name: str
    prompt: str
    expected: list[str]


@dataclass
class TestSuite:
    __test__ = False
    cases: list[TestCase]


@dataclass
class TestResult:
    __test__ = False
    name: str
    status: str
    message: str


def load_test_suite(path: Path) -> TestSuite:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    cases = [TestCase(**case) for case in data.get("cases", [])]
    return TestSuite(cases=cases)


def _build_output(case: TestCase, context: PowerContext | None) -> str:
    if context is None:
        return case.prompt

    lines = [
        f"power: {context.name}",
        f"prompt: {case.prompt}",
        f"steering_files: {', '.join(context.steering_files) or 'none'}",
        f"tools_files: {', '.join(context.tools_files) or 'none'}",
        f"hooks_files: {', '.join(context.hooks_files) or 'none'}",
        f"allowed_tools: {', '.join(context.allowed_tools) or 'none'}",
        f"denied_tools: {', '.join(context.denied_tools) or 'none'}",
        f"requires_network: {context.requires_network}",
    ]
    return "\n".join(lines)


def run_suite(suite: TestSuite, context: PowerContext | None = None) -> list[TestResult]:
    results: list[TestResult] = []
    for case in suite.cases:
        if not case.prompt.strip():
            results.append(TestResult(case.name, "fail", "Missing prompt"))
            continue
        if not case.expected:
            results.append(TestResult(case.name, "fail", "Missing expected assertions"))
            continue
        output = _build_output(case, context)
        missing = [text for text in case.expected if text not in output]
        if missing:
            results.append(
                TestResult(
                    case.name,
                    "fail",
                    f"Missing expected text: {', '.join(missing)}",
                )
            )
            continue
        results.append(TestResult(case.name, "pass", "Assertions passed"))
    return results
