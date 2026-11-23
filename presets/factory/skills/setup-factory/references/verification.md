# Phase 4: Verification

Generate the project-local verify skill with pstack `create-verification-skill`, then make it
discoverable by every harness. Requires a working `Run` section from phase 3.

## Steps

1. **Existing skill**: if `.cursor/skills/verify-*/` already exists, do not regenerate it. With
   several, pick the one for the primary surface or ask. Record it, keep its recorded proof
   evidence or mark proof unavailable, check the links below, and offer pstack
   `maintain-verification-skill` to refresh it.
2. **Generate**: load `create-verification-skill` by path (see SKILL.md, loading other skills) and
   follow it. Hand it the profile's `Run` section as the answer to its launch and isolation
   questions, so it does not rediscover them, and this skill's write rule: scaffolding and proof
   evidence go under `.factory/` or the generated skill dir. Keep its default output location,
   `.cursor/skills/verify-<app>/`, so `maintain-verification-skill` works unmodified. Its own
   step 4 (prove the skill end to end) is part of this phase, not optional.
3. **Symlink** the canonical dir into the other harnesses' project skill dirs, relative per skill:

   ```bash
   mkdir -p .agents/skills .claude/skills
   ln -s ../../.cursor/skills/verify-<app> .agents/skills/verify-<app>
   ln -s ../../.cursor/skills/verify-<app> .claude/skills/verify-<app>
   ```

   Check each destination first: keep a link to the same dir, and keep a copy the profile records
   as a fallback. Anything else there (another link, a directory, a file) is a conflict: stop and
   ask before `ln`, which would otherwise nest a link inside a directory.
4. **Discovery**: symlink discovery is not verified for every harness. Tell the user to open a
   fresh session in each harness they use and confirm `verify-<app>` is listed. Where it is not,
   replace that link with a copy and note in the profile that the copy must be refreshed after
   each `maintain-verification-skill` run.
5. Skip `create-verification-skill`'s step 5 (offering a maintenance cadence); `automate-factory`
   handles scheduling.

## Output

The profile's `Verification` section: skill name and canonical path, links and copies per harness,
discovery status per harness (confirmed, unconfirmed, copy), the feature map's features, and the
proof run's evidence location.
