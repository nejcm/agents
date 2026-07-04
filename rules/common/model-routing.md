# Model Routing

Defaults apply every turn. Override only with an explicit reason. Pick the best model capable of the task except if specified otherwise. 
Three tiers:

| Tier      | Use for                                                                                               | Model (effort)                                |
| --------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **Think** | Planning, architecture, code review, debugging, adversarial review, security audit, complex reasoning | fable (high), opus-4-8 (high), gpt-5.5 (high) |
| **Build** | Implementing, editing, refactoring, code generation, frontend design, general coding                  | opus-4-8 (medium), gpt-5.5 (medium)           |
| **Ship**  | Commits, linting, status checks, docs, exploration, search, simple one-shot tasks                     | haiku (medium), gpt-5.5 (low)                 |

**Per-skill overrides**: Skills with `model:` frontmatter automatically switch tier on load:

- **Think**: `code-review`, `requesting-code-review`, `adversarial-review`, `grill-*`, `codebase-design`, `improve-codebase-architecture`, `domain-modeling`, `security`
- **Build**: `implement-plan`, `review-fix-commit`, `frontend-design`
- **Ship**: `git-workflow`, `ci-status`, `code-quality`, `doc-generator`, `explore-codebase`, `performance-profiler`
