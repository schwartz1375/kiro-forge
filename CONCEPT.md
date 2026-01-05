# KiroForge: A Powers Framework for Testing and Governing Agent Capabilities

## Executive Summary

Agent systems are rapidly converging on the idea of **modular, dynamically loaded capabilities**—commonly referred to as *skills*, *powers*, or *tools*. While ecosystems like **Anthropic** have formalized this pattern through *Anthropic Skills*, **Kiro CLI** currently lacks a standardized, extensible, and community-scale framework for building, validating, discovering, and evolving *powers*.

This document outlines:

1. The **market and ecosystem gap**
2. A **comparison of Anthropic Skills vs Kiro Powers**
3. A proposed **Kiro-native Powers Framework**, inspired by the core ideas behind SkillForge
4. Why this represents a compelling open-source and startup-level opportunity

---

## 1. The Ecosystem Gap

### The Problem

Today, Kiro Powers are:

* Contextually loaded
* Powerful for steering behavior
* Tightly coupled to internal configurations

However, they lack:

* A **formal authoring standard**
* **Lifecycle tooling** (testing, validation, evolution)
* **Discovery, reuse, and composition**
* **Community-scale extensibility**

This creates friction for:

* Teams trying to reuse proven agent behaviors
* Organizations wanting governance over agent steering
* Developers building advanced agent workflows across tools

### The Gap

> There is no **opinionated, Kiro-native framework** for building, validating, and evolving agent steering modules as first-class artifacts.

This is the same gap Anthropic addressed with *Skills*—but Kiro’s developer-centric, tool-oriented ecosystem requires a different approach.

### Evidence Signals (Public)

The ecosystem is already standardizing around modular capability packages, which validates the need for a structured framework:

* **Anthropic Skills are formalized and widely cataloged**: the community maintains a large, curated list of Claude skills (dozens of categories and many examples), indicating demand for discovery and reuse. See the "Awesome Claude Skills" catalog: https://github.com/ComposioHQ/awesome-claude-skills
* **Anthropic ships structured development tooling**: the Claude Code "plugin-dev" toolkit includes workflows, validation utilities, and explicit "Skill Development" guidance, signaling real investment in skill lifecycle management. https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev
* **Kiro explicitly bundles capabilities into Powers**: Kiro powers bundle MCP tools, steering files, and hooks into an installable unit and emphasize sharing via GitHub, but a deeper lifecycle framework (testing, validation, governance) is still missing. https://kiro.dev/powers/
* **Kiro Steering is a persistent, file-based control surface**: steering uses markdown files under `.kiro/steering/` (workspace or global) and is treated as durable project knowledge. This supports the idea of a formal framework around authored steering. https://kiro.dev/docs/cli/steering/

---

## 2. Anthropic Skills vs Kiro Powers

| Dimension          | Anthropic Skills                | Kiro Powers                          |
| ------------------ | ------------------------------- | ------------------------------------ |
| Primary Goal       | Extend Claude’s task competence | Steer Kiro agent behavior            |
| Core Abstraction   | Skill (procedural knowledge)    | Power (workflow & behavior steering) |
| Packaging          | SKILL.md + optional code/assets | Config + tools + best practices      |
| Activation         | Contextual, dynamic             | Contextual, dynamic                  |
| Target User        | Prompt engineers, AI builders   | Developers, platform engineers       |
| Ecosystem Maturity | Growing shared catalog          | Early-stage, internal-first          |

### Key Insight

Anthropic Skills optimize for **knowledge reuse**.
Kiro Powers optimize for **workflow correctness and tool orchestration**.

This means a Kiro framework must go beyond documentation—it must encode **behavioral contracts**, **tool access**, and **execution constraints**.

---

## 2.1 Terminology (Make the Differences Explicit)

* **Kiro Steering**: Markdown files under `.kiro/steering/` (workspace or global) that provide persistent project context and standards to Kiro. They are always loaded in Kiro sessions and govern how the agent behaves in that workspace. https://kiro.dev/docs/cli/steering/
* **Kiro Powers**: Installable bundles that package MCP tools, steering files, and hooks into a single unit that can be shared and activated on-demand. https://kiro.dev/powers/
* **Anthropic Skills**: Skill packages (typically `SKILL.md` plus assets/scripts) used by Claude/Claude Code to add task-specific competence and workflows. https://github.com/anthropics/skills

These are related but not interchangeable. KiroForge should treat **Steering** as the persistent policy layer and **Powers** as portable capability bundles that can include steering plus tools and hooks.

KiroForge should also support **steering-only authoring**, since many teams want persistent guidance without bundling tools or hooks.

---

## 3. Why Build a Kiro Powers Framework (Inspired by [SkillForge](https://github.com/tripleyak/SkillForge))

The following proposal adapts the **five core principles demonstrated by SkillForge** into a Kiro-native system.

### Why SkillForge Is Not Enough (Non-Overlap)

SkillForge provides a strong pattern for **skills-as-knowledge**, but Kiro’s needs are structurally different:

* **Different unit of value**: SkillForge focuses on skills that add task competence; Kiro Powers bundle **tools + steering + hooks** into an installable capability that changes tool access and execution constraints. That bundle needs its own schema, validation, and safety model.
* **Steering is a first-class control surface**: Kiro has persistent steering files (`.kiro/steering/`) that are always loaded and behave like project policy. SkillForge does not model this persistent policy layer or conflicts between workspace/global steering.
* **Execution constraints are mandatory**: Kiro Powers must define allowed tools, hooks, and guardrails for CLI/IDE execution. Skills in SkillForge are largely descriptive and do not encode tool-level permissions or enforcement.
* **Packaging and distribution differ**: Kiro Powers are shared and installed via GitHub and include MCP servers and hooks; SkillForge assumes skills are primarily documentation plus assets, not executable bundles.
* **Lifecycle testing must be behavioral**: Kiro needs regression tests that validate tool usage and agent behavior under constraints. SkillForge does not ship a behavior test harness for executable powers.

Because of these differences, KiroForge should be **inspired by** SkillForge’s principles but **cannot be a direct adaptation** without rethinking schema, validation, and governance.

---

## 4. Proposed Solution: Kiro PowerForge (Working Name)

### 4.0 Scope: A Tight MVP Before a Full Platform

To avoid platform sprawl, start with a minimal, high-leverage scope:

1. **A `POWER.md` schema** that standardizes intent, triggers, constraints, and versioning
2. **A validator + linting CLI** that checks schema correctness and power packaging
3. **A behavioral test harness** with a small test DSL (pass/fail assertions against outcomes)
4. **2-3 exemplar Powers** that demonstrate authoring, validation, and testing

Routing, registries, and observability should follow only after the MVP proves adoption.

### 4.1 Principle 1 — Systemized Power Creation

**Problem today:**
Powers are handcrafted, undocumented, and hard to review.

**Proposed solution:**
Introduce a standardized `POWER.md` schema:

```
/power-name
  ├── POWER.md        # Intent, constraints, triggers
  ├── steering.yaml  # Behavioral rules & guardrails
  ├── tools.yaml     # MCP / CLI / API access
  └── tests/         # Behavioral validation
```

This treats agent steering as **infrastructure**, not prompts.

KiroForge should offer both a **template scaffold** and an **interactive authoring wizard** to guide users through metadata, triggers, constraints, and resources.

The interactive steering flow should map to Kiro’s recommended steering strategies and generate the same file sets (foundational and common strategies).

---

### 4.2 Principle 2 — Intelligent Power Routing

**Problem today:**
Context matching is opaque and static.

**Proposed solution:**
Add a *Power Router* that:

* Classifies tasks
* Selects existing powers
* Composes multiple powers when needed
* Falls back to generic behavior only when required

This mirrors SkillForge’s universal routing concept but tuned for **CLI and dev workflows**.

---

### 4.3 Principle 3 — Quality, Validation, and Drift Control

**Problem today:**
No guardrails prevent behavioral drift or regressions.

**Proposed solution:**

* Power test harnesses
* Regression prompts
* Execution constraints
* Safety and compliance checks

Think **unit tests for agent behavior**.

---

### 4.4 Principle 4 — Self-Verification & Observability

**Problem today:**
When an agent fails, root cause analysis is unclear.

**Proposed solution:**

* Powers declare success criteria
* Post-execution self-checks
* Structured traces for why a power activated

This enables **debuggable agents**, not opaque ones.

---

### 4.5 Principle 5 — Standards, Templates, and Community Scale

**Problem today:**
No shared ecosystem or reuse.

**Proposed solution:**

* Official Power templates
* Power registries (internal + public)
* Versioning and compatibility metadata

This unlocks:

* Team reuse
* Enterprise governance
* Open-source collaboration

---

## 5. Why This Is a Strategic Gap

### Open-Source Opportunity

* Establish the de-facto standard for Kiro Powers
* Encourage community-built power libraries
* Become foundational infrastructure

### Startup Opportunity

* Hosted power registry
* Enterprise validation & compliance tooling
* Cross-agent compatibility layers (Claude, Kiro, MCP)

### Strategic Insight

> Prompting is becoming a solved problem.
> **Agent steering, lifecycle management, and governance are not.**

Kiro is uniquely positioned to lead here due to its CLI-first, developer-native design.

---

## 6. Closing Thought

Anthropic Skills proved that **modular agent capability systems work**.
Kiro Powers prove that **agent steering is essential for real workflows**.

What’s missing is the **framework layer that turns powers into durable, testable, evolvable infrastructure**.

That is the gap—and the opportunity.
