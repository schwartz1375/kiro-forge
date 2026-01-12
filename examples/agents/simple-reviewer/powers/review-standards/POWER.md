---
meta:
  name: review-standards
  description: Code and document review standards and guidelines
  version: "1.0.0"
  author: "KiroForge Examples"

triggers:
  phrases: ["review", "check", "analyze", "feedback"]
  domains: ["code-review", "documentation"]
  files: ["*.py", "*.js", "*.md", "*.rst"]

constraints:
  allowed_tools: ["filesystem.read", "filesystem.write"]
  denied_tools: ["network.*"]
  requires_network: false

resources:
  steering_files: ["steering.md"]
  tools_files: []
  hooks_files: []
  assets: []

tests:
  tests_path: "tests"
  expected_behaviors:
    - "Provides structured review feedback"
    - "Identifies common code issues"
    - "Suggests specific improvements"

compatibility:
  kiro_version: ">=1.23"
  platforms: ["darwin", "linux"]
---

# Review Standards Power

This power provides standards and guidelines for code and document review processes.