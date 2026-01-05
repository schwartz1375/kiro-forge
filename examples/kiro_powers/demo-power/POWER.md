meta:
  name: demo-power
  description: Demo power for KiroForge validation.
  version: "0.1.0"
  author: KiroForge
  license: MIT
  homepage: https://example.com/demo-power
triggers:
  phrases:
    - "demo power"
  domains:
    - "demo"
  files:
    - "demo/**"
constraints:
  allowed_tools:
    - "filesystem.read"
    - "filesystem.write"
  denied_tools:
    - "network.*"
resources:
  steering_files:
    - steering.md
  tools_files:
    - tools.yaml
  hooks_files:
    - hooks.yaml
  assets: []
tests:
  tests_path: tests/tests.yaml
  expected_behaviors:
    - "Demonstrates validation and testing flow"
compatibility:
  kiro_version: ">=0.1"
  platforms:
    - darwin
    - linux
