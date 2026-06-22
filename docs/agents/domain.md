# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, when it exists.
- **`docs/adr/`** for architectural decisions that touch the area being worked on, when they exist.

If any of these files don't exist, proceed silently. Don't flag their absence or suggest creating them upfront. Producer workflows can create them lazily when terms or decisions actually get resolved.

## File structure

This is a single-context repo:

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

When output names a domain concept in an issue title, refactor proposal, hypothesis, test name, or PRD, use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept needed isn't in the glossary yet, that is a signal: either the output is inventing language the project doesn't use, or there is a real glossary gap to resolve.

## Flag ADR conflicts

If output contradicts an existing ADR, surface it explicitly rather than silently overriding.
