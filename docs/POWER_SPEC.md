# Kiro Power Specification (POWER.md)

This document defines the required and optional fields for a Kiro Power `POWER.md` file.
The file uses YAML format.

## File Location

Each power must include a `POWER.md` at the root of the power directory:

```
/power-name
  ├── POWER.md
  ├── steering.md
  ├── tools.yaml
  ├── hooks.yaml
  └── tests/
```

## Schema

### meta (required)

- `name` (string, required): Power identifier, kebab-case recommended.
- `description` (string, required): Short description of the power.
- `version` (string, required): Semver string.
  - Quote the value (e.g. `"0.1.0"`) to avoid YAML numeric coercion.
- `author` (string, optional): Author or organization.
- `license` (string, optional): SPDX identifier.
- `homepage` (string, optional): URL to docs or repo.

### triggers (optional)

- `phrases` (string[], optional): Example user phrases that should activate the power.
- `domains` (string[], optional): Domain tags used for routing.
- `files` (string[], optional): File patterns that indicate relevance (e.g. `infra/**`).

Routing uses simple substring matches for phrases/domains and glob matches for files.

### constraints (optional)

- `allowed_tools` (string[], optional): Allowed tool patterns (e.g. `filesystem.read`).
- `denied_tools` (string[], optional): Explicitly denied tool patterns.
- `sandbox_notes` (string, optional): Execution environment notes.
- `requires_network` (boolean, optional): Whether network access is required.

### resources (optional)

- `steering_files` (string[], optional): Relative paths to steering files.
- `tools_files` (string[], optional): Relative paths to tool definition files.
- `hooks_files` (string[], optional): Relative paths to hook definition files.
- `assets` (string[], optional): Other bundled assets.

### tests (optional)

- `tests_path` (string, optional): Relative path to a test suite YAML.
- `expected_behaviors` (string[], optional): High-level behavior assertions.

Test cases use `expected` as substring assertions against the harness output.

### compatibility (optional)

- `kiro_version` (string, optional): Minimum Kiro version.
- `platforms` (string[], optional): Supported platforms (e.g. `darwin`, `linux`).

## Example

```yaml
meta:
  name: stripe-payments
  description: Build payment flows with Stripe.
  version: 0.1.0
  author: ExampleCo
  license: MIT
  homepage: https://example.com/stripe-power
triggers:
  phrases:
    - "stripe checkout"
    - "billing and subscriptions"
  domains:
    - payments
    - saas
  files:
    - "billing/**"
constraints:
  allowed_tools:
    - "filesystem.read"
    - "filesystem.write"
  denied_tools:
    - "network.*"
  requires_network: false
resources:
  steering_files:
    - "steering.md"
  tools_files:
    - "tools.yaml"
  hooks_files:
    - "hooks.yaml"
  assets:
    - "templates/checkout.md"
tests:
  tests_path: "tests/tests.yaml"
  expected_behaviors:
    - "Creates a checkout flow using Stripe SDK"
compatibility:
  kiro_version: ">=0.6"
  platforms:
    - darwin
    - linux
```
