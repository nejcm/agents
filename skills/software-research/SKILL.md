---
name: software-research
description: Use when the user wants to pick or compare libraries, frameworks, databases, or tools, evaluate a system architecture or design, or check how a technology really behaves ("what should we use for X", "is Y production-ready"). Returns a sourced, version-pinned report. For the current repo use explore-codebase; for competitors or markets use competitive-intelligence or market-analysis.
disable-model-invocation: true
---

# Software Research

Turn a software question into a report an engineer can act on: a
recommendation, the evidence behind it, what it costs, and what would change
the answer. Prefer a few primary sources read closely over many secondary
sources skimmed. Model memory about libraries and APIs goes stale fast; treat
it as a lead to verify, never as a finding.

## Workflow

1. **Frame the decision.** Write down what is being decided, the constraints
   that bind it (language, runtime, platform, license, scale, latency,
   compliance, team size, existing stack, budget, deadline), what a good
   outcome looks like, and how reversible the choice is. If the user supplied a
   codebase, read enough of it to know the real constraints; a library that
   fails on the project's Node version or bundler is not a candidate. Label
   assumptions you had to make.
2. **Enumerate candidates.** List the serious options, including "do nothing",
   "write it ourselves", and the incumbent. Say why each made or missed the
   list. Stop at the handful that can plausibly win; ranking twelve options
   shallowly helps nobody.
3. **Plan sources before reading.** Pick the sources that can settle each
   question (see source hierarchy). Pin the version you are evaluating.
4. **Gather evidence** and record for each claim: source, version, date,
   and whether it is a documented promise, observed behavior, a benchmark, or
   someone's opinion.
5. **Verify by running when it is cheap.** A ten-minute spike — install,
   minimal example, one measurement under the user's constraint — outranks
   any blog post. Record the exact command and environment. Skip when the
   setup cost exceeds the value of certainty.
6. **Weigh and synthesize.** Score only dimensions that matter to the
   decision. Separate facts, measurements, inference, and preference. Stop
   when another source would not change the recommendation.
7. **Report** in the structure below, then say what would flip the answer.

## Source hierarchy

Higher rows settle disputes with lower rows. A lower-row claim that
contradicts a higher one is a lead to investigate, not evidence.

1. The code and its tests, at the pinned version. Read the implementation of
   the feature you are relying on; tests show what is actually guaranteed.
2. Official documentation, changelogs, release notes, migration guides,
   and deprecation notices. Fetch current docs with the documentation tool
   available in the session (such as Context7) or the web; do not quote an
   API from memory.
3. Issue tracker, pull requests, discussions, and security advisories. Open
   bugs with many reactions, stale maintainer responses, and "won't fix"
   decisions are first-hand evidence of behavior and priorities.
4. Specs, RFCs, ADRs, and design documents from the project or standards body.
5. Reproducible benchmarks with published methodology and code.
6. Engineering blog posts from teams who ran the thing in production, with the
   scale and date stated.
7. Comparison articles, forum answers, tutorials, and model recollection.
   Use only to discover leads and vocabulary.

Use `gh` to search and read repositories, issues, and release data directly
instead of relying on third-party summaries.

## What to evaluate

Pick from these; drop what the decision does not touch.

**Libraries, frameworks, tools**

- Fit: does it solve the actual problem without bending the design around it?
- API stability: semver discipline, breaking-change history, deprecation policy.
- Maintenance: release cadence, time-to-response on issues, number of active
  maintainers, funding, whether the last release is a bug-fix or a silence.
  Stars and downloads are popularity, not health.
- License and its compatibility with the user's distribution model.
- Security: advisories, dependency count and depth, supply-chain practices.
- Weight: install size, bundle or binary size, cold-start and memory cost.
- Platform and version support matrix against the user's targets.
- Performance under the user's workload shape, with evidence or a spike.
- Documentation and error quality: can an engineer self-serve?
- Exit cost: how much code touches it, and what migrating away would take.

**Architecture and system design**

- Requirements as numbers: throughput, latency percentiles, data volume,
  consistency and durability needs, availability target, growth horizon.
- Candidate designs with their key tradeoffs, named explicitly.
- Failure modes: what breaks first, blast radius, recovery path, how it is
  observed.
- Operational cost: services to run, on-call burden, infrastructure spend,
  skills the team must hold.
- Reversibility: what is cheap to change later and what is load-bearing.
- Prior art at comparable scale, with the differences from the user's case.
- Simplest design that meets the requirements; justify every added part.

## Evidence rules

- Every claim carries a version and a date. "Supports streaming" without a
  version is not a finding.
- Put the citation next to the claim it supports, with a link.
- Distinguish what the docs promise from what you observed; the two diverge.
- Report benchmarks only with workload, hardware, version, and whether you
  reproduced them. Vendor benchmarks are marketing until reproduced.
- Flag stale sources: anything older than the current major version, or
  older than a year for fast-moving ecosystems.
- Check for deprecations and successor projects before recommending.
- Never invent sources, version numbers, benchmark figures, or maintainer
  statements. If browsing or tool access is missing, say what you could not
  verify and recommend conditionally.
- When the user's existing stack or codebase was available, name the
  constraints it imposed and where you looked.

## Report structure

Use this shape unless the request calls for something smaller. For a quick
question, the recommendation and evidence sections alone are enough.

1. **Recommendation** — one paragraph: what to choose, for what, with the
   confidence level and the single biggest caveat.
2. **Decision and constraints** — what was decided, binding constraints,
   assumptions made.
3. **Candidates considered** — included and excluded, with reasons.
4. **Findings** — per candidate or per design, evidence inline, versions pinned.
5. **Comparison** — a table on the dimensions that mattered, nothing else.
6. **Risks and unknowns** — what could go wrong, what remains unverified,
   what would change the recommendation.
7. **Next step** — the smallest action that reduces the largest uncertainty
   (usually a spike with an exact command).
8. **Sources** — links with version and date accessed.

Write the report to a file when the user asks for one or when it is too long
for chat; otherwise answer in chat.

## Cross-model research

Run this protocol when the decision is consequential or hard to reverse, when
sources disagree, when a single-model report came back with low confidence, or
when the user asks for it. It costs several delegated sessions; say so before
starting and skip it for routine lookups.

Model, effort, and reviewer selection come from `agent-orchestration`:
research and review are Planner and Reviewer/Judge work at `high`. Invocation
mechanics come from `model-dispatch`: host-native subagents for the host's own
family, a thin wrapper around another family's CLI otherwise. Read both before
the first dispatch. Every delegate gets a fresh session; a session never
reviews its own output.

Phases are sequential; the two sides of each phase run in parallel.

1. **Independent research.** Dispatch the same research packet to one
   Claude-family researcher (Fable, then Opus) and one GPT-family researcher
   (Sol). Each follows this skill's workflow and report structure in a
   read-only workspace with the same tool access. Researchers must not see
   each other's output, so their agreement means something.
2. **Cross review.** Swap the reports. A fresh GPT-family reviewer reviews the
   Claude report; a fresh Claude-family reviewer reviews the GPT report, per
   the review routing in `agent-orchestration`. The reviewer checks each
   material claim against the cited source, hunts for missing candidates,
   stale versions, misread docs, and unsupported inference, and returns
   findings with evidence and a confirmed / rejected / unverifiable
   disposition for each.
3. **Synthesis.** The coordinator merges the two reports and both reviews into
   one draft. Mark each finding as confirmed by both researchers, found by one
   and confirmed in review, or disputed. Resolve disputes by reading the
   primary source yourself or running the spike; do not settle them by vote
   or by trusting the stronger model.
4. **Adversarial review.** Send the draft to a fresh reviewer from the family
   that did not write the synthesis, using the `adversarial-review` skill.
   When stakes warrant it, add a second adversary from the other family so
   both families have attacked the recommendation. Adversaries pressure-test
   the recommendation itself: load-bearing assumptions, unhappy paths, exit
   cost, and whether the question was framed correctly.
5. **Final report.** Fold confirmed adversarial findings into the report. Add
   a short provenance section: which models researched, reviewed, and
   attacked; what each phase changed; disagreements that remain open and
   what would settle them.

Delegation packet for each phase, built from the template in
`agent-orchestration`:

- Objective, decision, and constraints exactly as framed in step 1 of the
  workflow, so both researchers answer the same question.
- Candidate list if the user fixed it; otherwise instruct the researcher to
  enumerate.
- The evidence rules and report structure from this skill, quoted. Delegates
  do not inherit your instruction files.
- Tool access: which documentation, web, and repository tools exist in the
  delegate's environment, and the workspace path if a codebase is in scope.
- For reviewers: the report under review, the packet it was built from, and
  the instruction to verify claims at the source rather than from memory.
- Return format: the report structure above, plus a list of claims with the
  evidence type for each, so review can target them.

If the other family is unavailable, say so, fall back to a fresh same-family
delegate, and label the result as reduced independence rather than calling it
cross-model. Track the actual model that produced each artifact, including
after fallbacks.
