# KiroForge

[![Tests](https://img.shields.io/badge/tests-passing-green)](tests/)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)

KiroForge is a Python toolkit for authoring, validating, and testing Kiro Powers, Custom Agents, and Agent Collections - modular capabilities that bundle tools, steering, and behavioral constraints into reusable, testable units.

## Table of Contents

- [Goals](#goals)
- [Concept](#concept)
- [Documentation](#documentation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli)
- [Examples](#examples)
- [Testing](#testing)
- [Repository Layout](#repository-layout)

## Goals

- Define clear, Kiro-native schemas for Powers, Agents, and Collections
- Validate structure, metadata, and security constraints
- Run behavioral tests against expectations
- Enable secure multi-agent coordination with delegation controls
- Export Kiro-compatible configurations for direct import

## Concept

- **Powers**: [CONCEPT.md](CONCEPT.md) - Modular agent capabilities
- **Agents**: [AGENT-MODULE-CONCEPT.md](AGENT-MODULE-CONCEPT.md) - Custom agents with identity and delegation
- **Collections**: Multi-agent coordination with shared context and governance

## Blueprint: What a Power Produces

KiroForge standardizes the outputs of a power so they are predictable, reviewable, and reusable.

- `POWER.md`: metadata and triggers that define *what the power is* and *when it should run*.
- `steering.md`: persistent guidance that sets behavioral expectations and project standards.
- `tools.yaml`: MCP/tool configuration that defines *what the power can do*.
- `hooks.yaml`: guardrails and validation for *how the power should behave*.
- `tests/tests.yaml`: behavioral assertions that prevent drift and regressions.

This blueprint keeps powers portable across teams and makes governance possible.

Steering-only documents are supported when you just need persistent guidance without tools or hooks.

## Quick Start

**Recommended (using uv):**
```bash
uv venv --python 3.12
uv pip install -e .
uv run kiroforge --help
```

**Alternative (manual venv activation):**
```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
kiroforge --help
```


## Documentation

- [Concept & Framework Overview](CONCEPT.md) - Strategic vision and market positioning
- [POWER.md Specification](docs/POWER_SPEC.md) - Complete schema documentation

## Repository Layout

```
src/kiroforge/        # core library + CLI
examples/             # example powers
schemas/              # schema drafts
docs/                 # spec docs
tests/                # unit tests
templates/            # steering templates
```

## Examples

- `examples/kiro_powers/demo-power` (minimal power)
- `examples/kiro_powers/mcp-hook-power` (MCP + hook bundle)

## Power Distribution

### Manual Installation

Powers can be shared and installed manually using several approaches:

**Git Repository Sharing:**
```bash
# Share your power via Git
git clone https://github.com/user/my-power.git
kiroforge validate ./my-power
kiroforge run-tests ./my-power

# Copy to your powers directory
cp -r ./my-power ./powers/
```

**Archive Distribution:**
```bash
# Create a power archive
tar -czf my-power.tar.gz my-power/

# Extract and validate
tar -xzf my-power.tar.gz
kiroforge validate ./my-power
```

**Direct Copy:**
```bash
# Copy power between systems
scp -r ./my-power user@remote:/path/to/powers/
rsync -av ./my-power/ user@remote:/path/to/powers/my-power/
```

### Steering File Distribution

Steering files can be shared independently:

```bash
# Copy steering files to workspace
cp steering-templates/*.md .kiro/steering/

# Or to global steering
cp steering-templates/*.md ~/.kiro/steering/

# Validate steering files
kiroforge validate-steering .kiro/steering/api-standards.md
```

### Enterprise Deployment

For enterprise environments, consider:

1. **Internal Git repositories** for power version control
2. **Shared network drives** for steering templates
3. **Configuration management** tools (Ansible, Chef) for deployment
4. **CI/CD pipelines** for power validation and testing

### Power Discovery

Use the routing system to discover relevant powers:

```bash
# Find powers for specific tasks
kiroforge route "api testing" --powers-dir ./powers
kiroforge route "database migration" --powers-dir ./powers --min-score 3
```

## Local Development and Testing

KiroForge provides tools for developing and testing powers locally before sharing them:

### Real Kiro Integration

Test your powers against actual `kiro-cli` to see how they behave:

- **Local testing** with `kiroforge run ./my-power "test prompt"`
- **Actual kiro-cli calls** with your power's tool constraints and steering
- **Security validation** with command validation and secret redaction  
- **Configurable execution** using timeouts, trust modes, and wrap settings
- **Graceful fallbacks** when kiro-cli is unavailable

This lets you validate that your power works correctly before sharing it with others.

### Manual Distribution

When you're ready to share powers, use standard tools and workflows:

- **Git-based sharing** for version control and collaboration
- **Archive distribution** for offline or air-gapped environments  
- **Enterprise deployment** patterns using existing CI/CD tools
- **Cross-system copying** with validation workflows

This approach keeps distribution simple and leverages tools teams already know.

## Routing

Use `kiroforge route` to score powers based on triggers with improved intelligence:

```bash
kiroforge route "configure mcp service" --powers-dir examples/kiro_powers --file integrations/service.yaml
kiroforge route "demo validation" --min-score 5 --max-results 3
```

The improved router uses:
- **Exact phrase matching** (highest weight)
- **Fuzzy string similarity** for partial matches
- **Keyword overlap analysis** between prompt and power descriptions
- **Semantic matching** based on power descriptions
- **File pattern matching** with scoring based on match count

## CLI

### Configuration

```bash
kiroforge config --show                    # Show current configuration
kiroforge config --set router.min_score=3  # Set configuration value
kiroforge config --reset                   # Reset to defaults
```

Configuration files are loaded from (in order):
- `$KIROFORGE_CONFIG` environment variable
- `./kiroforge.yaml` or `./kiroforge.yml`
- `~/.kiroforge/config.yaml`
- `~/.config/kiroforge/config.yaml`

See `kiroforge.example.yaml` for configuration options.

### Powers

```bash
kiroforge init ./my-new-power                    # Create a new power
kiroforge init --interactive ./my-new-power      # Interactive power creation with AI steering
kiroforge init --interactive ./my-new-power --raw-output  # Skip output cleaning for AI-generated steering
kiroforge validate ./my-new-power                # Validate power structure
kiroforge run-tests ./my-new-power               # Run behavioral tests
kiroforge run ./my-new-power "Test prompt"       # Test locally with kiro-cli (optional)
```

### Agents

```bash
# Agent Management
kiroforge init-agent ./my-agent                  # Create a new agent
kiroforge init-agent --interactive ./my-agent    # Interactive agent creation
kiroforge validate-agent ./my-agent              # Validate agent structure and security
kiroforge test-agent ./my-agent                  # Run agent behavioral tests
kiroforge export-agent ./my-agent                # Export to Kiro-native JSON

# Agent Templates
kiroforge list-agent-templates                   # List available agent templates
kiroforge init-agent-from-template ./db-agent database-specialist  # Create from template
```

### Collections

```bash
# Collection Management
kiroforge init-collection ./backend-team         # Create a new collection
kiroforge init-collection --interactive ./backend-team  # Interactive creation
kiroforge validate-collection ./backend-team     # Validate collection and all agents
kiroforge test-collection ./backend-team         # Run multi-agent tests
kiroforge export-collection ./backend-team       # Export all agents + manifest

# Collection Templates
kiroforge list-collection-templates              # List available collection templates
kiroforge init-collection-from-template ./team backend-team  # Create from template
```

The `run` command is optional - it lets you test your power against local `kiro-cli` to see how it behaves before sharing it.

### Steering (Generate)

```bash
kiroforge init-steering .kiro/steering/project.md --scope workspace --title "Project Steering"
kiroforge init-steering .kiro/steering/ --mode generate --template common --file api-standards.md --file testing-standards.md
```

### Steering (Wizard)

```bash
kiroforge init-steering .kiro/steering/ --interactive
kiroforge init-steering .kiro/steering/ --mode wizard --template foundational
```

`--interactive` prompts for mode and template; `--mode wizard --template foundational` is the explicit, non-interactive equivalent.
In plain terms: `--interactive` asks you questions. The second command skips the questions and picks the wizard + foundational template for you.

### Steering (AI)

Recommended flags for stable output: `--kiro-wrap never --kiro-trust-none`

```bash
# Reliable single-file AI generation (one kiro-cli call per file)
kiroforge init-steering .kiro/steering/ --mode ai --template common --goal "SaaS API with Stripe billing" --file api-standards.md
kiroforge init-steering .kiro/steering/ --mode ai --template common --goal "Code review checklist that follows OWASP guidance" --file api-standards.md
kiroforge init-steering .kiro/steering/ --mode ai --template common --goal "OWASP-aligned code review" --file api-standards.md --kiro-trust-tools fs_read --kiro-no-interactive

# Skip output cleaning with --raw-output (preserves original kiro-cli output)
kiroforge init-steering .kiro/steering/ --mode ai --template common --goal "SaaS API with Stripe billing" --file api-standards.md --raw-output

# Quick health check for AI functionality
kiroforge ai-test
```

If you pass `--kiro-agent`, use a real agent name from `kiro-cli agent list`.

### Routing and Diagnostics

```bash
kiroforge route "configure mcp service" --powers-dir examples/kiro_powers --file integrations/service.yaml
kiroforge doctor
kiroforge ai-test  # Quick health check for AI steering functionality
```

Interactive prompts (steering):

```
Scope (workspace/global) [workspace]:
Mode (generate/wizard) [generate]:
Template set (foundational/common/blank) [common]:
Files to generate (comma-separated) [...]
```

`init-steering` parameters:

- `PATH`: target file path for the steering document
- `--scope`: `workspace` or `global` (informational label)
- `--title`: heading for the generated markdown

`validate` checks power structure (POWER.md plus referenced resources).\
`validate-steering` checks standalone steering markdown files.

`run-tests` performs a synthetic execution and asserts expected substrings in the harness output.
`run` simulates a single prompt execution and prints a trace.
`route` matches powers by triggers (phrases, domains, file patterns).
`init --interactive` and `init-steering --interactive` support two modes:

- generate: create selected files from a template set
- wizard: ask for purpose/standards/examples and populate each file

Interactive steering templates align with Kiro’s published strategies and generate multiple files:

- Foundational: `product.md`, `tech.md`, `structure.md`
- Common: `api-standards.md`, `testing-standards.md`, `code-conventions.md`, `security-policies.md`, `deployment-workflow.md`

Non-interactive steering flags:

- `--mode`: `generate`, `wizard`, or `ai`
- `--template`: `foundational`, `common`, or `blank`
- `--file`: repeatable file names to generate (defaults to all in the set)
- `--goal`: required for `ai` mode
- `--kiro-no-interactive/--kiro-interactive`: control prompting in `kiro-cli`
- `--kiro-trust-all`: allow all tools (use with care)
- `--kiro-trust-tools`: allow a specific set of tools (repeatable)
- `--kiro-trust-none`: disallow all tools (ai mode, maps to `--trust-tools=`)
- `--kiro-timeout`: timeout for `kiro-cli` calls in seconds
- `--kiro-wrap`: output wrapping mode for `kiro-cli` (auto, never, always)
- `--kiro-pty/--no-kiro-pty`: retry with a pseudo-tty on timeout
- `--kiro-debug`: print the command and surface output on failure
- `--kiro-agent`: use a specific Kiro agent profile
- `--kiro-model`: select a model for Kiro CLI

Note: KiroForge calls `kiro-cli chat` and can run with or without `--no-interactive`. If your version does not support `--no-interactive`, it will retry without it.

AI generation uses single-file approach for reliability. Use `--file` to specify which file to generate.
AI output is normalized to include a top-level heading and required sections per file.
AI mode defaults to `--kiro-trust-none` unless you explicitly allow tools.
`--kiro-wrap=never` avoids line wrapping artifacts in generated markdown.
KiroForge writes the markdown files itself; `kiro-cli` is only used to generate text.

## Doctor

```bash
kiroforge doctor
```

`validate-steering` also checks best-practice heuristics (clear file name, context, examples, and no secrets).

## Scaffolds

Power scaffold created by `kiroforge init ./my-new-power`:

```
my-new-power/
├── POWER.md
├── steering.md
├── tools.yaml
├── hooks.yaml
└── tests/
    └── tests.yaml
```

Steering-only scaffold created by `kiroforge init-steering .kiro/steering/project.md`:

```
.kiro/
└── steering/
    └── project.md
```

## Testing

```bash
uv run python -m pytest
```

## Limitations

- Router is heuristic and uses simple matches (semantic analysis planned)
- SPDX list is minimal and hard-coded for now
