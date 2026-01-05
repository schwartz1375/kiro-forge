meta:
  name: mcp-hook-power
  description: Example power that bundles an MCP tool and a validation hook.
  version: "0.1.0"
  author: KiroForge
  license: MIT
  homepage: https://example.com/mcp-hook-power
triggers:
  phrases:
    - "connect to service"
  domains:
    - "integration"
  files:
    - "integrations/**"
constraints:
  allowed_tools:
    - "filesystem.read"
    - "filesystem.write"
  denied_tools:
    - "network.*"
  requires_network: false
resources:
  steering_files:
    - steering.md
  tools_files:
    - tools.yaml
  hooks_files:
    - hooks.yaml
  assets:
    - templates/usage.md
tests:
  tests_path: tests/tests.yaml
  expected_behaviors:
    - "Configures MCP tool usage"
    - "Blocks unsafe operations via hook"
compatibility:
  kiro_version: ">=0.1"
  platforms:
    - darwin
    - linux
