# KiroForge Custom Agent Support: Concept and Fit

## Summary

This proposal extends KiroForge from Powers (passive context + tooling) to Custom Agents (active identity + invocation). It aligns with Kiro's existing Custom Agent architecture and maintains KiroForge's focus on authoring, validation, and testing.

## Key Design Decisions

### 1. Collection Roles: Purely Descriptive
**Decision**: Roles in `collection.yaml` are descriptive labels only and do NOT participate in subagent resolution.

- **Subagent Resolution**: Uses module directory names (`allowed_specialists: ["database-specialist"]`)
- **Role Usage**: Human-readable labels for coordination patterns (`"database questions -> database_expert"`)
- **Rationale**: Keeps resolution predictable and avoids role-to-module mapping complexity

### 2. Network Access: Collection Policy Wins with Opt-out
**Decision**: Collection `requires_network` policy overrides agent settings unless agent explicitly opts out.

- **Default**: Collection network policy takes precedence over agent requests
- **Agent Restriction**: Agents can be more restrictive than collection (always allowed)
- **Opt-out**: Agents can override with `opt_out_collection_constraints: true` + justification
- **Rationale**: Security governance at collection level with audit trail for exceptions

### 3. Power Dependencies: Flat Model Only
**Decision**: No recursive power dependencies - all powers must be explicitly listed in agent.yaml.

- **Explicit Listing**: Agent must list all required powers directly
- **No Transitive Dependencies**: Powers cannot automatically include other powers
- **Validation**: Each power in the list is validated independently
- **Rationale**: Explicit is better than implicit - agent author sees all dependencies

### 4. Subagent Resolution: Module Names Only
**Decision**: `allowed_specialists` must use module directory names, not collection roles.

- **Module Names**: `allowed_specialists: ["database-specialist"]` (maps to `./agents/database-specialist/`)
- **No Role Resolution**: Cannot use `allowed_specialists: ["database_expert"]` even if role exists
- **Consistency**: Aligns with "roles are purely descriptive" principle
- **Rationale**: Predictable resolution without collection dependency

## Does it make sense for this project?

### Why it fits
- KiroForge already provides schema validation, scaffolding, and behavioral tests for Power modules
- Custom Agent configs suffer from the same drift and copy-paste problems that Powers solved
- Exporting Kiro-native agent configs aligns with KiroForge's role as a local authoring tool
- Kiro already has Custom Agents - we're just adding proper tooling for them

### Positioning
- **Scope**: Authoring and validation only (not execution or orchestration)
- **Alignment**: Uses Kiro's established terminology (Custom Agents, Subagents, Steering)
- **Architecture**: Builds on existing Power validation and testing patterns

## Core Model

```
Power        = context + tools + constraints (passive, loaded by triggers)
Custom Agent = identity + powers + subagent rules (active, called directly)
```

## Custom Agent Module

### Purpose
Define a Custom Agent's identity, power dependencies, and subagent capabilities with schema validation and behavioral tests.

### Structure
```
backend-specialist/
├── agent.yaml
├── system-prompt.md
├── powers/
│   ├── database-patterns/
│   └── api-standards/
└── tests/
    ├── test_responses.yaml
    └── test_delegation.yaml
```

### Agent Schema (agent.yaml)
```yaml
meta:
  name: backend-specialist
  description: Database and API expert
  version: "1.0.0"
  author: Team Backend

identity:
  prompt_file: system-prompt.md
  expertise: ["databases", "apis", "backend-patterns"]

powers:
  # Simple file references - flat model
  - "./powers/database-patterns"
  - "./powers/api-standards"

constraints:
  allowed_tools: ["filesystem.*", "database.*"]
  denied_tools: ["network.external.*"]
  requires_network: false
  
subagents:
  # Optional - only for agents that spawn subagents
  allowed_specialists: ["database-specialist", "api-reviewer"]
  max_concurrent: 3
  delegation_rules:
    - "Delegate complex queries to database-specialist"
    - "Route API reviews to api-reviewer"
  
  # Security: Confused Deputy Protection
  delegation_security:
    constraint_intersection: true  # Subagent inherits delegator's constraints (default)
    audit_trail: true             # Log all delegations with context
    require_justification: false  # Optional: require delegation reasoning
    allowed_elevations: []        # Explicit list of permissions subagents can exceed

tests:
  test_path: "tests/"
  expected_behaviors:
    - "Suggests database best practices"
    - "Reviews API designs for consistency"
    - "Can delegate to appropriate specialists"

compatibility:
  kiro_version: ">=1.23"
  platforms: ["darwin", "linux"]
```

### Key Design Principles

1. **Flat Power References**: No complex dependency resolution - just file paths
2. **File-based System Prompts**: Separate .md files for better editing
3. **Reuse Power Constraints**: Same allowed_tools/denied_tools model
4. **Optional Subagent Config**: Only include when the agent spawns subagents
5. **Behavioral Testing**: Same pattern as Powers for consistency

### Power Resolution
- Powers referenced by local filesystem path (no registry complexity)
- Paths are resolved relative to the agent module root
- Directory references must contain a valid `POWER.md` file (consistent with existing KiroForge)
- `POWER.md` must pass `kiroforge validate` successfully
- All resources referenced in `POWER.md` must exist and be readable
- **No recursive dependencies**: All required powers must be explicitly listed in agent.yaml
- **Flat dependency model**: Powers cannot automatically include other powers
- Export bundles resolved power references into Kiro-native agent JSON

### Subagent Resolution Rules

**Context-Aware Resolution Strategy:**
- **Collection Context**: Use collection's agent registry (explicit control)
- **Standalone Context**: Look for sibling directories (convention-based)
- **Collection Override**: Collection registry takes precedence over sibling discovery

**Resolution Algorithm:**
```python
def resolve_subagent(specialist_name, agent_context):
    if agent_context.is_in_collection:
        # Collection context: use collection's explicit agent registry
        collection_agent = agent_context.collection.find_agent(specialist_name)
        if collection_agent:
            return collection_agent.path
        else:
            raise SubagentNotFound(f"Agent '{specialist_name}' not found in collection registry")
    else:
        # Standalone context: look for sibling directory
        sibling_path = agent_context.agent_dir.parent / specialist_name
        if sibling_path.exists() and (sibling_path / "agent.yaml").exists():
            return sibling_path
        else:
            raise SubagentNotFound(f"Sibling agent '{specialist_name}' not found at {sibling_path}")
```

**Standalone Agent Structure:**
```
my-workspace/
├── agents/
│   ├── coordinator-agent/
│   │   └── agent.yaml          # Can reference database-specialist, api-reviewer
│   ├── database-specialist/
│   │   └── agent.yaml
│   └── api-reviewer/
│       └── agent.yaml
```

**Collection Agent Structure:**
```
backend-team/
├── collection.yaml             # Explicit agent registry
├── agents/
│   ├── database-specialist/    # Registered in collection.yaml
│   ├── api-reviewer/          # Registered in collection.yaml  
│   └── coordinator/           # Can delegate to registered agents
```

**Resolution Examples:**

*Standalone Context:*
```yaml
# agents/coordinator-agent/agent.yaml
subagents:
  allowed_specialists: ["database-specialist", "api-reviewer"]
  
# Resolution:
# "database-specialist" -> ../database-specialist/ (sibling directory)
# "api-reviewer" -> ../api-reviewer/ (sibling directory)
```

*Collection Context:*
```yaml
# backend-team/collection.yaml
agents:
  - path: "./agents/database-specialist"
    role: "database_expert"
  - path: "./agents/api-reviewer" 
    role: "api_specialist"

# backend-team/agents/coordinator/agent.yaml  
subagents:
  allowed_specialists: ["database-specialist", "api-reviewer"]
  
# Resolution:
# "database-specialist" -> ./agents/database-specialist/ (from collection registry)
# "api-reviewer" -> ./agents/api-reviewer/ (from collection registry)
```

**Role Usage:**
- Roles in `collection.yaml` are purely descriptive labels
- Used for human readability and coordination patterns  
- Not used for subagent resolution (always use module directory names)

**Validation Rules:**
- **Standalone**: Each specialist must exist as sibling directory with valid `agent.yaml`
- **Collection**: Each specialist must be registered in `collection.yaml` agents list
- **Module Names**: `allowed_specialists` must use directory names, not role names
- **Existence Check**: Target agent directory must contain valid `agent.yaml`

**Context Benefits:**

*Standalone Agents:*
- **Flexibility**: Quick multi-agent setups without collection overhead
- **Convention**: Predictable sibling directory resolution
- **Development**: Easy testing of agent interactions
- **Portability**: Self-contained agent groups

*Collection Agents:*
- **Control**: Explicit agent registry with roles and metadata
- **Governance**: Centralized agent management and constraints
- **Documentation**: Clear coordination patterns and shared context
- **Scale**: Manage large numbers of related agents

### Delegation Security: Confused Deputy Protection

**The Problem**: A "confused deputy" attack occurs when Agent A (limited permissions) delegates to Agent B (broader permissions) and tricks Agent B into performing actions Agent A isn't authorized to do.

**Example Scenario:**
```yaml
# Agent A: limited-reviewer (can only read files)
constraints:
  allowed_tools: ["filesystem.read"]
  denied_tools: ["filesystem.write", "network.*"]

# Agent B: database-specialist (can modify databases)  
constraints:
  allowed_tools: ["filesystem.*", "database.*", "network.internal"]
  
# Attack: Agent A delegates "review this schema" but includes malicious instructions
# that trick Agent B into executing unauthorized database modifications
```

**Security Model: Constraint Intersection by Default**

```yaml
subagents:
  delegation_security:
    constraint_intersection: true  # Default: subagent inherits delegator's constraints
    audit_trail: true             # Log all delegations with context
    require_justification: false  # Optional: require delegation reasoning
    allowed_elevations: []        # Explicit list of permissions subagents can exceed
```

**Disabling Constraint Intersection (Dangerous - Requires Explicit Intent)**

```yaml
# Option 1: Full delegation with explicit acknowledgment
subagents:
  delegation_security:
    constraint_intersection: false
    allow_full_delegation: true  # REQUIRED when constraint_intersection: false
    justification: "Coordinator needs to delegate with full subagent permissions for complex workflows"
    audit_trail: true           # Still required for security review

# Option 2: Partial elevation with specific permissions
subagents:
  delegation_security:
    constraint_intersection: false
    allowed_elevations:         # REQUIRED when constraint_intersection: false
      - tool_pattern: "database.*"
        justification: "Database specialist needs full DB access for migrations"
      - tool_pattern: "network.internal"
        justification: "API calls to internal services for validation"
    audit_trail: true
```

**Validation Rules for Disabling Intersection:**
- `constraint_intersection: false` MUST have either:
  - `allow_full_delegation: true` + `justification` (full subagent permissions)
  - Non-empty `allowed_elevations` (specific permission grants)
- Cannot disable intersection without explicit intent
- `audit_trail` cannot be disabled when `constraint_intersection: false`

**Constraint Resolution Algorithm:**
```python
def resolve_delegation_constraints(delegator_constraints, subagent_constraints, security_config):
    if security_config.constraint_intersection:
        # Secure default: intersection of permissions
        effective_allowed = intersection(delegator_constraints.allowed_tools, 
                                       subagent_constraints.allowed_tools)
        effective_denied = union(delegator_constraints.denied_tools,
                               subagent_constraints.denied_tools)
    else:
        # Dangerous mode: validate explicit intent
        if security_config.allow_full_delegation:
            # Use full subagent permissions
            effective_allowed = subagent_constraints.allowed_tools
            effective_denied = subagent_constraints.denied_tools
        else:
            # Start with delegator constraints, add elevations
            effective_allowed = delegator_constraints.allowed_tools.copy()
            effective_denied = delegator_constraints.denied_tools.copy()
            
            # Apply explicit elevations
            for elevation in security_config.allowed_elevations:
                effective_allowed.add(elevation.tool_pattern)
    
    return ConstraintSet(allowed=effective_allowed, denied=effective_denied)
```

**Elevation with Audit Trail:**
```yaml
# When subagent needs broader permissions than delegator
subagents:
  delegation_security:
    constraint_intersection: true
    allowed_elevations:
      - tool_pattern: "database.write"
        justification: "Schema migrations require write access"
        audit_level: "high"  # Extra logging for elevated permissions
```

**Security Benefits:**
1. **Principle of Least Privilege**: Subagents can't exceed delegator's authority by default
2. **Explicit Elevation**: Any permission escalation must be declared and justified
3. **Audit Trail**: All delegations logged with context for security review
4. **Attack Prevention**: Malicious prompts can't trick subagents into unauthorized actions

### Export Mapping (Draft)
- `meta` -> Kiro agent metadata fields (name/description/version/author)
- `identity.prompt_file` -> system prompt content
- `powers` -> Kiro agent power list (resolved, validated)
- `constraints` -> Kiro tool allow/deny list and network flag
- `subagents` -> Kiro subagent policy (allowed specialists + delegation rules)

### Benefits
- **Schema validation** before runtime deployment
- **Behavioral testing** for agent responses and delegation patterns
- **Power reuse** across multiple agents
- **Export compatibility** with Kiro CLI agent format
- **Familiar patterns** - same validation/testing approach as Powers

## Validation Layers

- **Schema**: agent.yaml structure and required fields
- **Dependencies**: referenced powers exist and validate successfully  
- **Constraints**: tool permissions are valid and consistent
- **Behavioral**: agent responses match expected patterns
- **Subagent**: delegation rules reference valid specialist agents

## Implementation Phases

### Phase 1: Basic Custom Agent Support
- `kiroforge init-agent ./my-agent` - scaffold agent structure
- `kiroforge validate-agent ./my-agent` - schema and dependency validation
- `kiroforge export-agent ./my-agent` - generate Kiro-compatible JSON

### Phase 2: Testing and Behavioral Validation  
- `kiroforge test-agent ./my-agent` - run behavioral tests
- Agent test harness for response validation
- Subagent delegation testing

### Phase 3: Agent Collections (Multi-Agent Support)
- `kiroforge init-collection ./backend-team` - scaffold agent collection
- `kiroforge validate-collection ./backend-team` - validate all agents + shared context
- `kiroforge test-collection ./backend-team` - run multi-agent scenarios

### Phase 4: Advanced Features
- Agent templates for common patterns
- Cross-collection dependency validation
- Integration with existing Power workflows

## Agent Collections (Phase 3)

### Purpose
Manage shared context and coordination across multiple related agents to ensure consistency and enable collaboration.

### Structure
```
backend-team/
├── collection.yaml
├── shared/
│   ├── powers/
│   │   ├── company-standards/
│   │   ├── database-schemas/
│   │   └── api-conventions/
│   └── steering/
│       ├── team-practices.md
│       └── code-review-standards.md
├── agents/
│   ├── database-specialist/
│   ├── api-reviewer/
│   └── backend-coordinator/
└── tests/
    ├── test_multi_agent_review.yaml
    └── test_database_migration_workflow.yaml
```

### Collection Schema (collection.yaml)
```yaml
meta:
  name: backend-team
  description: Database and API specialists working together
  version: "1.0.0"
  author: Backend Team

shared_context:
  powers:
    # Shared powers available to all agents in collection
    - "./shared/powers/company-standards"
    - "./shared/powers/database-schemas" 
    - "./shared/powers/api-conventions"
  
  steering:
    # Common steering files for consistent behavior
    - "./shared/steering/team-practices.md"
    - "./shared/steering/code-review-standards.md"
  
  constraints:
    # Collection-wide constraints applied to all agents
    # Effective tools = intersection of collection and agent allowed_tools,
    # and union of denied_tools.
    allowed_tools: ["filesystem.*", "database.*"]
    denied_tools: ["network.external.*"]
    max_concurrent_agents: 5
    requires_network: false

agents:
  # Reference existing agent modules with roles
  - path: "./agents/database-specialist"
    role: "database_expert"
    description: "Handles database design and optimization"
  
  - path: "./agents/api-reviewer" 
    role: "api_specialist"
    description: "Reviews API designs for consistency"
  
  - path: "./agents/backend-coordinator"
    role: "coordinator"
    can_spawn_subagents: true
    description: "Coordinates complex multi-agent tasks"

coordination:
  # Simple handoff rules for agent collaboration
  patterns:
    - "database questions -> database_expert"     # Uses role for readability
    - "api reviews -> api_specialist"             # Uses role for readability  
    - "complex tasks -> coordinator spawns subagents"
  
  shared_memory:
    # Optional: shared context between agents in workflows
    enabled: true
    scope: "collection"  # collection | workspace | global

tests:
  test_path: "tests/"
  scenarios:
    - name: "Multi-agent code review workflow"
      description: "Coordinate database and API review"
    - name: "Database migration with API updates"
      description: "End-to-end migration coordination"

compatibility:
  kiro_version: ">=1.23"
  platforms: ["darwin", "linux"]
```

### Key Benefits of Collections

1. **Shared Context Management**: All agents inherit common powers and steering
2. **Consistency**: Unified standards across related agents
3. **Coordination**: Simple rules for when agents should collaborate
4. **Efficiency**: Shared resources aren't duplicated across agents
5. **Testing**: Validate multi-agent scenarios end-to-end
6. **Scalability**: Collections can reference other collections

### Collection Validation
- **Schema**: collection.yaml structure and agent references
- **Dependencies**: all referenced agents and shared resources exist
- **Consistency**: agent constraints don't conflict with collection constraints
- **Coordination**: handoff patterns reference valid agent roles
- **Integration**: shared powers validate successfully across all agents

### Multi-Agent Testing
```yaml
# tests/test_multi_agent_review.yaml
scenarios:
  - name: "Database schema review"
    prompt: "Review this database migration for our user service"
    expected_flow:
      - coordinator: "Analyzes request and delegates"
      - database_expert: "Reviews schema changes"        # Role used for test readability
      - api_specialist: "Checks API compatibility"       # Role used for test readability
    expected_outcomes:
      - "Schema follows company standards"
      - "API changes are backward compatible"
      - "Migration plan is provided"
    subagent_calls:
      # Technical validation uses module names
      - agent: "database-specialist"                      # Module name for validation
        expected_delegation: true
      - agent: "api-reviewer"                             # Module name for validation
        expected_delegation: true
```

## Export Mapping: KiroForge -> Kiro Native JSON

### Single Agent Export

| KiroForge YAML Field | Kiro JSON Field | Notes |
|---------------------|-----------------|-------|
| `meta.name` | `name` | Agent identifier |
| `meta.description` | `description` | Agent description |
| `identity.prompt_file` | `prompt` | Content of system-prompt.md file |
| `POWER.md` tool resources | `tools` | Merged tool definitions from referenced powers |
| `POWER.md` tool resources | `mcpServers` | MCP server configs from power tool files |
| `constraints.allowed_tools` | `allowedTools` | Tools that can be used without prompting |
| `constraints.denied_tools` | `disabledTools` | Tools to omit when calling the agent |
| `POWER.md` steering resources | `prompt` (appended) | Steering content appended to system prompt |
| `subagents.allowed_specialists` | `_kiroforge.subagents` | KiroForge extension for subagent management |

### Sample Export

**KiroForge Input (agent.yaml):**
```yaml
meta:
  name: backend-specialist
  description: Database and API expert
  
identity:
  prompt_file: system-prompt.md
  
powers:
  - "./powers/database-patterns"
  - "./powers/api-standards"
  
constraints:
  allowed_tools: ["filesystem.*", "database.*"]
  denied_tools: ["network.external.*"]
  
subagents:
  allowed_specialists: ["database-specialist"]
  max_concurrent: 3
```

**Kiro Native JSON Output:**
```json
{
  "name": "backend-specialist",
  "description": "Database and API expert",
  "prompt": "You are a backend specialist expert in databases and APIs.\n\n# Database Patterns\n[Content from database-patterns/steering.md]\n\n# API Standards\n[Content from api-standards/steering.md]",
  "mcpServers": {
    "database-tools": {
      "command": "uvx",
      "args": ["database-mcp-server"],
      "autoApprove": ["query_schema", "validate_migration"]
    }
  },
  "tools": [
    "filesystem.read",
    "filesystem.write", 
    "database.query",
    "database.migrate"
  ],
  "allowedTools": [
    "filesystem.*",
    "database.*"
  ],
  "disabledTools": [
    "network.external.*"
  ],
  "_kiroforge": {
    "subagents": {
      "allowed_specialists": ["database-specialist"],
      "max_concurrent": 3
    },
    "source_powers": [
      "./powers/database-patterns",
      "./powers/api-standards"
    ]
  }
}
```

### Collection Export

**Collections export as multiple individual agent JSON files plus a manifest:**

**KiroForge Input (collection.yaml):**
```yaml
meta:
  name: backend-team
  
shared_context:
  powers: ["./shared/powers/company-standards"]
  steering: ["./shared/steering/team-practices.md"]
  
agents:
  - path: "./agents/database-specialist"
    role: "database_expert"
  - path: "./agents/api-reviewer"
    role: "api_specialist"
```

**Export Output:**
```
exported/
├── backend-team-manifest.json
├── database-specialist.json
└── api-reviewer.json
```

**backend-team-manifest.json:**
```json
{
  "collection": "backend-team",
  "agents": [
    {
      "name": "database-specialist",
      "role": "database_expert",
      "file": "database-specialist.json"
    },
    {
      "name": "api-reviewer", 
      "role": "api_specialist",
      "file": "api-reviewer.json"
    }
  ],
  "shared_context": {
    "powers": ["company-standards"],
    "steering": ["team-practices.md"]
  }
}
```

### Export Process

1. **Resolve Power Dependencies**: Load and validate all referenced powers
2. **Merge Steering Content**: Combine power steering files into agent prompt
3. **Consolidate Tool Definitions**: Merge MCP servers and tool lists from powers
4. **Apply Constraints**: Merge collection and agent-level constraints
5. **Generate Native JSON**: Export in Kiro's expected format
6. **Preserve Metadata**: Store KiroForge-specific data in `_kiroforge` field

### Validation Before Export

- All referenced powers must validate successfully
- Tool constraints must not conflict between powers and agent config
- MCP server names must not collide across powers
- Steering files must exist and be readable
- Agent names must be valid Kiro identifiers

### Resource Collision Detection and Resolution

When an agent references multiple powers, name collisions can occur across tools, MCP servers, and steering content. KiroForge uses a **Fail Fast + Last-Wins with Warnings** approach:

#### Tool Name Collisions
```yaml
# powers/database-patterns/tools.yaml
tools:
  - name: "query"
    command: "psql -c"
    
# powers/api-standards/tools.yaml  
tools:
  - name: "query"  # ❌ Collision detected
    command: "curl -X GET"

# Resolution Strategy:
# 1. DETECT: Validation fails with collision error
# 2. RESOLVE: Agent must explicitly handle collision
```

**Resolution Options:**
```yaml
# Option 1: Agent excludes conflicting tools
# agent.yaml
powers:
  - path: "./powers/database-patterns"
  - path: "./powers/api-standards"
    exclude_tools: ["query"]  # Explicit exclusion

# Option 2: Agent renames conflicting tools  
# agent.yaml
powers:
  - path: "./powers/database-patterns"
  - path: "./powers/api-standards"
    tool_aliases:
      query: "api_query"  # Rename to avoid collision
```

#### MCP Server Name Collisions
```yaml
# powers/database-patterns/tools.yaml
mcpServers:
  validator:
    command: "uvx database-validator"
    
# powers/api-standards/tools.yaml
mcpServers:
  validator:  # ❌ Same server name
    command: "uvx api-validator"

# Validation Error:
# "MCP server name collision: 'validator' defined in both database-patterns and api-standards"
# "Resolution: Use server_aliases in agent.yaml or rename servers in power definitions"
```

**Resolution:**
```yaml
# agent.yaml
powers:
  - path: "./powers/database-patterns"
  - path: "./powers/api-standards"
    server_aliases:
      validator: "api_validator"  # Rename conflicting server
```

#### Steering Content Collisions
```yaml
# powers/database-patterns/steering.md
# Database Best Practices
Use PostgreSQL for all relational data.

# powers/api-standards/steering.md  
# Database Best Practices  ❌ Same heading
Use MongoDB for document storage.
```

**Resolution Strategy: Last-Wins with Warnings**
```yaml
# Export behavior:
# 1. WARN: Generate collision warning in export metadata
# 2. MERGE: Later power content overwrites earlier content
# 3. AUDIT: Track collision in _kiroforge metadata

# Final merged steering content:
# Database Best Practices
# Use MongoDB for document storage.  ← api-standards wins (last in list)
```

#### Collision Validation Schema
```yaml
# agent.yaml enhanced schema
powers:
  type: array
  items:
    oneOf:
      - type: string  # Simple path reference
      - type: object  # Advanced with collision resolution
        required: [path]
        properties:
          path:
            type: string
          exclude_tools:
            type: array
            items:
              type: string
          tool_aliases:
            type: object
            additionalProperties:
              type: string
          server_aliases:
            type: object
            additionalProperties:
              type: string
          exclude_steering_sections:
            type: array
            items:
              type: string  # Heading names to exclude
```

#### Export Collision Metadata
```json
{
  "_kiroforge": {
    "collision_resolution": {
      "tool_collisions": [
        {
          "name": "query",
          "powers": ["database-patterns", "api-standards"],
          "resolution": "excluded_from_api-standards",
          "final_source": "database-patterns"
        }
      ],
      "server_collisions": [
        {
          "name": "validator", 
          "powers": ["database-patterns", "api-standards"],
          "resolution": "aliased_api-standards_to_api_validator",
          "final_names": ["validator", "api_validator"]
        }
      ],
      "steering_collisions": [
        {
          "section": "Database Best Practices",
          "powers": ["database-patterns", "api-standards"], 
          "resolution": "last_wins",
          "final_source": "api-standards",
          "warning": "Content from database-patterns was overwritten"
        }
      ]
    }
  }
}
```

This mapping ensures KiroForge agents can be directly imported into Kiro CLI without manual conversion.

## Detailed Specifications

### Power Directory Validation Rules

**Required Structure:**
```
powers/database-patterns/
├── POWER.md              # Required - must pass kiroforge validate
├── steering.md           # Referenced in POWER.md resources
├── tools.yaml           # Referenced in POWER.md resources  
└── tests/               # Referenced in POWER.md tests
    └── tests.yaml
```

**Validation Logic:**
1. Each power reference in `agent.yaml` must point to a directory
2. Directory must contain `POWER.md` (not `power.yaml` - consistent with existing KiroForge)
3. `POWER.md` must pass `kiroforge validate` successfully
4. All resources referenced in `POWER.md` must exist and be readable
5. **No transitive dependencies**: Powers cannot reference other powers

### Constraint Resolution Rules

**Collection vs Agent Constraints:**
```yaml
# collection.yaml
shared_context:
  constraints:
    allowed_tools: ["filesystem.*", "database.*", "network.read"]
    denied_tools: ["network.write", "system.admin"]

# agent.yaml
constraints:
  allowed_tools: ["filesystem.read", "database.query"]  # Must be subset
  denied_tools: ["network.*"]                           # Can be more restrictive
  opt_out_collection_constraints: false                 # Default: must comply
  opt_out_justification: ""                            # Required if opt_out=true
```

**Resolution Algorithm:**
1. **Default**: `agent.allowed_tools = intersection(collection.allowed_tools, agent.allowed_tools)`
2. **Default**: `agent.denied_tools = union(collection.denied_tools, agent.denied_tools)`
3. **Network Access**: Collection `requires_network` policy takes precedence unless agent opts out
4. **Opt-out**: If `opt_out_collection_constraints: true`, use agent constraints directly
5. **Validation**: Opt-out requires non-empty `opt_out_justification`

**Network Access Resolution:**
```python
def resolve_network_access(collection_network, agent_network, agent_opt_out):
    if agent_opt_out:
        return agent_network  # Agent overrides with justification
    
    if collection_network == False and agent_network == True:
        # Agent wants network but collection denies - collection wins
        return False
    
    return agent_network  # Agent can be more restrictive than collection
```

### Complete Schema Definitions

#### agent.yaml Schema
```yaml
# JSON Schema equivalent for validation
type: object
required: [meta, identity, powers, constraints]
properties:
  meta:
    type: object
    required: [name, description, version]
    properties:
      name: 
        type: string
        pattern: "^[a-zA-Z0-9_-]+$"  # Valid Kiro agent name
      description: 
        type: string
        minLength: 10
        maxLength: 500
      version: 
        type: string
        pattern: "^\\d+\\.\\d+\\.\\d+$"  # Semantic versioning
      author: 
        type: string
        
  identity:
    type: object
    required: [prompt_file]
    properties:
      prompt_file: 
        type: string
        pattern: "\\.md$"  # Must be markdown file
      expertise: 
        type: array
        items:
          type: string
          
  powers:
    type: array
    minItems: 1
    items:
      type: string
      pattern: "^\\./.*"  # Must be relative path
      
  constraints:
    type: object
    properties:
      allowed_tools:
        type: array
        items:
          type: string
          pattern: "^[a-zA-Z0-9_.*-]+$"  # Valid tool pattern
      denied_tools:
        type: array
        items:
          type: string
      requires_network:
        type: boolean
        default: false
      opt_out_collection_constraints:
        type: boolean
        default: false
      opt_out_justification:
        type: string
        # Required if opt_out_collection_constraints is true
        
  subagents:
    type: object
    properties:
      allowed_specialists:
        type: array
        items:
          type: string
          pattern: "^[a-zA-Z0-9_-]+$"  # Must match agent module directory names
      max_concurrent:
        type: integer
        minimum: 1
        maximum: 10
        default: 3
      delegation_rules:
        type: array
        items:
          type: string
      delegation_security:
        type: object
        properties:
          constraint_intersection:
            type: boolean
            default: true
            description: "Subagents inherit delegator's constraints (secure default)"
          audit_trail:
            type: boolean
            default: true
            description: "Log all delegation requests with context"
          require_justification:
            type: boolean
            default: false
            description: "Require explanation for each delegation"
          allow_full_delegation:
            type: boolean
            default: false
            description: "Allow subagent to use full permissions (requires justification)"
          justification:
            type: string
            description: "Required when allow_full_delegation: true or constraint_intersection: false"
          allowed_elevations:
            type: array
            items:
              type: object
              required: [tool_pattern, justification]
              properties:
                tool_pattern:
                  type: string
                  description: "Tool pattern subagent can use beyond delegator's permissions"
                justification:
                  type: string
                  description: "Why this elevation is needed"
                audit_level:
                  enum: ["low", "medium", "high"]
                  default: "medium"
        # Validation: if constraint_intersection: false, must have either:
        # - allow_full_delegation: true + justification
        # - non-empty allowed_elevations
          
  tests:
    type: object
    required: [test_path, expected_behaviors]
    properties:
      test_path:
        type: string
      expected_behaviors:
        type: array
        minItems: 1
        items:
          type: string
          
  compatibility:
    type: object
    properties:
      kiro_version:
        type: string
        pattern: "^>=\\d+\\.\\d+$"
      platforms:
        type: array
        items:
          enum: ["darwin", "linux", "windows"]
```

#### collection.yaml Schema
```yaml
type: object
required: [meta, shared_context, agents]
properties:
  meta:
    type: object
    required: [name, description, version]
    properties:
      name:
        type: string
        pattern: "^[a-zA-Z0-9_-]+$"
      description:
        type: string
      version:
        type: string
        pattern: "^\\d+\\.\\d+\\.\\d+$"
      author:
        type: string
        
  shared_context:
    type: object
    properties:
      powers:
        type: array
        items:
          type: string
          pattern: "^\\./.*"
      steering:
        type: array
        items:
          type: string
          pattern: "\\.md$"
      constraints:
        type: object
        properties:
          allowed_tools:
            type: array
            items:
              type: string
          denied_tools:
            type: array
            items:
              type: string
          max_concurrent_agents:
            type: integer
            minimum: 1
            maximum: 20
            default: 5
          requires_network:
            type: boolean
            
  agents:
    type: array
    minItems: 1
    items:
      type: object
      required: [path, role]
      properties:
        path:
          type: string
          pattern: "^\\./.*"
        role:
          type: string
          pattern: "^[a-zA-Z0-9_]+$"  # Descriptive label, not used for resolution
        description:
          type: string
        can_spawn_subagents:
          type: boolean
          default: false
          
  coordination:
    type: object
    properties:
      patterns:
        type: array
        items:
          type: string
          pattern: ".* -> .*"  # Must contain arrow pattern, can use roles for readability
      shared_memory:
        type: object
        properties:
          enabled:
            type: boolean
            default: true
          scope:
            enum: ["collection", "workspace", "global"]
            default: "collection"
```

### Error Cases and Validation

#### Constraint Conflicts
```yaml
# ERROR: Agent requests tools not allowed by collection
# collection.yaml
shared_context:
  constraints:
    allowed_tools: ["filesystem.*", "database.*"]

# agent.yaml  
constraints:
  allowed_tools: ["filesystem.*", "network.*"]  # ❌ network.* not in collection
  
# Validation Error:
# "Agent 'backend-specialist' requests tools not allowed by collection: network.*"
# "Either remove from agent or add to collection allowed_tools"
```

#### Missing Subagent References

**Standalone Context Errors:**
```yaml
# ERROR: Sibling agent not found
# agents/coordinator/agent.yaml
subagents:
  allowed_specialists: ["database-specialist", "missing-agent"]  # ❌ missing-agent not found

# Directory structure:
# agents/
# ├── coordinator/
# ├── database-specialist/  ✅ Found
# └── api-reviewer/         ❌ missing-agent not found

# Validation Error:
# "Sibling agent 'missing-agent' not found at ../missing-agent/"
# "Available sibling agents: database-specialist, api-reviewer"
# "Create agent: mkdir ../missing-agent && kiroforge init-agent ../missing-agent"
```

**Collection Context Errors:**
```yaml
# ERROR: Agent not registered in collection
# backend-team/agents/coordinator/agent.yaml
subagents:
  allowed_specialists: ["database-specialist", "unregistered-agent"]  # ❌ not in collection

# backend-team/collection.yaml
agents:
  - path: "./agents/database-specialist"
    role: "database_expert"
  # ❌ unregistered-agent not in collection registry

# Validation Error:
# "Agent 'unregistered-agent' not found in collection registry"
# "Available agents in collection: database-specialist"
# "Add to collection.yaml or create new agent module"
```

**Invalid Agent Module:**
```yaml
# ERROR: Agent directory exists but missing agent.yaml
# agents/coordinator/agent.yaml
subagents:
  allowed_specialists: ["broken-agent"]

# Directory structure:
# agents/
# ├── coordinator/
# └── broken-agent/          ❌ Missing agent.yaml
#     └── README.md

# Validation Error:
# "Agent 'broken-agent' found at ../broken-agent/ but missing agent.yaml"
# "Run 'kiroforge init-agent ../broken-agent' to create valid agent structure"
```

#### Role vs Module Name Confusion

**Collection Context - Role vs Module Name:**
```yaml
# ERROR: Using role name instead of module name
# backend-team/collection.yaml
agents:
  - path: "./agents/database-specialist"
    role: "db_expert"

# backend-team/agents/coordinator/agent.yaml (INCORRECT)
subagents:
  allowed_specialists: ["db_expert"]  # ❌ Role name, not module name

# Validation Error:
# "Agent 'db_expert' not found in collection registry"
# "Did you mean 'database-specialist'? (role: db_expert)"
# "Use module names in allowed_specialists, not role names"

# backend-team/agents/coordinator/agent.yaml (CORRECT)
subagents:
  allowed_specialists: ["database-specialist"]  # ✅ Module name
```

**Standalone Context - Directory Name Required:**
```yaml
# ERROR: Using descriptive name instead of directory name
# agents/coordinator/agent.yaml (INCORRECT)
subagents:
  allowed_specialists: ["database_expert"]  # ❌ Not a directory name

# Directory structure:
# agents/
# ├── coordinator/
# └── database-specialist/  ← Actual directory name

# Validation Error:
# "Sibling agent 'database_expert' not found at ../database_expert/"
# "Did you mean 'database-specialist'?"
# "Use actual directory names in allowed_specialists"

# agents/coordinator/agent.yaml (CORRECT)
subagents:
  allowed_specialists: ["database-specialist"]  # ✅ Actual directory name
```

#### Invalid Power References
```yaml
# ERROR: Power directory missing POWER.md
# agent.yaml
powers:
  - "./powers/broken-power"  # Directory exists but no POWER.md

# Validation Error:
# "Power './powers/broken-power' missing required POWER.md file"
# "Run 'kiroforge init ./powers/broken-power' to create power structure"
```

#### Network Access Conflicts
```yaml
# WARNING: Agent requests network access denied by collection
# collection.yaml
shared_context:
  constraints:
    requires_network: false  # Collection policy: no network

# agent.yaml
constraints:
  requires_network: true     # ⚠️ Agent wants network access
  
# Validation Warning:
# "Agent 'api-validator' requests network access denied by collection policy"
# "Either set agent requires_network: false or use opt_out_collection_constraints: true"
# "Final resolution: requires_network: false (collection policy wins)"
```

#### Network Access Opt-out
```yaml
# AUDIT: Agent opts out of collection network policy
# agent.yaml
constraints:
  requires_network: true
  opt_out_collection_constraints: true
  opt_out_justification: "Needs external API access for schema validation"
  
# Validation Result:
# "Agent 'api-validator' opted out of collection network policy"
# "Justification: Needs external API access for schema validation"
# "Final resolution: requires_network: true (agent override with audit trail)"
```

#### Delegation Security Violations
```yaml
# ERROR: Disabling constraint intersection without explicit intent
# agent.yaml
subagents:
  allowed_specialists: ["database-specialist"]
  delegation_security:
    constraint_intersection: false  # ❌ Disabled without required fields
    allowed_elevations: []

# Validation Error:
# "constraint_intersection: false requires either:"
# "  - allow_full_delegation: true + justification"
# "  - non-empty allowed_elevations array"
# "Cannot disable security without explicit intent"
```

```yaml
# ERROR: Full delegation without justification
# agent.yaml
subagents:
  delegation_security:
    constraint_intersection: false
    allow_full_delegation: true  # ❌ Missing required justification
        
# Validation Error:
# "allow_full_delegation: true requires justification field"
# "Explain why subagent needs full permissions"
```

```yaml
# ERROR: Elevation without justification
# agent.yaml
subagents:
  delegation_security:
    constraint_intersection: false
    allowed_elevations:
      - tool_pattern: "database.*"  # ❌ Missing justification
        
# Validation Error:
# "Elevation 'database.*' missing required justification"
# "Add justification field explaining why elevation is needed"
```

```yaml
# ERROR: Overly broad elevation
# agent.yaml  
subagents:
  delegation_security:
    constraint_intersection: false
    allowed_elevations:
      - tool_pattern: "*"  # ❌ Too broad
        justification: "Need full access"
        
# Validation Error:
# "Elevation pattern '*' is too broad and dangerous"
# "Use specific tool patterns like 'database.*' or 'filesystem.write'"
```

```yaml
# VALID: Explicit full delegation
# agent.yaml
subagents:
  delegation_security:
    constraint_intersection: false
    allow_full_delegation: true
    justification: "Coordinator agent needs to delegate complex workflows with full subagent capabilities"
    audit_trail: true  # Cannot be disabled when constraint_intersection: false
```
```yaml
# ERROR: Tool name collision without resolution
# powers/database-patterns/tools.yaml has tool "query"
# powers/api-standards/tools.yaml has tool "query"

# agent.yaml (PROBLEMATIC)
powers:
  - "./powers/database-patterns"
  - "./powers/api-standards"  # ❌ No collision resolution

# Validation Error:
# "Tool name collision: 'query' defined in both database-patterns and api-standards"
# "Add exclude_tools or tool_aliases to resolve collision"

# agent.yaml (RESOLVED)
powers:
  - "./powers/database-patterns"
  - path: "./powers/api-standards"
    tool_aliases:
      query: "api_query"  # ✅ Explicit resolution
```

#### Resource Collision Errors  
```yaml
# ERROR: MCP server name collision
# Validation Error:
# "MCP server collision: 'validator' in database-patterns and api-standards"
# "Use server_aliases to resolve: validator -> api_validator"

# Resolution:
powers:
  - "./powers/database-patterns" 
  - path: "./powers/api-standards"
    server_aliases:
      validator: "api_validator"  # ✅ Renamed to avoid collision
```

### Complete Kiro Native JSON Example

**Real Kiro Agent JSON Output:**
```json
{
  "name": "backend-specialist",
  "description": "Database and API expert with company standards",
  "prompt": "You are a backend specialist expert in databases and APIs.\n\nYou follow these company standards:\n- Use PostgreSQL for relational data\n- Follow REST API conventions\n- Implement proper error handling\n\n# Database Patterns\nAlways validate schema changes:\n- Check for breaking changes\n- Ensure proper indexing\n- Review migration scripts\n\n# API Standards\nAPI design principles:\n- Use semantic HTTP status codes\n- Implement consistent error responses\n- Follow OpenAPI 3.0 specification",
  "mcpServers": {
    "database-tools": {
      "command": "uvx",
      "args": ["database-mcp-server@latest"],
      "env": {
        "DB_HOST": "${DATABASE_HOST}",
        "DB_PORT": "5432"
      },
      "autoApprove": [
        "query_schema",
        "validate_migration",
        "check_indexes"
      ],
      "disabledTools": [
        "drop_table",
        "truncate_data"
      ]
    },
    "api-validator": {
      "command": "uvx", 
      "args": ["openapi-validator@latest"],
      "autoApprove": [
        "validate_spec",
        "check_breaking_changes"
      ]
    }
  },
  "tools": [
    "filesystem.read",
    "filesystem.write",
    "database.query",
    "database.migrate", 
    "api.validate",
    "api.generate_docs"
  ],
  "allowedTools": [
    "filesystem.read",
    "filesystem.write",
    "database.query",
    "database.migrate",
    "api.validate"
  ],
  "disabledTools": [
    "network.external.*",
    "system.admin.*",
    "database.drop_table"
  ],
  "toolAliases": {
    "db_query": "database.query",
    "validate_api": "api.validate"
  },
  "_kiroforge": {
    "version": "1.0.0",
    "source_agent": "./agents/backend-specialist",
    "source_powers": [
      "./powers/database-patterns",
      "./powers/api-standards", 
      "./shared/powers/company-standards"
    ],
    "collision_resolution": {
      "tool_collisions": [],
      "server_collisions": [],
      "steering_collisions": [
        {
          "section": "Error Handling",
          "powers": ["database-patterns", "api-standards"],
          "resolution": "last_wins", 
          "final_source": "api-standards",
          "warning": "Content from database-patterns was overwritten"
        }
      ]
    },
    "subagents": {
      "allowed_specialists": ["database-specialist", "api-reviewer"],
      "max_concurrent": 3,
      "delegation_rules": [
        "Delegate complex queries to database-specialist",
        "Route API reviews to api-reviewer"
      ],
      "delegation_security": {
        "constraint_intersection": true,
        "audit_trail": true,
        "require_justification": false,
        "allowed_elevations": [
          {
            "tool_pattern": "database.write",
            "justification": "Schema migrations require write access",
            "audit_level": "high"
          }
        ]
      }
    },
    "constraint_resolution": {
      "collection_constraints_applied": true,
      "opt_out": false,
      "final_allowed_tools": ["filesystem.read", "filesystem.write", "database.query"],
      "final_denied_tools": ["network.external.*", "system.admin.*"],
      "network_access": {
        "collection_policy": false,
        "agent_requested": false, 
        "final_resolution": false,
        "resolution_reason": "Agent complies with collection policy"
      }
    },
    "export_timestamp": "2025-01-10T20:30:00Z",
    "kiroforge_version": "0.2.0"
  }
}
```

This comprehensive specification provides implementers with exact schemas, validation rules, error cases, and output formats needed to build the agent module functionality.
