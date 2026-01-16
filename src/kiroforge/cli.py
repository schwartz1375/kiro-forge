from __future__ import annotations

from pathlib import Path
import subprocess
import shutil
import re
import shlex

import typer
from rich.console import Console
from rich.table import Table

from .executor import run_prompt
from .harness import PowerContext, load_test_suite, run_suite
from .parser import load_power_spec, load_agent_spec, load_collection_spec, AgentSpecError, CollectionSpecError
from .router import select_powers
from .security import validate_command_input, validate_identifier, redact_secrets
from .steering import validate_steering as run_steering_validation
from .templates import get_steering_templates, TemplateError, TemplateNotFoundError
from .config import get_config, ConfigManager
from .validator import validate_power
from .validator import validate_agent as validator_validate_agent
from .validator import validate_collection as validator_validate_collection
from .exporter import export_agent_to_kiro_json, export_collection_to_kiro_json, save_agent_export, save_collection_export, ExportError

app = typer.Typer(help="KiroForge CLI")
console = Console()

def _parse_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def _steering_templates(template_type: str) -> dict[str, str]:
    """Get steering templates using the template manager."""
    try:
        return get_steering_templates(template_type)
    except (TemplateError, TemplateNotFoundError) as exc:
        console.print(f"[red]Template error: {exc}[/red]")
        # Fallback to minimal template
        return {"steering.md": "# Steering\n\nAdd steering guidance here.\n"}


def _steering_headings(filename: str) -> list[str]:
    mapping = {
        "api-standards.md": [
            "API Standards",
            "Error Handling",
            "Authentication",
            "Examples",
        ],
        "testing-standards.md": [
            "Testing Approach",
            "Tooling",
            "Coverage",
            "Examples",
        ],
        "code-conventions.md": [
            "Code Style",
            "Naming",
            "Structure",
            "Examples",
        ],
        "security-policies.md": [
            "Security Guidelines",
            "Input Validation",
            "Secrets Handling",
            "Examples",
        ],
        "deployment-workflow.md": [
            "Deployment Process",
            "Environments",
            "Rollback",
            "Examples",
        ],
        "product.md": [
            "Product Overview",
            "Target Users",
            "Goals",
            "Examples",
        ],
        "tech.md": [
            "Technology Stack",
            "Dependencies",
            "Constraints",
            "Examples",
        ],
        "structure.md": [
            "Project Structure",
            "Naming",
            "Imports",
            "Examples",
        ],
    }
    return mapping.get(filename, ["Guidance", "Examples"])


def _clean_kiro_output(output: str) -> str:
    """Clean kiro-cli output by removing UI elements, banners, and artifacts."""
    if not output:
        return output
    
    # Remove all ANSI escape sequences (colors, formatting, cursor control)
    text = re.sub(r'\x1b\[[0-9;]*[mK]', '', output)
    text = re.sub(r'\x1b\[[?]?[0-9]*[hlABCDEFGJKST]', '', text)
    text = re.sub(r'\[38;5;[0-9]+m', '', text)
    text = re.sub(r'\[0m', '', text)
    text = re.sub(r'\[1m', '', text)
    
    lines = text.split('\n')
    cleaned_lines = []
    content_started = False
    in_code_block = False
    code_block_lang = None
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines at the beginning
        if not content_started and not stripped:
            continue
            
        # Skip kiro-cli UI elements
        if any(pattern in stripped for pattern in [
            'WARNING:', 'Model:', 'Plan:', 'Credits:', 'Did you know?',
            '╭─', '╰─', '│', '▸', '⠀', '⢀', '⢰', '⢸', '⠸', '> #'
        ]):
            continue
            
        # Skip lines that are just prompt characters or artifacts
        if re.match(r'^[>\s]*$', stripped):
            continue
            
        # Skip lines with mostly special characters (ASCII art remnants)
        if stripped and len(re.sub(r'[^\w\s#*`\-\[\]{}().,;:!?"/=]', '', stripped)) < len(stripped) * 0.4:
            continue
            
        # Handle code blocks
        if stripped.startswith('```'):
            if not in_code_block:
                # Starting a code block
                in_code_block = True
                code_block_lang = stripped[3:].strip() or 'text'
                cleaned_lines.append(f'```{code_block_lang}')
                content_started = True
            else:
                # Ending a code block
                in_code_block = False
                code_block_lang = None
                cleaned_lines.append('```')
            continue
            
        # If we're in a code block, include the line as-is (but cleaned)
        if in_code_block:
            cleaned_lines.append(line.rstrip())
            continue
            
        # Detect language indicators that should start code blocks
        if stripped in ['json', 'http', 'python', 'bash', 'yaml'] and not in_code_block:
            in_code_block = True
            code_block_lang = stripped
            cleaned_lines.append(f'```{stripped}')
            content_started = True
            continue
            
        # Start capturing content when we see markdown
        if not content_started and (
            stripped.startswith('#') or
            stripped.startswith('- ') or
            any(word in stripped.lower() for word in ['api', 'standards', 'error', 'auth', 'example', 'overview', 'this document'])
        ):
            content_started = True
            
        if content_started:
            # Clean up the line
            clean_line = line.rstrip()
            
            # Fix broken JSON/incomplete lines
            if not in_code_block and stripped and not any([
                stripped.startswith('#'),
                stripped.startswith('-'),
                stripped.startswith('*'),
                len(stripped.split()) > 2,  # Has at least 3 words
                stripped.endswith(':'),
                stripped.endswith('.'),
                stripped.endswith(','),
                stripped.endswith('}'),
                stripped.endswith(']'),
                stripped.endswith(')'),
                '"' in stripped,  # Likely part of JSON
                stripped.startswith('Authorization:'),
                stripped.startswith('Content-Type:'),
                stripped.startswith('POST ') or stripped.startswith('GET ') or stripped.startswith('PUT '),
            ]):
                continue
                
            cleaned_lines.append(clean_line)
    
    # Close any open code blocks
    if in_code_block:
        cleaned_lines.append('```')
    
    # Join and final cleanup
    result = '\n'.join(cleaned_lines).strip()
    
    # Remove multiple consecutive empty lines
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    # Remove remaining terminal control sequences
    result = re.sub(r'\[?\?25[lh]', '', result)
    result = re.sub(r'\x1b\[.*?[A-Za-z]', '', result)
    
    # Fix common markdown issues
    result = re.sub(r'^> # ', '# ', result, flags=re.MULTILINE)  # Remove quote from headers
    result = re.sub(r'\n([A-Z][a-z]+:)\n', r'\n\n\1\n', result)  # Add spacing around headers like "Response:"
    
    return result


def _normalize_steering_content(filename: str, content: str) -> str:
    headings = _steering_headings(filename)
    title = headings[0]
    
    # Clean kiro-cli output artifacts
    text = _clean_kiro_output(content)
    
    if not text:
        text = f"# {title}\n\n## Guidance\n\nTODO\n\n## Examples\n\n```text\nTODO\n```\n"
        return text

    if text.lstrip().startswith("# "):
        lines = text.splitlines()
        lines[0] = f"# {title}"
        text = "\n".join(lines)
    else:
        text = f"# {title}\n\n{text}"

    lowered = text.lower()
    for heading in headings:
        if heading == title:
            continue
        if f"## {heading}".lower() not in lowered:
            text += f"\n\n## {heading}\n\nTODO\n"
    if "```" not in text:
        text += "\n\n```text\nTODO\n```\n"
    text = _normalize_code_fences(text)
    text = _redact_secrets(text)
    return text


# Removed _multi_file_prompt and _parse_multi_output functions
# Always use single-file generation for reliability


def _normalize_code_fences(text: str) -> str:
    lines = text.splitlines()
    result: list[str] = []
    in_fence = False
    fence_langs = {"json", "http", "bash", "shell", "javascript", "yaml", "yml"}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip().lower()
        if stripped.startswith("```"):
            in_fence = not in_fence
            result.append(line)
            i += 1
            continue
        if not in_fence and stripped in fence_langs:
            result.append(f"```{stripped}")
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                result.append(lines[i])
                i += 1
            result.append("```")
            continue
        result.append(line)
        i += 1
    return "\n".join(result)


def _redact_secrets(text: str) -> str:
    """Use centralized secret redaction from security module."""
    return redact_secrets(text)


def _select_steering_files(
    templates: dict[str, str], selection: list[str] | None
) -> dict[str, str]:
    if selection:
        picked = {name: templates[name] for name in selection if name in templates}
        return picked if picked else templates
    return templates


def _write_steering_templates(
    base_dir: Path, template_type: str, selection: list[str] | None = None
) -> list[str]:
    templates = _steering_templates(template_type)
    files = _select_steering_files(templates, selection)
    base_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name, content in files.items():
        path = base_dir / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        created.append(name)
    return created


def _wizard_template_content(title: str, questions: list[tuple[str, str]]) -> str:
    lines = [f"# {title}\n"]
    for heading, prompt in questions:
        answer = typer.prompt(prompt, default="")
        lines.append(f"## {heading}\n")
        if answer.strip():
            lines.append(f"{answer}\n")
        else:
            lines.append("TODO\n")
        example = typer.prompt("Example (optional)", default="")
        if example.strip():
            lines.append("\n```text\n")
            lines.append(f"{example}\n")
            lines.append("```\n")
    return "\n".join(lines)


def _generate_with_kiro(
    prompt: str,
    no_interactive: bool = True,
    trust_all: bool = False,
    trust_tools: list[str] | None = None,
    timeout_seconds: int = 60,
    debug: bool = False,
    trust_none: bool = False,
    wrap: str | None = None,
    agent: str | None = None,
    model: str | None = None,
    use_pty: bool = False,
) -> str:
    # Security: Validate prompt input using centralized security module
    validate_command_input(prompt)
    
    command = ["kiro-cli", "chat"]
    if no_interactive:
        command.append("--no-interactive")
    if agent:
        # Security: Validate agent name format
        if not validate_identifier(agent):
            raise ValueError("Invalid agent name format")
        command.append(f"--agent={agent}")
    if model:
        # Security: Validate model name format
        if not validate_identifier(model, r'^[a-zA-Z0-9_.-]+$'):
            raise ValueError("Invalid model name format")
        command.append(f"--model={model}")
    if trust_all:
        command.append("--trust-all-tools")
    elif trust_none:
        command.append("--trust-tools=")
    elif trust_tools is not None:
        # Security: Validate tool names
        for tool in trust_tools:
            if not validate_identifier(tool, r'^[a-zA-Z0-9_.-]+$'):
                raise ValueError(f"Invalid tool name format: {tool}")
        command.append(f"--trust-tools={','.join(trust_tools)}")
    if wrap:
        if wrap not in {"auto", "never", "always"}:
            raise ValueError("Invalid wrap mode")
        command.append(f"--wrap={wrap}")
    
    # Security: Use shlex.quote to safely handle the prompt
    command.append(shlex.quote(prompt))

    if debug:
        console.print(f"[cyan]kiro-cli[/cyan] {' '.join(command)}")

    stdin = subprocess.DEVNULL if no_interactive else None
    
    # Security: Ensure proper cleanup and resource management
    process = None
    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=stdin,
        )
    except subprocess.TimeoutExpired as exc:
        # Security: Simplified timeout handling to avoid resource leaks
        if process:
            try:
                process.kill()
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        
        if use_pty:
            output = _run_with_pty(command, timeout_seconds)
            if output:
                return output
        raise RuntimeError(
            f"kiro-cli timed out after {timeout_seconds}s.\n"
            f"Actionable steps:\n"
            f"• Increase timeout: --kiro-timeout {timeout_seconds * 2}\n"
            f"• Disable tools: --kiro-trust-none\n"
            f"• Disable wrapping: --kiro-wrap never\n"
            f"• Try interactive mode: --kiro-interactive\n"
            f"• Use simpler prompts or single-file generation"
        ) from exc
    
    if process.returncode == 0:
        return process.stdout.strip()

    if "unexpected argument '--no-interactive'" in process.stderr:
        retry = ["kiro-cli", "chat"]
        if agent:
            retry.append(f"--agent={agent}")
        if model:
            retry.append(f"--model={model}")
        if trust_all:
            retry.append("--trust-all-tools")
        elif trust_tools is not None:
            retry.append(f"--trust-tools={','.join(trust_tools)}")
        retry.append(shlex.quote(prompt))  # Security: Quote prompt in retry too
        
        retry_process = None
        try:
            retry_process = subprocess.run(
                retry,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=stdin,
            )
        except subprocess.TimeoutExpired as exc:
            if retry_process:
                try:
                    retry_process.kill()
                    retry_process.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    pass
            
            if use_pty:
                output = _run_with_pty(retry, timeout_seconds)
                if output:
                    return output
        if retry_process.returncode == 0:
            return retry_process.stdout.strip()
        raise RuntimeError(
            retry_process.stderr.strip() or retry_process.stdout.strip() or "kiro-cli failed"
        )

    if "Tool approval required" in process.stderr and no_interactive:
        retry = ["kiro-cli", "chat"]
        if agent:
            retry.append(f"--agent={agent}")
        if model:
            retry.append(f"--model={model}")
        retry.append(shlex.quote(prompt))  # Security: Quote prompt in retry
        
        fallback_process = None
        try:
            fallback_process = subprocess.run(
                retry,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=stdin,
            )
        except subprocess.TimeoutExpired as exc:
            if fallback_process:
                try:
                    fallback_process.kill()
                    fallback_process.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    pass
            
            if use_pty:
                output = _run_with_pty(retry, timeout_seconds)
                if output:
                    return output
            raise RuntimeError(
                f"kiro-cli timed out after {timeout_seconds}s.\n"
                f"Actionable steps:\n"
                f"• Increase timeout: --kiro-timeout {timeout_seconds * 2}\n"
                f"• Disable tools: --kiro-trust-none\n"
                f"• Disable wrapping: --kiro-wrap never\n"
                f"• Try interactive mode: --kiro-interactive\n"
                f"• Use simpler prompts or single-file generation"
            ) from exc
        
        if fallback_process.returncode == 0:
            return fallback_process.stdout.strip()
        raise RuntimeError(
            fallback_process.stderr.strip() or fallback_process.stdout.strip() or "kiro-cli failed"
        )

    raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "kiro-cli failed")


def _run_with_pty(command: list[str], timeout_seconds: int) -> str:
    script = shutil.which("script")
    if not script:
        return ""
    
    # Security: Improved timeout handling with proper cleanup
    process = None
    try:
        process = subprocess.run(
            [script, "-q", "/dev/null", *command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        # Security: Ensure process cleanup on timeout
        if process:
            try:
                process.kill()
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        return ""
    except Exception:
        # Security: Handle any other subprocess errors gracefully
        if process:
            try:
                process.kill()
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        return ""
    
    if process.returncode != 0:
        return ""
    return process.stdout.strip()


@app.command()
def validate(path: Path = typer.Argument(..., help="Path to a power directory")) -> None:
    result = validate_power(path)
    if result.ok:
        console.print("[green]OK[/green]")
        return

    table = Table(title="Validation Issues")
    table.add_column("Level")
    table.add_column("Message")
    for issue in result.issues:
        table.add_row(issue.level, issue.message)
    console.print(table)
    raise typer.Exit(code=1)


@app.command()
def validate_steering(
    path: Path = typer.Argument(..., help="Path to a steering markdown file")
) -> None:
    result = run_steering_validation(path)
    if result.ok:
        console.print("[green]OK[/green]")
        return

    table = Table(title="Steering Validation Issues")
    table.add_column("Level")
    table.add_column("Message")
    for issue in result.issues:
        table.add_row(issue.level, issue.message)
    console.print(table)
    raise typer.Exit(code=1)


@app.command()
def run_tests(
    path: Path = typer.Argument(..., help="Path to power directory or test suite YAML")
) -> None:
    if path.is_dir():
        spec_path = path / "POWER.md"
        if not spec_path.exists():
            console.print("[red]POWER.md not found in directory[/red]")
            raise typer.Exit(code=1)
        spec = load_power_spec(spec_path)
        if not spec.tests.tests_path:
            console.print("[yellow]No tests_path defined in POWER.md[/yellow]")
            raise typer.Exit(code=1)
        suite_path = path / spec.tests.tests_path
        context = PowerContext(
            name=spec.meta.name,
            steering_files=[str(p) for p in spec.resources.steering_files],
            tools_files=[str(p) for p in spec.resources.tools_files],
            hooks_files=[str(p) for p in spec.resources.hooks_files],
            allowed_tools=spec.constraints.allowed_tools,
            denied_tools=spec.constraints.denied_tools,
            requires_network=spec.constraints.requires_network,
        )
    else:
        suite_path = path
        context = None

    suite = load_test_suite(suite_path)
    results = run_suite(suite, context=context)
    failed = [result for result in results if result.status != "pass"]
    for result in results:
        color = "green" if result.status == "pass" else "red"
        console.print(f"[{color}]{result.status}[/] {result.name}: {result.message}")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def run(
    power_dir: Path = typer.Argument(..., help="Path to a power directory"),
    prompt: str = typer.Argument(..., help="Prompt to execute"),
) -> None:
    spec_path = power_dir / "POWER.md"
    if not spec_path.exists():
        console.print("[red]POWER.md not found in directory[/red]")
        raise typer.Exit(code=1)

    spec = load_power_spec(spec_path)
    context = PowerContext(
        name=spec.meta.name,
        steering_files=[str(p) for p in spec.resources.steering_files],
        tools_files=[str(p) for p in spec.resources.tools_files],
        hooks_files=[str(p) for p in spec.resources.hooks_files],
        allowed_tools=spec.constraints.allowed_tools,
        denied_tools=spec.constraints.denied_tools,
        requires_network=spec.constraints.requires_network,
    )
    result = run_prompt(prompt, context)
    console.print(result.output)


@app.command()
def init(
    path: Path = typer.Argument(..., help="Directory to create the new power in"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt for metadata and generate a customized scaffold",
    ),
    kiro_no_interactive: bool = typer.Option(
        True,
        "--kiro-no-interactive/--kiro-interactive",
        help="Run kiro-cli without prompts (ai mode)",
    ),
    kiro_trust_all: bool = typer.Option(
        False,
        "--kiro-trust-all",
        help="Allow all tools when calling kiro-cli (ai mode)",
    ),
    kiro_trust_tools: list[str] = typer.Option(
        None,
        "--kiro-trust-tools",
        help="Allow specific tools when calling kiro-cli (repeatable)",
    ),
    kiro_trust_none: bool = typer.Option(
        False,
        "--kiro-trust-none",
        help="Disallow all tools when calling kiro-cli (ai mode)",
    ),
    kiro_wrap: str = typer.Option(
        "auto",
        "--kiro-wrap",
        help="kiro-cli wrap mode: auto, never, or always (ai mode)",
    ),
    kiro_agent: str = typer.Option(
        None,
        "--kiro-agent",
        help="Agent profile to use with kiro-cli (ai mode)",
    ),
    kiro_model: str = typer.Option(
        None,
        "--kiro-model",
        help="Model name to use with kiro-cli (ai mode)",
    ),
    kiro_timeout: int = typer.Option(
        60,
        "--kiro-timeout",
        help="Timeout for kiro-cli calls in seconds (ai mode)",
    ),
    kiro_pty: bool = typer.Option(
        True,
        "--kiro-pty/--no-kiro-pty",
        help="Retry kiro-cli with a pseudo-tty on timeout (ai mode)",
    ),
    kiro_debug: bool = typer.Option(
        False,
        "--kiro-debug",
        help="Print kiro-cli command and include output on failure",
    ),
    raw_output: bool = typer.Option(
        False,
        "--raw-output",
        help="Skip output normalization and cleaning (ai mode)",
    ),
) -> None:
    if path.exists() and any(path.iterdir()):
        console.print("[red]Target directory is not empty[/red]")
        raise typer.Exit(code=1)

    path.mkdir(parents=True, exist_ok=True)
    (path / "tests").mkdir(parents=True, exist_ok=True)

    if interactive:
        name = typer.prompt("Power name", default="power-name")
        description = typer.prompt("Description", default="Describe the power.")
        version = typer.prompt("Version", default="0.1.0")
        author = typer.prompt("Author", default="Your Name")
        license_id = typer.prompt("License", default="MIT")
        phrases = _parse_list(
            typer.prompt("Trigger phrases (comma-separated)", default="example phrase")
        )
        domains = _parse_list(typer.prompt("Domains (comma-separated)", default=""))
        file_patterns = _parse_list(
            typer.prompt("File patterns (comma-separated)", default="")
        )
        allowed_tools = _parse_list(
            typer.prompt("Allowed tools (comma-separated)", default="filesystem.read")
        )
        denied_tools = _parse_list(
            typer.prompt("Denied tools (comma-separated)", default="network.*")
        )
        requires_network = typer.confirm("Requires network access?", default=False)
        include_steering = typer.confirm("Include steering guidance?", default=True)
        include_tools = typer.confirm("Include tools.yaml?", default=True)
        include_hooks = typer.confirm("Include hooks.yaml?", default=True)
        tests_path = typer.prompt("Tests path", default="tests/tests.yaml")
        behaviors = _parse_list(
            typer.prompt(
                "Expected behaviors (comma-separated)",
                default="Describe expected behavior",
            )
        )

        resources = []
        steering_files: list[str] = []
        if include_steering:
            steering_mode = typer.prompt(
                "Steering mode (generate/wizard/ai)", default="generate"
            ).strip().lower()
            if steering_mode not in {"generate", "wizard", "ai"}:
                console.print("[red]Steering mode must be generate, wizard, or ai[/red]")
                raise typer.Exit(code=1)

            steering_type = typer.prompt(
                "Steering template set (foundational/common/blank)", default="common"
            ).strip().lower()
            if steering_type not in {"foundational", "common", "blank"}:
                console.print(
                    "[red]Steering template set must be foundational, common, or blank[/red]"
                )
                raise typer.Exit(code=1)

            if steering_mode == "generate":
                available = list(_steering_templates(steering_type).keys())
                selection_raw = typer.prompt(
                    f"Files to generate (comma-separated) {available}",
                    default=",".join(available),
                )
                selection = _parse_list(selection_raw)
                steering_files = _write_steering_templates(
                    path, steering_type, selection=selection
                )
            elif steering_mode == "wizard":
                templates = _steering_templates(steering_type)
                selection_raw = typer.prompt(
                    f"Files to generate (comma-separated) {list(templates.keys())}",
                    default=",".join(templates.keys()),
                )
                selection = _parse_list(selection_raw)
                picked = _select_steering_files(templates, selection)
                path.mkdir(parents=True, exist_ok=True)
                steering_files = []
                for filename in picked.keys():
                    title = filename.replace(".md", "").replace("-", " ").title()
                    content = _wizard_template_content(
                        title,
                        [
                            ("Purpose", f"{title} purpose"),
                            ("Standards", f"{title} standards"),
                            ("Examples", f"{title} examples"),
                        ],
                    )
                    (path / filename).write_text(content, encoding="utf-8")
                    steering_files.append(filename)
            else:
                goal = typer.prompt("Goal for steering content", default="")
                templates = _steering_templates(steering_type)
                selection_raw = typer.prompt(
                    f"Files to generate (comma-separated) {list(templates.keys())}",
                    default=",".join(templates.keys()),
                )
                selection = _parse_list(selection_raw)
                picked = _select_steering_files(templates, selection)
                path.mkdir(parents=True, exist_ok=True)
                steering_files = []
                effective_trust_none = kiro_trust_none or (
                    not kiro_trust_all and not kiro_trust_tools
                )
                filenames = list(picked.keys())
                
                # Always use single-file generation for reliability
                console.print(f"[cyan]Generating {len(filenames)} steering files (single-file approach for reliability)...[/cyan]")
                for filename in filenames:
                    prompt = (
                        f"Create a steering file named {filename} for this goal: "
                        f"{goal}. Use markdown. Include these headings: "
                        f"{', '.join(_steering_headings(filename))}. "
                        "Provide context and concrete examples. "
                        "Output markdown only. Do not use tools or write files."
                    )
                    console.print(f"[cyan]Generating[/cyan] {filename}...")
                    try:
                        content = _generate_with_kiro(
                            prompt,
                            no_interactive=kiro_no_interactive,
                            trust_all=kiro_trust_all,
                            trust_tools=kiro_trust_tools,
                            timeout_seconds=kiro_timeout,
                            debug=kiro_debug,
                            trust_none=effective_trust_none,
                            wrap=kiro_wrap,
                            agent=kiro_agent,
                            model=kiro_model,
                            use_pty=kiro_pty,
                        )
                    except RuntimeError as exc:
                        console.print(f"[red]{exc}[/red]")
                        # Fallback to template content if kiro-cli fails
                        console.print(f"[yellow]Falling back to template content for {filename}[/yellow]")
                        content = templates[filename]
                    if not content:
                        content = templates[filename]
                    if raw_output:
                        # Skip normalization when raw output is requested
                        (path / filename).write_text(content, encoding="utf-8")
                    else:
                        normalized = _normalize_steering_content(filename, content)
                        (path / filename).write_text(normalized, encoding="utf-8")
                    steering_files.append(filename)
                    console.print(f"[green]Wrote[/green] {filename}")
            resources.extend(steering_files)
        tools = []
        if include_tools:
            tools.append("tools.yaml")
        hooks = []
        if include_hooks:
            hooks.append("hooks.yaml")

        power_template = "meta:\n"
        power_template += f"  name: {name}\n"
        power_template += f"  description: {description}\n"
        power_template += f"  version: \"{version}\"\n"
        power_template += f"  author: {author}\n"
        power_template += f"  license: {license_id}\n"
        power_template += "triggers:\n"
        if phrases:
            power_template += "  phrases:\n"
            for phrase in phrases:
                power_template += f"    - \"{phrase}\"\n"
        else:
            power_template += "  phrases: []\n"
        if domains:
            power_template += "  domains:\n"
            for domain in domains:
                power_template += f"    - \"{domain}\"\n"
        else:
            power_template += "  domains: []\n"
        if file_patterns:
            power_template += "  files:\n"
            for pattern in file_patterns:
                power_template += f"    - \"{pattern}\"\n"
        else:
            power_template += "  files: []\n"
        power_template += "constraints:\n"
        if allowed_tools:
            power_template += "  allowed_tools:\n"
            for tool in allowed_tools:
                power_template += f"    - \"{tool}\"\n"
        else:
            power_template += "  allowed_tools: []\n"
        if denied_tools:
            power_template += "  denied_tools:\n"
            for tool in denied_tools:
                power_template += f"    - \"{tool}\"\n"
        else:
            power_template += "  denied_tools: []\n"
        power_template += f"  requires_network: {str(requires_network)}\n"
        power_template += "resources:\n"
        if resources:
            power_template += "  steering_files:\n"
            for item in resources:
                power_template += f"    - \"{item}\"\n"
        else:
            power_template += "  steering_files: []\n"
        if tools:
            power_template += "  tools_files:\n"
            for item in tools:
                power_template += f"    - \"{item}\"\n"
        else:
            power_template += "  tools_files: []\n"
        if hooks:
            power_template += "  hooks_files:\n"
            for item in hooks:
                power_template += f"    - \"{item}\"\n"
        else:
            power_template += "  hooks_files: []\n"
        power_template += "  assets: []\n"
        power_template += "tests:\n"
        power_template += f"  tests_path: \"{tests_path}\"\n"
        if behaviors:
            power_template += "  expected_behaviors:\n"
            for item in behaviors:
                power_template += f"    - \"{item}\"\n"
        else:
            power_template += "  expected_behaviors: []\n"
        power_template += "compatibility:\n"
        power_template += "  kiro_version: \">=0.1\"\n"
        power_template += "  platforms:\n"
        power_template += "    - darwin\n"
        power_template += "    - linux\n"
    else:
        power_template = """meta:\n  name: power-name\n  description: Describe the power.\n  version: \"0.1.0\"\n  author: Your Name\n  license: MIT\ntriggers:\n  phrases:\n    - \"example phrase\"\n  domains:\n    - \"example\"\nconstraints:\n  allowed_tools:\n    - \"filesystem.read\"\n  denied_tools:\n    - \"network.*\"\nresources:\n  steering_files:\n    - \"steering.md\"\n  tools_files:\n    - \"tools.yaml\"\n  hooks_files:\n    - \"hooks.yaml\"\n  assets: []\ntests:\n  tests_path: \"tests/tests.yaml\"\n  expected_behaviors:\n    - \"Describe expected behavior\"\ncompatibility:\n  kiro_version: \">=0.1\"\n  platforms:\n    - darwin\n    - linux\n"""
    (path / "POWER.md").write_text(power_template, encoding="utf-8")
    if not interactive and "steering.md" in power_template:
        _write_steering_templates(path, "blank")
    if "tools.yaml" in power_template:
        (path / "tools.yaml").write_text("# Tools\n", encoding="utf-8")
    if "hooks.yaml" in power_template:
        (path / "hooks.yaml").write_text("# Hooks\n", encoding="utf-8")
    (path / "tests" / "tests.yaml").write_text(
        "cases:\n  - name: example\n    prompt: \"Describe the task\"\n    expected:\n      - \"Expected outcome\"\n",
        encoding="utf-8",
    )
    console.print(f"[green]Created power scaffold in {path}[/green]")


@app.command()
def init_steering(
    path: Path = typer.Argument(..., help="Path for the steering markdown file"),
    scope: str = typer.Option(
        "workspace",
        "--scope",
        help="Steering scope: workspace or global",
    ),
    title: str = typer.Option(
        "Project Steering",
        "--title",
        help="Heading for the steering document",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt for steering document metadata",
    ),
    mode: str = typer.Option(
        "generate",
        "--mode",
        help="Generation mode: generate, wizard, or ai",
    ),
    template_set: str = typer.Option(
        "common",
        "--template",
        help="Template set: foundational, common, or blank",
    ),
    files: list[str] = typer.Option(
        None,
        "--file",
        help="Specific steering files to generate (repeatable)",
    ),
    goal: str = typer.Option(
        "",
        "--goal",
        help="High-level goal for AI-generated content (ai mode)",
    ),
    kiro_no_interactive: bool = typer.Option(
        True,
        "--kiro-no-interactive/--kiro-interactive",
        help="Run kiro-cli without prompts (ai mode)",
    ),
    kiro_trust_all: bool = typer.Option(
        False,
        "--kiro-trust-all",
        help="Allow all tools when calling kiro-cli (ai mode)",
    ),
    kiro_trust_tools: list[str] = typer.Option(
        None,
        "--kiro-trust-tools",
        help="Allow specific tools when calling kiro-cli (repeatable)",
    ),
    kiro_trust_none: bool = typer.Option(
        False,
        "--kiro-trust-none",
        help="Disallow all tools when calling kiro-cli (ai mode)",
    ),
    kiro_wrap: str = typer.Option(
        "auto",
        "--kiro-wrap",
        help="kiro-cli wrap mode: auto, never, or always (ai mode)",
    ),
    kiro_agent: str = typer.Option(
        None,
        "--kiro-agent",
        help="Agent profile to use with kiro-cli (ai mode)",
    ),
    kiro_model: str = typer.Option(
        None,
        "--kiro-model",
        help="Model name to use with kiro-cli (ai mode)",
    ),
    kiro_timeout: int = typer.Option(
        60,
        "--kiro-timeout",
        help="Timeout for kiro-cli calls in seconds (ai mode)",
    ),
    kiro_pty: bool = typer.Option(
        True,
        "--kiro-pty/--no-kiro-pty",
        help="Retry kiro-cli with a pseudo-tty on timeout (ai mode)",
    ),
    kiro_debug: bool = typer.Option(
        False,
        "--kiro-debug",
        help="Print kiro-cli command and include output on failure",
    ),
    raw_output: bool = typer.Option(
        False,
        "--raw-output",
        help="Skip output normalization and cleaning (ai mode)",
    ),
) -> None:
    if scope not in {"workspace", "global"}:
        console.print("[red]Scope must be 'workspace' or 'global'[/red]")
        raise typer.Exit(code=1)

    if interactive:
        scope = typer.prompt("Scope (workspace/global)", default=scope)
        if scope not in {"workspace", "global"}:
            console.print("[red]Scope must be 'workspace' or 'global'[/red]")
            raise typer.Exit(code=1)
        mode = typer.prompt("Mode (generate/wizard/ai)", default=mode).strip().lower()
        if mode not in {"generate", "wizard", "ai"}:
            console.print("[red]Mode must be generate, wizard, or ai[/red]")
            raise typer.Exit(code=1)
        template_set = typer.prompt(
            "Template set (foundational/common/blank)", default=template_set
        ).strip().lower()
        if template_set not in {"foundational", "common", "blank"}:
            console.print("[red]Template must be foundational, common, or blank[/red]")
            raise typer.Exit(code=1)
        base_dir = path if path.suffix == "" else path.parent
        if mode == "generate":
            available = list(_steering_templates(template_set).keys())
            selection_raw = typer.prompt(
                f"Files to generate (comma-separated) {available}",
                default=",".join(available),
            )
            selection = _parse_list(selection_raw)
            created = _write_steering_templates(
                base_dir, template_set, selection=selection
            )
            console.print(
                f"[green]Created steering files ({scope}) in {base_dir}[/green]"
            )
            for name in created:
                console.print(f" - {name}")
            return

        if mode == "wizard":
            templates = _steering_templates(template_set)
            selection_raw = typer.prompt(
                f"Files to generate (comma-separated) {list(templates.keys())}",
                default=",".join(templates.keys()),
            )
            selection = _parse_list(selection_raw)
            picked = _select_steering_files(templates, selection)
            base_dir.mkdir(parents=True, exist_ok=True)
            created = []
            for filename in picked.keys():
                title = filename.replace(".md", "").replace("-", " ").title()
                content = _wizard_template_content(
                    title,
                    [
                        ("Purpose", f"{title} purpose"),
                        ("Standards", f"{title} standards"),
                        ("Examples", f"{title} examples"),
                    ],
                )
                (base_dir / filename).write_text(content, encoding="utf-8")
                created.append(filename)
            console.print(f"[green]Created steering files ({scope}) in {base_dir}[/green]")
            for name in created:
                console.print(f" - {name}")
            return

        goal = typer.prompt("Goal for steering content", default=goal)
        templates = _steering_templates(template_set)
        selection_raw = typer.prompt(
            f"Files to generate (comma-separated) {list(templates.keys())}",
            default=",".join(templates.keys()),
        )
        selection = _parse_list(selection_raw)
        picked = _select_steering_files(templates, selection)
        base_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for filename in picked.keys():
            prompt = (
                f"Create a steering file named {filename} for this goal: "
                f"{goal}. Provide markdown with a top-level heading and "
                "clear guidance, including context and examples."
            )
            try:
                content = _generate_with_kiro(
                    prompt,
                    no_interactive=kiro_no_interactive,
                    trust_all=kiro_trust_all,
                    trust_tools=kiro_trust_tools,
                    timeout_seconds=kiro_timeout,
                    debug=kiro_debug,
                    trust_none=kiro_trust_none,
                    wrap=kiro_wrap,
                    agent=kiro_agent,
                    model=kiro_model,
                    use_pty=kiro_pty,
                )
            except RuntimeError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1)
            if not content:
                content = templates[filename]
            (base_dir / filename).write_text(content, encoding="utf-8")
            created.append(filename)
        console.print(f"[green]Created steering files ({scope}) in {base_dir}[/green]")
        for name in created:
            console.print(f" - {name}")
        return

    mode = mode.strip().lower()
    template_set = template_set.strip().lower()
    if mode not in {"generate", "wizard", "ai"}:
        console.print("[red]Mode must be generate, wizard, or ai[/red]")
        raise typer.Exit(code=1)
    if template_set not in {"foundational", "common", "blank"}:
        console.print("[red]Template must be foundational, common, or blank[/red]")
        raise typer.Exit(code=1)

    base_dir = path if path.suffix == "" else path.parent
    if mode == "generate":
        selection = files
        created = _write_steering_templates(
            base_dir, template_set, selection=selection
        )
        console.print(f"[green]Created steering files ({scope}) in {base_dir}[/green]")
        for name in created:
            console.print(f" - {name}")
        return

    if mode == "wizard":
        templates = _steering_templates(template_set)
        picked = _select_steering_files(templates, files)
        base_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for filename in picked.keys():
            title = filename.replace(".md", "").replace("-", " ").title()
            content = _wizard_template_content(
                title,
                [
                    ("Purpose", f"{title} purpose"),
                    ("Standards", f"{title} standards"),
                    ("Examples", f"{title} examples"),
                ],
            )
            (base_dir / filename).write_text(content, encoding="utf-8")
            created.append(filename)
        console.print(f"[green]Created steering files ({scope}) in {base_dir}[/green]")
        for name in created:
            console.print(f" - {name}")
        return

    if not goal.strip():
        console.print("[red]--goal is required for ai mode[/red]")
        raise typer.Exit(code=1)

    if kiro_trust_all and kiro_trust_none:
        console.print("[red]Use either --kiro-trust-all or --kiro-trust-none[/red]")
        raise typer.Exit(code=1)

    templates = _steering_templates(template_set)
    picked = _select_steering_files(templates, files)
    base_dir.mkdir(parents=True, exist_ok=True)
    created = []
    effective_trust_none = kiro_trust_none or (
        not kiro_trust_all and not kiro_trust_tools
    )
    filenames = list(picked.keys())
    
    # Always use single-file generation for reliability
    console.print(f"[cyan]Generating {len(filenames)} steering files (single-file approach for reliability)...[/cyan]")
    for filename in filenames:
        prompt = (
            f"Create a steering file named {filename} for this goal: "
            f"{goal}. Use markdown. Include these headings: "
            f"{', '.join(_steering_headings(filename))}. "
            "Provide context and concrete examples. "
            "Output markdown only. Do not use tools or write files."
        )
        console.print(f"[cyan]Generating[/cyan] {filename}...")
        try:
            content = _generate_with_kiro(
                prompt,
                no_interactive=kiro_no_interactive,
                trust_all=kiro_trust_all,
                trust_tools=kiro_trust_tools,
                timeout_seconds=kiro_timeout,
                debug=kiro_debug,
                trust_none=effective_trust_none,
                wrap=kiro_wrap,
                agent=kiro_agent,
                model=kiro_model,
                use_pty=kiro_pty,
            )
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        if not content:
            content = templates[filename]
        if raw_output:
            # Skip normalization when raw output is requested
            (base_dir / filename).write_text(content, encoding="utf-8")
        else:
            normalized = _normalize_steering_content(filename, content)
            (base_dir / filename).write_text(normalized, encoding="utf-8")
        created.append(filename)
        console.print(f"[green]Wrote[/green] {filename}")
    console.print(f"[green]Created steering files ({scope}) in {base_dir}[/green]")
    for name in created:
        console.print(f" - {name}")
    return


@app.command()
def ai_test() -> None:
    """Quick health check for AI steering functionality."""
    console.print("[cyan]Running AI steering health check...[/cyan]")
    
    # Check 1: kiro-cli availability
    kiro_path = shutil.which("kiro-cli")
    if kiro_path:
        console.print(f"[green]✓[/green] kiro-cli found: {kiro_path}")
    else:
        console.print("[red]✗[/red] kiro-cli not found in PATH")
        console.print("[yellow]Install kiro-cli to use AI steering features[/yellow]")
        raise typer.Exit(code=1)
    
    # Check 2: Configuration validity
    try:
        config = get_config()
        console.print(f"[green]✓[/green] Configuration loaded (timeout: {config.kiro.timeout}s)")
    except Exception as exc:
        console.print(f"[red]✗[/red] Configuration error: {exc}")
        raise typer.Exit(code=1)
    
    # Check 3: Basic kiro-cli connectivity
    try:
        result = subprocess.run(
            ["kiro-cli", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_info = result.stdout.strip() or "version info available"
            console.print(f"[green]✓[/green] kiro-cli responsive: {version_info}")
        else:
            console.print(f"[yellow]⚠[/yellow] kiro-cli responded with exit code {result.returncode}")
            if result.stderr:
                console.print(f"[dim]Error: {result.stderr.strip()}[/dim]")
    except subprocess.TimeoutExpired:
        console.print("[red]✗[/red] kiro-cli timed out (10s)")
        console.print("[yellow]Try increasing timeout with --kiro-timeout[/yellow]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]✗[/red] kiro-cli test failed: {exc}")
        raise typer.Exit(code=1)
    
    # Check 4: Quick AI test (optional, only if kiro-cli is working)
    console.print("[cyan]Testing basic AI generation...[/cyan]")
    try:
        test_output = _generate_with_kiro(
            "Say 'AI test successful' in markdown format.",
            no_interactive=True,
            trust_tools=[],
            timeout_seconds=15,
            debug=False,
            trust_none=True,
            wrap="never",
        )
        if test_output and "test successful" in test_output.lower():
            console.print("[green]✓[/green] AI generation working")
        else:
            console.print("[yellow]⚠[/yellow] AI generation responded but output unclear")
            console.print(f"[dim]Response: {test_output[:100]}...[/dim]")
    except Exception as exc:
        console.print(f"[yellow]⚠[/yellow] AI generation test failed: {exc}")
        console.print("[dim]This may be due to model availability or network issues[/dim]")
    
    console.print("[green]Health check complete![/green]")
    console.print("[dim]Use 'kiroforge init-steering --mode ai' to generate steering files[/dim]")


@app.command()
def doctor() -> None:
    kiro_path = shutil.which("kiro-cli")
    if kiro_path:
        console.print(f"[green]kiro-cli found[/green]: {kiro_path}")
    else:
        console.print("[red]kiro-cli not found in PATH[/red]")


@app.command()
def route(
    prompt: str = typer.Argument(..., help="Prompt to route"),
    powers_dir: Path = typer.Option(
        Path("examples/kiro_powers"),
        "--powers-dir",
        help="Directory containing power folders",
    ),
    files: list[str] = typer.Option(
        None,
        "--file",
        help="File path(s) to include for routing signals",
    ),
    min_score: int = typer.Option(
        None,
        "--min-score",
        help="Minimum score threshold (overrides config)",
    ),
    max_results: int = typer.Option(
        None,
        "--max-results", 
        help="Maximum number of results (overrides config)",
    ),
) -> None:
    """Route a prompt to matching powers with improved intelligence."""
    if not powers_dir.exists():
        console.print("[red]Powers directory not found[/red]")
        raise typer.Exit(code=1)

    # Load configuration
    config = get_config()
    
    # Use CLI arguments or fall back to config
    effective_min_score = min_score if min_score is not None else config.router.min_score
    effective_max_results = max_results if max_results is not None else config.router.max_results

    specs = []
    for child in powers_dir.iterdir():
        if not child.is_dir():
            continue
        spec_path = child / "POWER.md"
        if spec_path.exists():
            try:
                specs.append(load_power_spec(spec_path))
            except Exception as exc:
                console.print(f"[yellow]Warning: Failed to load {spec_path}: {exc}[/yellow]")
                continue

    matches = select_powers(
        specs, 
        prompt, 
        files=files,
        min_score=effective_min_score,
        max_results=effective_max_results
    )
    
    if not matches:
        console.print("[yellow]No matching powers found[/yellow]")
        console.print(f"[dim]Searched {len(specs)} powers with min_score={effective_min_score}[/dim]")
        return

    table = Table(title=f"Route Matches (min_score={effective_min_score})")
    table.add_column("Power")
    table.add_column("Score", justify="right")
    table.add_column("Reasons")
    
    for match in matches:
        reasons_str = ", ".join(match.reasons)
        if len(reasons_str) > 60:
            reasons_str = reasons_str[:57] + "..."
        table.add_row(match.name, str(match.score), reasons_str)
    
    console.print(table)
    console.print(f"[dim]Found {len(matches)} matching powers out of {len(specs)} total[/dim]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    set_key: str = typer.Option(None, "--set", help="Set configuration key (format: section.key=value)"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default configuration"),
) -> None:
    """Manage KiroForge configuration."""
    config_manager = ConfigManager()
    
    if reset:
        # Create default config and save it
        from kiroforge.config import KiroForgeConfig
        default_config = KiroForgeConfig()
        config_manager.save_config(default_config)
        console.print("[green]Configuration reset to defaults[/green]")
        return
    
    if set_key:
        # Parse and set configuration value
        if "=" not in set_key:
            console.print("[red]Invalid format. Use: section.key=value[/red]")
            raise typer.Exit(code=1)
        
        key_path, value = set_key.split("=", 1)
        if "." not in key_path:
            console.print("[red]Invalid key format. Use: section.key[/red]")
            raise typer.Exit(code=1)
        
        section, key = key_path.split(".", 1)
        
        # Load current config
        current_config = config_manager.get_config()
        config_dict = current_config.model_dump()
        
        # Update the value
        if section not in config_dict:
            console.print(f"[red]Unknown section: {section}[/red]")
            raise typer.Exit(code=1)
        
        # Try to convert value to appropriate type
        try:
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
        except ValueError:
            pass  # Keep as string
        
        config_dict[section][key] = value
        
        # Validate and save
        try:
            from kiroforge.config import KiroForgeConfig
            new_config = KiroForgeConfig.model_validate(config_dict)
            config_manager.save_config(new_config)
            console.print(f"[green]Set {key_path} = {value}[/green]")
        except Exception as exc:
            console.print(f"[red]Invalid configuration: {exc}[/red]")
            raise typer.Exit(code=1)
        
        return
    
    if show or (not set_key and not reset):
        # Show current configuration
        current_config = config_manager.get_config()
        
        console.print("[bold]KiroForge Configuration[/bold]")
        console.print()
        
        # Router configuration
        console.print("[bold cyan]Router:[/bold cyan]")
        console.print(f"  min_score: {current_config.router.min_score}")
        console.print(f"  max_results: {current_config.router.max_results}")
        console.print(f"  fuzzy_threshold: {current_config.router.fuzzy_threshold}")
        console.print(f"  keyword_threshold: {current_config.router.keyword_threshold}")
        console.print(f"  semantic_threshold: {current_config.router.semantic_threshold}")
        console.print()
        
        # Validation configuration
        console.print("[bold cyan]Validation:[/bold cyan]")
        console.print(f"  max_file_size: {current_config.validation.max_file_size}")
        console.print(f"  strict_spdx: {current_config.validation.strict_spdx}")
        console.print(f"  require_tests: {current_config.validation.require_tests}")
        console.print()
        
        # Template configuration
        console.print("[bold cyan]Templates:[/bold cyan]")
        console.print(f"  custom_templates_dir: {current_config.templates.custom_templates_dir}")
        console.print(f"  default_template_set: {current_config.templates.default_template_set}")
        console.print()
        
        # Kiro configuration
        console.print("[bold cyan]Kiro:[/bold cyan]")
        console.print(f"  timeout: {current_config.kiro.timeout}")
        console.print(f"  trust_mode: {current_config.kiro.trust_mode}")
        console.print(f"  wrap_mode: {current_config.kiro.wrap_mode}")
        console.print(f"  debug: {current_config.kiro.debug}")
        console.print()
        
        # Show config file locations
        console.print("[dim]Configuration files checked (in order):[/dim]")
        for path in config_manager._config_paths:
            status = "✓" if path.exists() else "✗"
            console.print(f"  {status} {path}")


if __name__ == "__main__":
    app()

# Agent and Collection CLI Commands

def _generate_agent_yaml(agent_name: str, interactive: bool = False) -> str:
    """Generate agent.yaml content."""
    if interactive:
        description = typer.prompt("Agent description")
        expertise = typer.prompt("Expertise areas (comma-separated)", default="")
        expertise_list = [e.strip() for e in expertise.split(",") if e.strip()]
    else:
        description = f"{agent_name.replace('-', ' ').replace('_', ' ').title()} agent"
        expertise_list = []
    
    return f"""meta:
  name: {agent_name}
  description: {description}
  version: "1.0.0"
  author: "Your Name"

identity:
  prompt_file: system-prompt.md
  expertise: {expertise_list}

powers:
  # Add power references here
  # - "./powers/example-power"

constraints:
  allowed_tools: ["filesystem.*"]
  denied_tools: ["network.external.*"]
  requires_network: false

tests:
  test_path: "tests/"
  expected_behaviors:
    - "Provides helpful responses"
    - "Follows specified constraints"

compatibility:
  kiro_version: ">=1.23"
  platforms: ["darwin", "linux"]
"""


def _generate_system_prompt(agent_name: str, interactive: bool = False) -> str:
    """Generate system-prompt.md content."""
    title = agent_name.replace('-', ' ').replace('_', ' ').title()
    
    if interactive:
        role_description = typer.prompt("Role description", default=f"You are a {title} agent")
        capabilities = typer.prompt("Key capabilities (comma-separated)", default="")
        cap_list = [c.strip() for c in capabilities.split(",") if c.strip()]
    else:
        role_description = f"You are a {title} agent"
        cap_list = ["Analyze and provide insights", "Follow best practices", "Maintain helpful and professional tone"]
    
    capabilities_section = ""
    if cap_list:
        capabilities_section = "\n\n## Capabilities\n\n" + "\n".join(f"- {cap}" for cap in cap_list)
    
    return f"""# {title} Agent

{role_description}.{capabilities_section}

## Guidelines

- Provide clear and actionable responses
- Ask clarifying questions when needed
- Follow all specified constraints and policies
- Maintain a helpful and professional tone

## Constraints

- Only use approved tools and resources
- Respect security and privacy requirements
- Follow organizational policies and standards
"""


def _generate_test_template() -> str:
    """Generate test template content."""
    return """# Agent Tests

scenarios:
  - name: "Basic functionality test"
    prompt: "Hello, can you help me?"
    expected_behaviors:
      - "Responds helpfully"
      - "Follows constraints"
    
  - name: "Constraint compliance test"
    prompt: "Can you access external networks?"
    expected_behaviors:
      - "Explains constraint limitations"
      - "Suggests alternatives within constraints"

# Add more test scenarios as needed
"""


def _generate_collection_yaml(collection_name: str, interactive: bool = False) -> str:
    """Generate collection.yaml content."""
    if interactive:
        description = typer.prompt("Collection description")
    else:
        description = f"{collection_name.replace('-', ' ').replace('_', ' ').title()} agent collection"
    
    return f"""meta:
  name: {collection_name}
  description: {description}
  version: "1.0.0"
  author: "Your Name"

shared_context:
  powers:
    # Shared powers available to all agents
    # - "./shared/powers/common-standards"
  
  steering:
    # Common steering files
    # - "./shared/steering/team-practices.md"
  
  constraints:
    allowed_tools: ["filesystem.*"]
    denied_tools: ["network.external.*"]
    max_concurrent_agents: 5
    requires_network: false

agents:
  # Reference agent modules with roles
  # - path: "./agents/example-agent"
  #   role: "example_role"
  #   description: "Example agent description"

coordination:
  patterns:
    # Define coordination patterns
    # - "complex tasks -> coordinator spawns subagents"
  
  shared_memory:
    enabled: true
    scope: "collection"

tests:
  test_path: "tests/"
  scenarios: []

compatibility:
  kiro_version: ">=1.23"
  platforms: ["darwin", "linux"]
"""


@app.command()
def init_agent(
    path: Path = typer.Argument(..., help="Directory to create the new agent in"),
    name: str = typer.Option(None, "--name", help="Agent name (defaults to directory name)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive agent creation"),
) -> None:
    """Initialize a new agent module with scaffolding."""
    if path.exists() and any(path.iterdir()):
        console.print("[red]Target directory is not empty[/red]")
        raise typer.Exit(1)
    
    agent_name = name or path.name
    if not re.match(r"^[a-zA-Z0-9_-]+$", agent_name):
        console.print("[red]Invalid agent name. Use only letters, numbers, hyphens, and underscores.[/red]")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Creating agent module: {agent_name}[/cyan]")
    
    # Create agent structure
    path.mkdir(parents=True, exist_ok=True)
    
    # Create agent.yaml
    agent_yaml = _generate_agent_yaml(agent_name, interactive)
    (path / "agent.yaml").write_text(agent_yaml)
    
    # Create system-prompt.md
    prompt_content = _generate_system_prompt(agent_name, interactive)
    (path / "system-prompt.md").write_text(prompt_content)
    
    # Create powers directory
    (path / "powers").mkdir(exist_ok=True)
    (path / "powers" / ".gitkeep").write_text("# Add power modules here\n")
    
    # Create tests directory
    (path / "tests").mkdir(exist_ok=True)
    (path / "tests" / "test_responses.yaml").write_text(_generate_test_template())
    
    console.print(f"[green]✓ Agent module created at {path}[/green]")
    console.print(f"[yellow]Next steps:[/yellow]")
    console.print(f"  1. Edit {path}/system-prompt.md")
    console.print(f"  2. Add powers to {path}/powers/")
    console.print(f"  3. Update {path}/agent.yaml with power references")
    console.print(f"  4. Run: kiroforge validate-agent {path}")


@app.command()
def validate_agent(
    path: Path = typer.Argument(..., help="Path to an agent directory")
) -> None:
    """Validate an agent module."""
    console.print(f"[cyan]Validating agent: {path.name}[/cyan]")
    
    result = validator_validate_agent(path)
    if result.ok:
        console.print(f"[green]✓ Agent {path.name} is valid[/green]")
    else:
        console.print(f"[red]✗ Agent {path.name} has issues:[/red]")
        for issue in result.issues:
            color = "red" if issue.level == "error" else "yellow"
            console.print(f"  [{color}]{issue.level.upper()}: {issue.message}[/{color}]")
        
        error_count = sum(1 for issue in result.issues if issue.level == "error")
        warning_count = sum(1 for issue in result.issues if issue.level == "warning")
        
        if error_count > 0:
            console.print(f"[red]Found {error_count} error(s) and {warning_count} warning(s)[/red]")
            raise typer.Exit(1)
        else:
            console.print(f"[yellow]Found {warning_count} warning(s)[/yellow]")


@app.command()
def export_agent(
    path: Path = typer.Argument(..., help="Path to an agent directory"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file (defaults to {agent-name}.json)"),
) -> None:
    """Export agent to Kiro-native JSON format."""
    console.print(f"[cyan]Exporting agent: {path.name}[/cyan]")
    
    # Validate first
    result = validate_agent(path)
    if not result.ok:
        console.print("[red]Cannot export invalid agent. Run validate-agent first.[/red]")
        for issue in result.issues:
            if issue.level == "error":
                console.print(f"  [red]ERROR: {issue.message}[/red]")
        raise typer.Exit(1)
    
    try:
        spec = load_agent_spec(path)
        kiro_json = export_agent_to_kiro_json(path, spec)
        
        output_file = output or Path(f"{spec.meta.name}.json")
        save_agent_export(kiro_json, output_file)
        
        console.print(f"[green]✓ Agent exported to {output_file}[/green]")
        console.print(f"[dim]Export includes {len(kiro_json.get('tools', []))} tools and {len(kiro_json.get('mcpServers', {}))} MCP servers[/dim]")
        
    except (AgentSpecError, ExportError) as exc:
        console.print(f"[red]Export failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def test_agent(
    path: Path = typer.Argument(..., help="Path to agent directory")
) -> None:
    """Run behavioral tests for an agent."""
    from .harness import run_agent_tests, print_agent_test_results
    
    console.print(f"[cyan]Testing agent: {path.name}[/cyan]")
    
    try:
        context = run_agent_tests(path)
        print_agent_test_results(context)
        
        if not context.all_passed:
            raise typer.Exit(1)
            
    except Exception as exc:
        console.print(f"[red]Agent testing failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def init_collection(
    path: Path = typer.Argument(..., help="Directory to create the collection in"),
    name: str = typer.Option(None, "--name", help="Collection name (defaults to directory name)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive collection creation"),
) -> None:
    """Initialize a new agent collection."""
    if path.exists() and any(path.iterdir()):
        console.print("[red]Target directory is not empty[/red]")
        raise typer.Exit(1)
    
    collection_name = name or path.name
    if not re.match(r"^[a-zA-Z0-9_-]+$", collection_name):
        console.print("[red]Invalid collection name. Use only letters, numbers, hyphens, and underscores.[/red]")
        raise typer.Exit(1)
    
    console.print(f"[cyan]Creating collection: {collection_name}[/cyan]")
    
    # Create collection structure
    path.mkdir(parents=True, exist_ok=True)
    
    # Create collection.yaml
    collection_yaml = _generate_collection_yaml(collection_name, interactive)
    (path / "collection.yaml").write_text(collection_yaml)
    
    # Create shared directory structure
    (path / "shared").mkdir(exist_ok=True)
    (path / "shared" / "powers").mkdir(exist_ok=True)
    (path / "shared" / "powers" / ".gitkeep").write_text("# Add shared power modules here\n")
    (path / "shared" / "steering").mkdir(exist_ok=True)
    (path / "shared" / "steering" / ".gitkeep").write_text("# Add shared steering files here\n")
    
    # Create agents directory
    (path / "agents").mkdir(exist_ok=True)
    (path / "agents" / ".gitkeep").write_text("# Add agent modules here\n")
    
    # Create tests directory
    (path / "tests").mkdir(exist_ok=True)
    (path / "tests" / ".gitkeep").write_text("# Add collection tests here\n")
    
    console.print(f"[green]✓ Collection created at {path}[/green]")
    console.print(f"[yellow]Next steps:[/yellow]")
    console.print(f"  1. Add agent modules to {path}/agents/")
    console.print(f"  2. Update {path}/collection.yaml with agent references")
    console.print(f"  3. Add shared resources to {path}/shared/")
    console.print(f"  4. Run: kiroforge validate-collection {path}")


@app.command()
def validate_collection(
    path: Path = typer.Argument(..., help="Path to a collection directory")
) -> None:
    """Validate an agent collection and all its agents."""
    console.print(f"[cyan]Validating collection: {path.name}[/cyan]")
    
    result = validator_validate_collection(path)
    if result.ok:
        console.print(f"[green]✓ Collection {path.name} is valid[/green]")
    else:
        console.print(f"[red]✗ Collection {path.name} has issues:[/red]")
        for issue in result.issues:
            color = "red" if issue.level == "error" else "yellow"
            console.print(f"  [{color}]{issue.level.upper()}: {issue.message}[/{color}]")
        
        error_count = sum(1 for issue in result.issues if issue.level == "error")
        warning_count = sum(1 for issue in result.issues if issue.level == "warning")
        
        if error_count > 0:
            console.print(f"[red]Found {error_count} error(s) and {warning_count} warning(s)[/red]")
            raise typer.Exit(1)
        else:
            console.print(f"[yellow]Found {warning_count} warning(s)[/yellow]")


@app.command()
def export_collection(
    path: Path = typer.Argument(..., help="Path to a collection directory"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="Output directory (defaults to ./exported)"),
) -> None:
    """Export collection to multiple Kiro-native JSON files."""
    console.print(f"[cyan]Exporting collection: {path.name}[/cyan]")
    
    # Validate first
    result = validate_collection(path)
    if not result.ok:
        console.print("[red]Cannot export invalid collection. Run validate-collection first.[/red]")
        for issue in result.issues:
            if issue.level == "error":
                console.print(f"  [red]ERROR: {issue.message}[/red]")
        raise typer.Exit(1)
    
    try:
        spec = load_collection_spec(path)
        export_data = export_collection_to_kiro_json(path, spec)
        
        output_directory = output_dir or Path("exported")
        created_files = save_collection_export(export_data, output_directory)
        
        console.print(f"[green]✓ Collection exported to {output_directory}[/green]")
        console.print(f"[dim]Created {len(created_files)} files:[/dim]")
        for file_path in created_files:
            console.print(f"  [dim]- {file_path.name}[/dim]")
        
    except (CollectionSpecError, ExportError) as exc:
        console.print(f"[red]Export failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def test_collection(
    path: Path = typer.Argument(..., help="Path to collection directory")
) -> None:
    """Run multi-agent tests for a collection."""
    from .harness import run_collection_tests, print_collection_test_results
    
    console.print(f"[cyan]Testing collection: {path.name}[/cyan]")
    
    try:
        context = run_collection_tests(path)
        print_collection_test_results(context)
        
        if not context.all_passed:
            raise typer.Exit(1)
            
    except Exception as exc:
        console.print(f"[red]Collection testing failed: {exc}[/red]")
        raise typer.Exit(1)

@app.command()
def list_agent_templates() -> None:
    """List available agent templates."""
    from .templates import TemplateManager
    
    template_manager = TemplateManager()
    templates = template_manager.get_agent_templates()
    
    if not templates:
        console.print("[yellow]No agent templates found[/yellow]")
        return
    
    console.print("[cyan]Available Agent Templates:[/cyan]")
    for template in templates:
        try:
            info = template_manager.get_agent_template_info(template)
            console.print(f"  [green]{template}[/green]: {info['description']}")
        except Exception:
            console.print(f"  [green]{template}[/green]: Agent template")


@app.command()
def list_collection_templates() -> None:
    """List available collection templates."""
    from .templates import TemplateManager
    
    template_manager = TemplateManager()
    templates = template_manager.get_collection_templates()
    
    if not templates:
        console.print("[yellow]No collection templates found[/yellow]")
        return
    
    console.print("[cyan]Available Collection Templates:[/cyan]")
    for template in templates:
        try:
            info = template_manager.get_collection_template_info(template)
            console.print(f"  [green]{template}[/green]: {info['description']}")
        except Exception:
            console.print(f"  [green]{template}[/green]: Collection template")


@app.command()
def init_agent_from_template(
    path: Path = typer.Argument(..., help="Directory to create the agent in"),
    template: str = typer.Argument(..., help="Template name to use"),
    name: str = typer.Option(None, "--name", help="Agent name (defaults to directory name)"),
) -> None:
    """Initialize a new agent from a template."""
    from .templates import TemplateManager, TemplateNotFoundError, TemplateError
    
    if path.exists() and any(path.iterdir()):
        console.print("[red]Target directory is not empty[/red]")
        raise typer.Exit(1)
    
    agent_name = name or path.name
    if not re.match(r"^[a-zA-Z0-9_-]+$", agent_name):
        console.print("[red]Invalid agent name. Use only letters, numbers, hyphens, and underscores.[/red]")
        raise typer.Exit(1)
    
    template_manager = TemplateManager()
    
    try:
        console.print(f"[cyan]Creating agent from template: {template}[/cyan]")
        path.mkdir(parents=True, exist_ok=True)
        template_manager.copy_agent_template(template, path)
        
        # Update agent name in agent.yaml if different from template
        agent_yaml = path / "agent.yaml"
        if agent_yaml.exists() and agent_name != template:
            content = agent_yaml.read_text()
            # Simple replacement - could be more sophisticated
            content = content.replace(f"name: {template}", f"name: {agent_name}")
            agent_yaml.write_text(content)
        
        console.print(f"[green]✓ Agent created from template at {path}[/green]")
        console.print(f"[yellow]Next steps:[/yellow]")
        console.print(f"  1. Review and customize {path}/agent.yaml")
        console.print(f"  2. Edit {path}/system-prompt.md")
        console.print(f"  3. Add powers to {path}/powers/")
        console.print(f"  4. Run: kiroforge validate-agent {path}")
        
    except TemplateNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("[dim]Use 'kiroforge list-agent-templates' to see available templates[/dim]")
        raise typer.Exit(1)
    except TemplateError as exc:
        console.print(f"[red]Template error: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def init_collection_from_template(
    path: Path = typer.Argument(..., help="Directory to create the collection in"),
    template: str = typer.Argument(..., help="Template name to use"),
    name: str = typer.Option(None, "--name", help="Collection name (defaults to directory name)"),
) -> None:
    """Initialize a new collection from a template."""
    from .templates import TemplateManager, TemplateNotFoundError, TemplateError
    
    if path.exists() and any(path.iterdir()):
        console.print("[red]Target directory is not empty[/red]")
        raise typer.Exit(1)
    
    collection_name = name or path.name
    if not re.match(r"^[a-zA-Z0-9_-]+$", collection_name):
        console.print("[red]Invalid collection name. Use only letters, numbers, hyphens, and underscores.[/red]")
        raise typer.Exit(1)
    
    template_manager = TemplateManager()
    
    try:
        console.print(f"[cyan]Creating collection from template: {template}[/cyan]")
        path.mkdir(parents=True, exist_ok=True)
        template_manager.copy_collection_template(template, path)
        
        # Update collection name in collection.yaml if different from template
        collection_yaml = path / "collection.yaml"
        if collection_yaml.exists() and collection_name != template:
            content = collection_yaml.read_text()
            # Simple replacement - could be more sophisticated
            content = content.replace(f"name: {template}", f"name: {collection_name}")
            collection_yaml.write_text(content)
        
        console.print(f"[green]✓ Collection created from template at {path}[/green]")
        console.print(f"[yellow]Next steps:[/yellow]")
        console.print(f"  1. Review and customize {path}/collection.yaml")
        console.print(f"  2. Add agent modules to {path}/agents/")
        console.print(f"  3. Add shared resources to {path}/shared/")
        console.print(f"  4. Run: kiroforge validate-collection {path}")
        
    except TemplateNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("[dim]Use 'kiroforge list-collection-templates' to see available templates[/dim]")
        raise typer.Exit(1)
    except TemplateError as exc:
        console.print(f"[red]Template error: {exc}[/red]")
        raise typer.Exit(1)