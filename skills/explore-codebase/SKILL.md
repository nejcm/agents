---
name: explore-codebase
description: Map an unfamiliar codebase's stack, entry points, data flow, architecture, auth, tests, and deployment. Use when orienting in a repository or tracing behavior.
category: workflow
---

## When exploring unfamiliar code

1. Start with package.json/composer.json to understand dependencies
2. Read AGENTS.md or README for project overview
3. Identify entry points (main, index, server files)
4. Trace request flow from entry to database
5. Note patterns: DI, repository, service layers
6. Document in a summary for future reference

## Questions to answer

- What framework(s)?
- What database(s)?
- How is auth handled?
- How are tests structured?
- What's the deployment target?
