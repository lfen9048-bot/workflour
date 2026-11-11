---
name: search-first
description: "Find existing tools, libraries, plugins, skills, templates, and GitHub implementations before building a new feature or reusable workflow. Use when the user describes a new capability, asks for an existing solution, or plans to create custom code or a skill."
metadata:
  origin: ECC
  source: https://github.com/affaan-m/ECC/tree/main/skills/search-first
---

# /search-first — Research Before You Code

Systematizes the "search for existing solutions before implementing" workflow.

## Codex runtime

Use the tools and skill catalog exposed in the current Codex session. Prefer a
connected GitHub tool when available; otherwise use public GitHub/web search.
Read the actual README, SKILL.md, documentation, or relevant implementation of
promising candidates before recommending one. A search snippet is not sufficient
evidence of compatibility. Report unavailable search channels honestly.

Respect explicit user instructions and the task's existing authorization.
Research does not itself authorize unrelated installations or configuration
changes. For an implementation request, continue the authorized work after
choosing an approach; avoid an unnecessary approval pause after research.
Reuse recent research for follow-ups to the same requirement, and refresh it
when the requirement, compatibility constraints, or external facts change.

## Trigger

Use this skill when:
- Starting a new feature that likely has existing solutions
- Adding a dependency or integration
- The user asks "add X functionality" and you're about to write code
- Before creating a new utility, helper, or abstraction

## Workflow

```
┌─────────────────────────────────────────────┐
│  0. TOOL AVAILABILITY PREFLIGHT             │
│     Check search channels before relying on │
│     them; report skipped channels honestly   │
├─────────────────────────────────────────────┤
│  1. NEED ANALYSIS                           │
│     Define what functionality is needed      │
│     Identify language/framework constraints  │
├─────────────────────────────────────────────┤
│  2. SEARCH RELEVANT SOURCES                 │
│     ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│     │  npm /   │ │  MCP /   │ │  GitHub / │  │
│     │  PyPI    │ │  Skills  │ │  Web      │  │
│     └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────┤
│  3. EVALUATE                                │
│     Score candidates (functionality, maint, │
│     community, docs, license, deps)         │
├─────────────────────────────────────────────┤
│  4. DECIDE                                  │
│     ┌─────────┐  ┌──────────┐  ┌─────────┐  │
│     │  Adopt  │  │  Extend  │  │  Build   │  │
│     │ as-is   │  │  /Wrap   │  │  Custom  │  │
│     └─────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────┤
│  5. IMPLEMENT                               │
│     Install package / Configure MCP /       │
│     Write minimal custom code               │
└─────────────────────────────────────────────┘
```

## Decision Matrix

| Signal | Action |
|--------|--------|
| Exact match, well-maintained, MIT/Apache | **Adopt** — install and use directly |
| Partial match, good foundation | **Extend** — install + write thin wrapper |
| Multiple weak matches | **Compose** — combine 2-3 small packages |
| Nothing suitable found | **Build** — write custom, but informed by research |

## How to Use

### Step 0: Tool Availability Preflight

This is agent guidance, not an executable setup script. Check only the channels
that are relevant to the task and project in front of you.

| Channel | Check | If missing |
|---------|-------|------------|
| Repository search | `rg --files` and targeted `rg` queries | State that only visible files were inspected |
| Package registry | `npm --version`, `python -m pip --version`, or project package manager | Use web/docs search and avoid claiming registry coverage |
| GitHub CLI | `gh auth status` | Use public web or local git history only |
| MCP/docs tools | Available tool list or local MCP config | Fall back to official docs/web search |
| Skills directory | Current skill catalog; configured user and project skill roots | Say no local skill catalog was available |

### Quick Mode (inline)

Before writing a utility or adding functionality, mentally run through:

0. Does this already exist in the repo? → `rg` through relevant modules/tests first
1. Is this a common problem? → Search npm/PyPI
2. Is there a connected tool or MCP for this? → Inspect the current tool catalog
3. Is there a skill for this? → Inspect the current skill catalog and configured skill roots
4. Is there a GitHub implementation/template? → Run GitHub code search for maintained OSS before writing net-new code

### Full Mode

For non-trivial functionality, run a bounded comparison with the current tools.
Use this research brief directly; delegate only when the current task or
applicable instructions authorize delegation and an independent search helps:

```
  Research existing tools for: [DESCRIPTION]
  Language/framework: [LANG]
  Constraints: [ANY]

  Search: relevant package registries, connected tools, skills, GitHub, official docs
  Return: Structured comparison with recommendation
```

Use only search and delegation tools actually available in the current session.

## Search Shortcuts by Category

### Development Tooling
- Linting → `eslint`, `ruff`, `textlint`, `markdownlint`
- Formatting → `prettier`, `black`, `gofmt`
- Testing → `jest`, `pytest`, `go test`
- Pre-commit → `husky`, `lint-staged`, `pre-commit`

### AI/LLM Integration
- Provider SDKs → official documentation or the configured documentation tool
- Prompt management → Check MCP servers
- Document processing → `unstructured`, `pdfplumber`, `mammoth`

### Data & APIs
- HTTP clients → `httpx` (Python), `ky`/`undici` (Node)
- Validation → `zod` (TS), `pydantic` (Python)
- Database → Check for MCP servers first

### Content & Publishing
- Markdown processing → `remark`, `unified`, `markdown-it`
- Image optimization → `sharp`, `imagemin`

## Examples

These upstream examples illustrate decisions, not verified current package
recommendations. Check current documentation and compatibility for the actual task.

### Example 1: "Add dead link checking"
```
Need: Check markdown files for broken links
Search: npm "markdown dead link checker"
Found: textlint-rule-no-dead-link (score: 9/10)
Action: ADOPT — npm install textlint-rule-no-dead-link
Result: Zero custom code, battle-tested solution
```

### Example 2: "Add HTTP client wrapper"
```
Need: Resilient HTTP client with retries and timeout handling
Search: npm "http client retry", PyPI "httpx retry"
Found: got (Node) with retry plugin, httpx (Python) with built-in retry
Action: ADOPT — use got/httpx directly with retry config
Result: Zero custom code, production-proven libraries
```

### Example 3: "Add config file linter"
```
Need: Validate project config files against a schema
Search: npm "config linter schema", "json schema validator cli"
Found: ajv-cli (score: 8/10)
Action: ADOPT + EXTEND — install ajv-cli, write project-specific schema
Result: 1 package + 1 schema file, no custom validation logic
```

## Anti-Patterns

- **Jumping to code**: Writing a utility without checking if one exists
- **Ignoring MCP**: Not checking if an MCP server already provides the capability
- **Silent skipping**: Reporting "nothing found" when a search channel was unavailable
- **Over-customizing**: Wrapping a library so heavily it loses its benefits
- **Dependency bloat**: Installing a massive package for one small feature

## Source

Adapted for Codex from [ECC search-first](https://github.com/affaan-m/ECC/tree/main/skills/search-first).
Reviewed upstream Git blob: `3d2669e71ba54afba95defb05080253058190600`.
Local changes use Codex tool/skill discovery, allow inline research, broaden
discovery to reusable workflows, and preserve the user's task authorization.
Upstream copyright and MIT terms are in [LICENSE](LICENSE).
