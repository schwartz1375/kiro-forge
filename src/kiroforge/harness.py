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
# Agent and Collection Testing

from .models import AgentSpec, CollectionSpec
from .parser import load_agent_spec, load_collection_spec
from .validator import validate_agent, validate_collection
import yaml


class AgentTestContext:
    """Test context for agent testing."""
    
    def __init__(self, agent_dir: Path, spec: AgentSpec):
        self.agent_dir = agent_dir
        self.spec = spec
        self.test_results = []
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """Add a test result."""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
    
    @property
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        return all(result["passed"] for result in self.test_results)


class CollectionTestContext:
    """Test context for collection testing."""
    
    def __init__(self, collection_dir: Path, spec: CollectionSpec):
        self.collection_dir = collection_dir
        self.spec = spec
        self.test_results = []
        self.agent_contexts = {}
    
    def add_agent_context(self, agent_name: str, context: AgentTestContext):
        """Add agent test context."""
        self.agent_contexts[agent_name] = context
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """Add a collection-level test result."""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
    
    @property
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        collection_passed = all(result["passed"] for result in self.test_results)
        agents_passed = all(ctx.all_passed for ctx in self.agent_contexts.values())
        return collection_passed and agents_passed


def load_agent_test_suite(agent_dir: Path) -> dict:
    """Load agent test suite from tests directory.
    
    Args:
        agent_dir: Path to agent directory
        
    Returns:
        dict: Test suite data
        
    Raises:
        FileNotFoundError: If test file doesn't exist
        yaml.YAMLError: If test file is invalid
    """
    test_file = agent_dir / "tests" / "test_responses.yaml"
    if not test_file.exists():
        raise FileNotFoundError(f"Test file not found: {test_file}")
    
    with test_file.open("r") as f:
        return yaml.safe_load(f)


def load_collection_test_suite(collection_dir: Path) -> dict:
    """Load collection test suite from tests directory.
    
    Args:
        collection_dir: Path to collection directory
        
    Returns:
        dict: Test suite data
        
    Raises:
        FileNotFoundError: If test file doesn't exist
        yaml.YAMLError: If test file is invalid
    """
    # Try multiple test file locations
    test_files = [
        collection_dir / "tests" / "test_scenarios.yaml",
        collection_dir / "tests" / "collection_tests.yaml",
        collection_dir / "tests" / "tests.yaml"
    ]
    
    for test_file in test_files:
        if test_file.exists():
            with test_file.open("r") as f:
                return yaml.safe_load(f)
    
    raise FileNotFoundError(f"No test file found in {collection_dir / 'tests'}")


def run_agent_tests(agent_dir: Path) -> AgentTestContext:
    """Run tests for an agent.
    
    Args:
        agent_dir: Path to agent directory
        
    Returns:
        AgentTestContext: Test results
    """
    # Load agent spec
    spec = load_agent_spec(agent_dir)
    context = AgentTestContext(agent_dir, spec)
    
    # Validate agent first
    validation_result = validate_agent(agent_dir)
    context.add_result(
        "Agent Validation",
        validation_result.ok,
        f"Validation issues: {len(validation_result.issues)}" if not validation_result.ok else "Valid"
    )
    
    # Load and run behavioral tests
    try:
        test_suite = load_agent_test_suite(agent_dir)
        
        # Run scenario tests
        scenarios = test_suite.get("scenarios", [])
        for scenario in scenarios:
            scenario_name = scenario.get("name", "Unnamed scenario")
            
            # Basic scenario validation
            has_prompt = "prompt" in scenario
            has_expected = "expected_behaviors" in scenario
            
            context.add_result(
                f"Scenario: {scenario_name}",
                has_prompt and has_expected,
                "Missing prompt or expected_behaviors" if not (has_prompt and has_expected) else "Valid scenario"
            )
            
            # TODO: Implement actual agent execution and behavior validation
            # This would involve:
            # 1. Loading the agent's system prompt and powers
            # 2. Executing the scenario prompt
            # 3. Validating the response against expected behaviors
            # 4. Checking constraint compliance
    
    except FileNotFoundError:
        context.add_result("Test Suite", False, "No test file found")
    except Exception as exc:
        context.add_result("Test Suite", False, f"Test loading failed: {exc}")
    
    return context


def run_collection_tests(collection_dir: Path) -> CollectionTestContext:
    """Run tests for a collection.
    
    Args:
        collection_dir: Path to collection directory
        
    Returns:
        CollectionTestContext: Test results
    """
    # Load collection spec
    spec = load_collection_spec(collection_dir)
    context = CollectionTestContext(collection_dir, spec)
    
    # Validate collection first
    validation_result = validate_collection(collection_dir)
    context.add_result(
        "Collection Validation",
        validation_result.ok,
        f"Validation issues: {len(validation_result.issues)}" if not validation_result.ok else "Valid"
    )
    
    # Test individual agents
    for agent_ref in spec.agents:
        agent_dir = collection_dir / agent_ref.path
        agent_name = Path(agent_ref.path).name
        
        if agent_dir.exists():
            agent_context = run_agent_tests(agent_dir)
            context.add_agent_context(agent_name, agent_context)
        else:
            # Create a failed context for missing agent
            missing_spec = AgentSpec(
                meta={"name": agent_name, "description": "Missing agent", "version": "0.0.0"},
                identity={"prompt_file": "missing.md"},
                powers=[]
            )
            agent_context = AgentTestContext(agent_dir, missing_spec)
            agent_context.add_result("Agent Exists", False, f"Agent directory not found: {agent_dir}")
            context.add_agent_context(agent_name, agent_context)
    
    # Load and run collection-specific tests
    try:
        test_suite = load_collection_test_suite(collection_dir)
        
        # Run multi-agent scenarios
        scenarios = test_suite.get("scenarios", [])
        for scenario in scenarios:
            scenario_name = scenario.get("name", "Unnamed scenario")
            
            # Basic scenario validation
            has_description = "description" in scenario
            has_expected_flow = "expected_flow" in scenario
            has_subagent_calls = "subagent_calls" in scenario
            
            scenario_valid = has_description and (has_expected_flow or has_subagent_calls)
            
            context.add_result(
                f"Multi-Agent Scenario: {scenario_name}",
                scenario_valid,
                "Missing required scenario fields" if not scenario_valid else "Valid scenario"
            )
            
            # Validate subagent call expectations
            if has_subagent_calls:
                subagent_calls = scenario["subagent_calls"]
                registered_agents = {Path(agent.path).name for agent in spec.agents}
                
                for call in subagent_calls:
                    agent_name = call.get("agent", "")
                    if agent_name not in registered_agents:
                        context.add_result(
                            f"Subagent Reference: {agent_name}",
                            False,
                            f"Agent '{agent_name}' not registered in collection"
                        )
                    else:
                        context.add_result(
                            f"Subagent Reference: {agent_name}",
                            True,
                            "Valid agent reference"
                        )
            
            # TODO: Implement actual multi-agent scenario execution
            # This would involve:
            # 1. Coordinating multiple agents
            # 2. Validating delegation patterns
            # 3. Checking shared context usage
            # 4. Verifying expected outcomes
    
    except FileNotFoundError:
        context.add_result("Collection Test Suite", False, "No collection test file found")
    except Exception as exc:
        context.add_result("Collection Test Suite", False, f"Test loading failed: {exc}")
    
    return context


def print_agent_test_results(context: AgentTestContext) -> None:
    """Print agent test results in a formatted way.
    
    Args:
        context: Agent test context with results
    """
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    console.print(f"\n[cyan]Agent Test Results: {context.spec.meta.name}[/cyan]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Test", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")
    
    for result in context.test_results:
        status = "[green]✓ PASS[/green]" if result["passed"] else "[red]✗ FAIL[/red]"
        table.add_row(result["test"], status, result["message"])
    
    console.print(table)
    
    if context.all_passed:
        console.print("[green]All tests passed![/green]")
    else:
        failed_count = sum(1 for r in context.test_results if not r["passed"])
        console.print(f"[red]{failed_count} test(s) failed[/red]")


def print_collection_test_results(context: CollectionTestContext) -> None:
    """Print collection test results in a formatted way.
    
    Args:
        context: Collection test context with results
    """
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    console.print(f"\n[cyan]Collection Test Results: {context.spec.meta.name}[/cyan]")
    
    # Collection-level results
    if context.test_results:
        table = Table(show_header=True, header_style="bold magenta", title="Collection Tests")
        table.add_column("Test", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Message", style="dim")
        
        for result in context.test_results:
            status = "[green]✓ PASS[/green]" if result["passed"] else "[red]✗ FAIL[/red]"
            table.add_row(result["test"], status, result["message"])
        
        console.print(table)
    
    # Agent-level results summary
    if context.agent_contexts:
        agent_table = Table(show_header=True, header_style="bold blue", title="Agent Test Summary")
        agent_table.add_column("Agent", style="dim")
        agent_table.add_column("Tests", justify="center")
        agent_table.add_column("Status", justify="center")
        
        for agent_name, agent_context in context.agent_contexts.items():
            test_count = len(agent_context.test_results)
            passed_count = sum(1 for r in agent_context.test_results if r["passed"])
            status = "[green]✓ PASS[/green]" if agent_context.all_passed else "[red]✗ FAIL[/red]"
            
            agent_table.add_row(agent_name, f"{passed_count}/{test_count}", status)
        
        console.print(agent_table)
    
    if context.all_passed:
        console.print("[green]All collection tests passed![/green]")
    else:
        collection_failed = sum(1 for r in context.test_results if not r["passed"])
        agent_failed = sum(1 for ctx in context.agent_contexts.values() if not ctx.all_passed)
        console.print(f"[red]{collection_failed} collection test(s) and {agent_failed} agent(s) failed[/red]")