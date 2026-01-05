meta:
  name: kiroforge-framework
  description: Core framework documentation for authoring, validating, and testing Kiro Powers.
  version: "0.1.0"
  author: KiroForge
  license: MIT
  homepage: https://github.com/kiroforge/kiroforge
triggers:
  phrases:
    - "power framework"
    - "kiro powers"
constraints:
  allowed_tools:
    - "filesystem.read"
    - "filesystem.write"
  denied_tools:
    - "network.*"
resources:
  steering_files: []
  tools_files: []
  hooks_files: []
  assets: []
tests:
  tests_path: null
  expected_behaviors: []
compatibility:
  kiro_version: ">=0.1"
  platforms:
    - darwin
    - linux
