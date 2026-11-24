#!/usr/bin/env bash
# Factory automation; step rules in automate-factory references/safety.md.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ ! -e .factory/pause ] || { echo paused; exit 0; }
entry=$(basename "$0" .sh)
day=$(date +%F)
out=.factory/reports/$entry
mkdir -p "$out" .factory/tmp
[ -e .factory/tmp/.gitignore ] || echo '*' > .factory/tmp/.gitignore
view=$(mktemp -d "$PWD/.factory/tmp/$entry.XXXXXX")
# Against mistakes only: the edit step runs as this user and can change any Git config.
n=${GIT_CONFIG_COUNT:-0}
[[ $n =~ ^[0-9]+$ ]] || { echo "GIT_CONFIG_COUNT is not a number" >&2; exit 1; }
n=$((10#$n))
export GIT_CONFIG_COUNT=$((n + 2)) "GIT_CONFIG_KEY_$n=core.hooksPath" "GIT_CONFIG_VALUE_$n=/dev/null" \
  "GIT_CONFIG_KEY_$((n + 1))=core.fsmonitor" "GIT_CONFIG_VALUE_$((n + 1))=false"
creds_re='sk-ant-[A-Za-z0-9_-]{16}'
calls=$view/calls.jsonl gates_log=$view/gates.log began=$(date -u +%FT%TZ) run_outcome="" run_reason="" gate_block=""
record_py=$(cat <<'PY'
import json, os, re, sys
mode, *a = sys.argv[1:]
def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""
def lines(p):
    return read(p).splitlines()
def disclosed(t):
    t = (t or "").split()
    if len(t) != 4:
        return dict(test_changes=None, dependency_change=None, scope=None, weighted_lines=None)
    return dict(test_changes=int(t[0]), dependency_change=t[1] == "1", scope=t[2], weighted_lines=int(t[3]))
def reviews(t):
    return [dict(model=m, family="same family", verdict="approve" if v == "approve" else "changes", valid=v != "invalid")
            for m, _, v in (x.rpartition("=") for x in (t or "").split())]
if mode == "json":
    raw = read(a[0])
    try:
        d = json.loads(raw)
    except ValueError:
        d = None
    if not isinstance(d, dict):
        print(raw, end="")
        d = {}
    elif isinstance(d.get("result"), str):
        r = d["result"]
        print(r, end="" if r.endswith("\n") else "\n")
    u = d.get("usage") if isinstance(d.get("usage"), dict) else {}
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    with open(a[1], "a") as f:
        f.write(json.dumps(dict({k: u.get(k) for k in keys}, turns=d.get("num_turns"), cost_usd=d.get("total_cost_usd"),
                            max_turns=d.get("subtype") == "error_max_turns")) + "\n")
    sys.exit()
creds, calls, gates, outcomes, *kv = a
rec = dict(x.split("=", 1) for x in kv)
rec = {k: v or None for k, v in rec.items()}
rec["exit_code"], rec["dry_run"] = int(rec["exit_code"]), rec["dry_run"] == "1"
rec.update(disclosed(rec.pop("disclosure")))
rec["gates"] = lines(gates)
use = [json.loads(x) for x in lines(calls)]
rec["calls"] = len(use)
rec["max_turns_hit"] = sum(u.get("max_turns") is True for u in use)
for k, n in (("turns", "turns"), ("input_tokens", "input_tokens"), ("cache_write_tokens", "cache_creation_input_tokens"),
             ("cache_read_tokens", "cache_read_input_tokens"), ("output_tokens", "output_tokens"), ("cost_usd", "cost_usd")):
    v = [u.get(n) for u in use]
    rec[k] = sum(v) if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v) else None
if os.path.isdir(outcomes):
    rec["items"] = []
    for i in sorted(os.listdir(outcomes)):
        o = lines(os.path.join(outcomes, i)) + ["", "", "", "", ""]
        rec["items"].append(dict(zip(("outcome", "reason", "pr", "start_commit", "end_commit"), (o[0] + " " + o[1]).split()),
                                 id=i, diff_stat=o[2] or None, **disclosed(o[3]), reviews=reviews(o[4])))
path = ".factory/reports/runs.jsonl"
if os.path.islink(path):
    sys.exit("record: runs.jsonl is a symlink")
with open(path, "a") as f:
    f.write(re.sub(creds + "[A-Za-z0-9_-]*", "[redacted]", json.dumps(rec)) + "\n")
PY
)
# Existing test files changed, dependencies disclosed, scope and weighted size, once gates passed.
disclosure() { [ -z "${gated:-}" ] || echo "${#changed[@]} $([ -s "$view/deps.md" ] && echo 1 || echo 0) $scope $weighted"; }
record() {
  local rc=$1 o=$run_outcome stat=""
  [ "$rc" = 0 ] || { o=failed; [ -z "$gate_block" ] || o=blocked; }
  local base
  base=$(git rev-parse -q --verify "${ref:-}^{commit}" 2> /dev/null) || true
  [ -z "${commit:-}" ] || stat=$(git diff --shortstat "$start" "$commit" 2> /dev/null | sed 's/^ //') || true
  python3 -I -c "$record_py" record "$creds_re" "$calls" "$gates_log" "$view/outcomes" entry="$entry" \
    started="$began" ended="$(date -u +%FT%TZ)" base="$base" \
    start_commit="${start:-$base}" end_commit="${commit:-${start:-$base}}" diff_stat="$stat" outcome="${o:-completed}" reason="$run_reason" exit_code="$rc" \
    dry_run="${FACTORY_DRY_RUN:-0}" disclosure="$(disclosure)"
}
trap 'record $? || true; rm -rf "$view"; git worktree prune' EXIT
mkdir "$view/repo" "$view/input" "$view/skills"
ref="<base>" repo="<owner/repo>"
max_turns="<turns>" minutes="<minutes>"
level="<level>"
# Credentials, providers and endpoints that would override the subscription login.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_PROFILE \
  ANTHROPIC_FEDERATION_RULE_ID ANTHROPIC_ORGANIZATION_ID ANTHROPIC_BASE_URL ANTHROPIC_CUSTOM_HEADERS \
  CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY CLAUDE_CODE_USE_MANTLE \
  CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD
caps=(--max-turns "$max_turns")
git archive "$ref" | tar -x -C "$view/repo"

# Project skills are repo-relative, read from the tracked snapshot and must resolve inside it;
# only regular, non-hidden .md and .py files are copied. Their paths, link and target, join deny.
skills=() consumed=()
snap=$(cd -P "$view/repo" && pwd)
for s in ${skills[@]+"${skills[@]}"}; do
  case "$s" in /*) src=$s ;; *) src=$view/repo/$s ;; esac
  real=$(cd -P "$src" && pwd)
  case "$s" in
    /*) ;;
    *) case "$real/" in "$snap"/*) ;; *) echo "skill $s resolves outside the snapshot" >&2; exit 1 ;; esac
      consumed+=("$s" "$s/*" "${real#"$snap"/}" "${real#"$snap"/}/*") ;;
  esac
  d="$view/skills/$(basename "$s")"
  mkdir "$d"
  (cd "$real" && find . -type f ! -path '*/.*' \( -name '*.md' -o -name '*.py' \) -print0 |
    tar --null -T - -cf -) | tar -x -C "$d"
done

# User guidance after the default prompt, before the record format; setup never writes these files.
overlay() { local f=.factory/automations/$entry.$1.local.md; [ ! -f "$f" ] || { echo; cat "$f"; echo; }; }

fetch() { :; }

analyze() {
  local rc=0
  prompt="$(cat ".factory/automations/$entry.md" && overlay judge)"
  prompt+="
Date: $day
Snapshot: $ref at $(git rev-parse --short "$ref")"
  (cd "$view" && claude -p --restricted --safe-mode --tools "Read,Grep,Glob" --strict-mcp-config \
    --no-session-persistence --permission-mode dontAsk "${caps[@]}" --output-format json \
    "$prompt" < /dev/null) > "$view/analyze.json" || rc=$?
  python3 -I -c "$record_py" json "$view/analyze.json" "$calls" > "$view/report.md"
  [ "$rc" = 0 ] || exit "$rc"
  test -s "$view/report.md"
  mv "$view/report.md" "$out/$day.md"
}

post_check() { :; }

post() { :; }

# draft-pr and pr only. Destination, gates and test command are fixed here at setup.
remote="<remote url>" branch="factory/$entry"
title="chore: $entry automation $day"
# dep_files=1 only for entries that fix source code; see runners.md.
# ceiling: a runaway guard in weighted lines (a deletion weighs 1/4), not a quality limit.
test_cmd="<test command>" ceiling=10000 summary_cap=65536 dep_files=0
# Patterns stay literal; expanded against the checkout they would miss new files.
set -f
allow=("<path glob>")
deny=(.github/* .gitlab-ci.yml .circleci/* .buildkite/* Jenkinsfile .factory/* .husky/* .githooks/*
  .pre-commit-config.yaml .gitattributes CODEOWNERS */CODEOWNERS .cursor/skills/verify-*
  *.claude/settings* *.claude/hooks/* .cursor/*.json .cursor/hooks/* .codex/* .gemini/* .mcp.json
  .vscode/* .devcontainer/*)
set +f
deny+=(${consumed[@]+"${consumed[@]}"})
tests_re='(^|/)(tests?|__tests__|spec)/|[._-](test|spec)\.[A-Za-z]+$|(^|/)test_[^/]*\.py$'
# Generated lockfiles skip the ceiling (bun.lockb the binary check) and are disclosed instead.
locks_re='(^|/)(package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|uv\.lock|poetry\.lock|pdm\.lock|Pipfile\.lock|Cargo\.lock|go\.sum)$'
generated_re='\.min\.(js|css)$|\.(js|css)\.map$|_pb2(_grpc)?\.pyi?$|\.pb\.go$'
manifests_re='(^|/)(package\.json|pyproject\.toml|Cargo\.toml|go\.mod)$'
pr="" start="" commit="" gated="" changed=() scope="" why="" weighted="" refactors=()
scope_rule='scope: minimal, or scope: refactor <why a smaller fix is worse> when restructuring first makes the fix better; then commit each refactor step yourself with git commit, existing tests unchanged and passing at each, and leave the behaviour change uncommitted.'
deps_py=$(cat <<'PY'
import json, re, subprocess, sys
start, commit, summary, locks_re, *guarded = sys.argv[1:]
def show(rev, p):
    r = subprocess.run(["git", "show", f"{rev}:{p}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""
def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()
def pep508(xs):
    return {norm(re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", x)[1]) for x in xs if isinstance(x, str)}
def pop(d, path):
    *parents, key = path
    chain = [d]
    for k in parents:
        if not isinstance(chain[-1].get(k), dict):
            return None
        chain.append(chain[-1][k])
    v = chain[-1].pop(key, None)
    for parent, k in zip(reversed(chain[:-1]), reversed(parents)):
        if v is None or parent[k]:
            break
        del parent[k]
    return v
def npm(t):
    d = json.loads(t or "{}")
    deps = {k: pop(d, (k,)) for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")}
    return {k for v in deps.values() for k in v or {}}, d, deps
def pyproject(t):
    import tomllib
    d = tomllib.loads(t)
    py = [("project", "dependencies"), ("tool", "uv", "dev-dependencies")]
    groups = [("project", "optional-dependencies"), ("dependency-groups",)]
    poetry = [("tool", "poetry", "dependencies"), ("tool", "poetry", "dev-dependencies")] + [
        ("tool", "poetry", "group", g, "dependencies") for g in d.get("tool", {}).get("poetry", {}).get("group", {})]
    deps = {p: pop(d, p) for p in py + groups + poetry}
    xs = [x for p in py for x in deps[p] or []] + [x for p in groups for v in (deps[p] or {}).values() for x in v]
    return pep508(xs) | {norm(k) for p in poetry for k in deps[p] or {} if k != "python"}, d, deps
def cargo(t):
    import tomllib
    d = tomllib.loads(t)
    keys = ("dependencies", "dev-dependencies", "build-dependencies")
    paths = [(s,) for s in keys] + [("target", x, s) for x in d.get("target", {}) for s in keys] + [("workspace", "dependencies")]
    deps = {p: pop(d, p) for p in paths}
    return {k for v in deps.values() for k in v or {}}, d, deps
def gomod(t):
    names, rest, req, inside = set(), [], [], False
    for l in t.splitlines():
        w = l.split("//")[0].split()
        if inside:
            inside = w != [")"]
            req += [w] if inside and w else []
        elif w[:1] == ["require"]:
            inside = w[1:] == ["("]
            req += [] if inside else [w[1:]]
        elif w:
            rest.append(w)
    return {w[0] for w in req}, rest, sorted(req)
parsers = {"package.json": npm, "pyproject.toml": pyproject, "Cargo.toml": cargo, "go.mod": gomod}
files = subprocess.run(["git", "diff", "--name-only", "-z", "--no-renames", start, commit], capture_output=True, text=True, check=True).stdout.split("\0")
new, unparsed, locks, moved = [], [], [], False
for f in filter(None, files):
    base = f.rsplit("/", 1)[-1]
    if base in parsers:
        try:
            (now, rest, dn), (was, old, do) = parsers[base](show(commit, f)), parsers[base](show(start, f))
        except Exception:
            if f in guarded:
                sys.exit(f"{f} outside the allowlist and not parsed")
            unparsed.append(f)
            continue
        if f in guarded and rest != old:
            sys.exit(f"{f} outside the allowlist: changes more than dependencies")
        new += [(n, f) for n in sorted(now - was)]
        moved = moved or dn != do
    elif re.search(locks_re, f):
        locks.append(f)
    elif base in ("requirements.txt", "Pipfile"):
        unparsed.append(f)
said = [m for m in (re.match(r"dependency: (\S+) +(\S.*)", l) for l in open(summary, errors="replace")) if m]
missing = [n for n, f in new if norm(n) not in {norm(m[1]) for m in said}]
if missing:
    sys.exit("new package without a dependency line: " + ", ".join(missing))
if new or unparsed or locks:
    print("## Adds dependencies\n\nNeeds human approval; the factory never merges.\n")
    for m in said[:50]:
        print(f"- {m[1]}: {m[2]}"[:200])
    if new:
        print("\nNew packages: " + ", ".join(f"{n} ({f})" for n, f in new))
    if unparsed or locks:
        print("\nDependency files changed: " + ", ".join(unparsed + locks))
    if locks and not moved:
        print("\nLockfile changed without a detected manifest dependency change; review resolutions and integrity.")
    print()
PY
)

clip() {
  local l n=0
  while IFS= read -r l; do
    if [ "$n" -lt "$1" ]; then printf '%s\n' "${l:0:200}"; fi
    n=$((n + 1))
  done
  if [ "$n" -gt "$1" ]; then echo "[$((n - $1)) more lines]"; fi
}

block() { echo "gate: $*" >&2; printf '%s\n' "$*" >> "$gates_log"; gate_block=1; exit 1; }

no_creds() { ! grep -qE "$creds_re"; }

# Final body of every external write; returns 1 in dry run so the caller writes nothing.
sendable() {
  [ "$(wc -c < "$1")" -le 65536 ] || block "body over GitHub's 65536 characters"
  no_creds < "$1" || block "credential-shaped text"
  [ "${FACTORY_DRY_RUN:-0}" != 1 ]
}

# Rollup of check runs and statuses: FAILURE or ERROR is red; PENDING, EXPECTED or none is not.
ci_state() {
  gh api graphql -f o="${repo%/*}" -f r="${repo#*/}" -f s="$1" --jq '.data.repository.object.statusCheckRollup.state' \
    -f query='query($o:String!,$r:String!,$s:GitObjectID!){repository(owner:$o,name:$r){object(oid:$s){... on Commit{statusCheckRollup{state}}}}}'
}

ledger_ok() {
  [ ! -L "$out/pushed.tsv" ] && { [ ! -e "$out/pushed.tsv" ] || [ -f "$out/pushed.tsv" ]; } ||
    block "$out/pushed.tsv is a symlink or not a regular file"
}

# Prints red after two red factory pushes on the PR, unknown on a failed lookup.
# Reset: a head nobody in the ledger pushed, with green CI.
ci_cap() {
  local c s red=0
  [ -f "$out/pushed.tsv" ] || return 0
  for c in $(awk -v p="$pr" '$1 == p {print $2}' "$out/pushed.tsv" | tail -n 2); do
    s=$(ci_state "$c") || { echo unknown; return; }
    case $s in FAILURE | ERROR) red=$((red + 1)) ;; esac
  done
  [ "$red" = 2 ] || return 0
  if ! awk -v p="$pr" -v h="$head" '$1 == p && $2 == h {f = 1} END {exit !f}' "$out/pushed.tsv"; then
    s=$(ci_state "$head") || { echo unknown; return; }
    [ "$s" != SUCCESS ] || return 0
  fi
  echo red
}

# issue-pipeline keeps its own pushed.tsv and never re-pushes.
ledger() { declare -F pipeline > /dev/null || printf '%s %s\n' "$1" "$commit" >> "$out/pushed.tsv"; }

edit() {
  local prs head prompt why tools=Bash,Read,Grep,Glob,Edit,Write rc=0
  check=$view/check work=$view/work
  start=$(git rev-parse "$ref")
  prs=$(gh pr list --repo "$repo" --head "$branch" --state open --json number,headRefOid,isCrossRepository \
    --jq '.[] | select(.isCrossRepository | not) | "\(.number) \(.headRefOid)"')
  read -r pr head <<< "$prs"
  if [ -n "$pr" ]; then
    git fetch -q "$remote" "refs/heads/$branch"
    [ "$(git rev-parse FETCH_HEAD)" = "$head" ] || block "$branch moved during the run"
    start=$head
    ledger_ok
    case $(ci_cap) in
      red) run_reason=ci-cap why="the last two factory pushes failed CI" ;;
      unknown) run_reason=ci-unknown why="CI status unknown" ;;
    esac
    if [ -n "$run_reason" ]; then
      printf '\nescalated: %s: PR %s, %s; needs a human.\n' "$run_reason" "$pr" "$why" | tee -a "$out/$day.md"
      run_outcome=escalated
      exit 0
    fi
  elif [ "$branch" != "factory/$entry" ]; then
    block "no open PR on $branch"
  elif git ls-remote --exit-code -q "$remote" "refs/heads/$branch" > /dev/null; then
    block "$branch exists without an open PR"
  fi
  mkdir "$check"
  git worktree add -q --detach "$work" "$start"
  cp "$out/$day.md" "$check/report.md"
  cp .factory/profile.md "$check/"
  cp -R "$view/skills" "$check/"
  prompt="$(cat ".factory/automations/$entry.edit.md" && overlay edit)
Inputs, read-only: $check (report.md, profile.md, skills/). Edit only the working directory; never
push or run gh, and commit only refactor steps as below.
End your reply with a summary of what changed and why, last line edit: outcome=changed or
edit: outcome=stopped. When the fix needs credentials, production access, a decision the report
leaves open, or work outside this automation, do not guess: say what is missing and make the last
line escalated: <credentials|prod-access|ambiguous|out-of-scope>. Before that, one line
$scope_rule One line per
existing test file you changed, deleted or renamed (old path):
test-change: <path from the repo root>: <one-line reason>. Prefer existing code and the standard
library; add a package only for substantial functionality, with one line per new package:
dependency: <name> <why not in-house>."
  # No setting sources: tracked project settings in the checkout could switch auth or permissions.
  (cd "$work" && timeout "${minutes}m" claude -p --safe-mode --setting-sources '' --strict-mcp-config \
    --no-session-persistence --tools "$tools" --allowedTools "$tools" "${caps[@]}" \
    --permission-mode dontAsk --output-format json "$prompt" < /dev/null) | head -c $((8 * summary_cap + 1)) \
    > "$view/edit.json" || rc=$?
  python3 -I -c "$record_py" json "$view/edit.json" "$calls" > "$view/summary.md"
  [ "$rc" = 0 ] || [ "$(wc -c < "$view/edit.json")" -gt $((8 * summary_cap)) ]
  [ "$(wc -c < "$view/summary.md")" -le "$summary_cap" ] || block "summary over $summary_cap bytes"
  if [[ $(tail -n1 "$view/summary.md") =~ ^escalated:\ (credentials|prod-access|ambiguous|out-of-scope)$ ]]; then
    printf '\nescalated: %s: the edit stopped; needs a human.\n' "${BASH_REMATCH[1]}" | tee -a "$out/$day.md"
    run_outcome=escalated run_reason=${BASH_REMATCH[1]}
    exit 0
  fi
  if [ "$(tail -n1 "$view/summary.md")" != "edit: outcome=changed" ]; then
    echo "edit: no change"
    run_outcome=no-change
    exit 0
  fi
  commit_edit "$title"
}

# The edit's own commits survive only under scope refactor; what is left becomes the last commit.
commit_edit() {
  grep -q '^scope: *refactor ' "$view/summary.md" || git -C "$work" reset -q --soft "$start"
  git -C "$work" add -A
  git -C "$work" diff --cached --quiet || git -C "$work" commit -q -m "$1"
  commit=$(git -C "$work" rev-parse HEAD)
}

scope_gate() {
  local l c p cs=()
  [ "$(grep -c '^scope:' "$view/summary.md")" -le 1 ] || block "more than one scope line"
  l=$(sed -n 's/^scope: *//p' "$view/summary.md")
  case $l in
    minimal) scope=minimal ;;
    "refactor "*[![:space:]]*) scope=refactor why=${l#refactor } ;;
    *) block "no scope line: scope: minimal or scope: refactor <why a smaller fix is worse>" ;;
  esac
  git merge-base --is-ancestor "$start" "$commit" || block "commit does not descend from the start"
  [ -z "$(git rev-list --merges "$start..$commit")" ] || block "merge commit in the edit"
  p=$(comm -23 <(git log --format= --name-only --no-renames "$start..$commit" | sort -u) \
    <(git diff --name-only --no-renames "$start" "$commit" | sort -u) | head -n 1)
  [ -z "$p" ] || block "a commit changes $p, unchanged in the final diff"
  mapfile -t cs < <(git rev-list --reverse "$start..$commit")
  [ "$scope" = minimal ] || [ ${#cs[@]} -ge 2 ] || block "scope refactor needs refactor commits before the behaviour commit"
  [ "$scope" = minimal ] || refactors=("${cs[@]:0:${#cs[@]}-1}")
  for c in ${refactors[@]+"${refactors[@]}"}; do
    while IFS= read -r p; do
      [[ ! $p =~ $tests_re ]] || block "refactor commit ${c:0:12} changes existing test $p"
    done < <(git diff --name-only --no-renames --diff-filter=MD "$start" "$c")
  done
}

refactor_tests() {
  local c
  for c in ${refactors[@]+"${refactors[@]}"}; do
    git worktree add -q --detach "$view/at" "$c"
    (cd "$view/at" && timeout "${minutes}m" sh -c "$test_cmd") > "$view/at.log" 2>&1 ||
      block "tests failed at refactor commit ${c:0:12}, exit $?"
    git worktree remove --force "$view/at"
  done
}

gates() {
  local st p g ok a d r m rc quarters=0 tests=() deleted=() guarded=() seen=$'\n'
  changed=() refactors=()
  ! git diff --quiet "$start" "$commit" || block "empty diff"
  while IFS=$'\t' read -r st p; do
    for g in "${deny[@]}"; do [[ $p != $g ]] || block "CI, hook or policy path $p"; done
    ok=0
    for g in "${allow[@]}"; do [[ $p != $g ]] || ok=1; done
    if [ "$ok" = 0 ]; then
      [ "$dep_files" = 1 ] && [[ $p =~ $locks_re || $p =~ $manifests_re ]] || block "$p outside the allowlist"
      [[ $p =~ $locks_re ]] || guarded+=("$p")
    fi
    if [ "$ok" = 0 ] || [[ $p =~ $locks_re ]]; then
      m=$(git ls-tree "$start" -- "$p" | cut -c1-6; git ls-tree "$commit" -- "$p" | cut -c1-6)
      [ -z "$(grep -vx 100644 <<< "$m")" ] || block "$p is not a regular file"
    fi
    [[ $p =~ $tests_re ]] || continue
    tests+=("$p")
    [ "$st" = A ] || changed+=("$p")
    [ "$st" != D ] || deleted+=("$p")
  done < <(git diff --name-status --no-renames "$start" "$commit")
  while read -r a d p; do
    [ "$a" != - ] || [[ $p == bun.lockb || $p == */bun.lockb ]] || block "binary change $p"
    [[ ! $p =~ $locks_re && ! $p =~ $generated_re ]] || continue
    quarters=$((quarters + 4 * a + d))
  done < <(git diff --numstat --no-renames "$start" "$commit")
  weighted=$((quarters / 4))
  [ "$weighted" -le "$ceiling" ] || block "$weighted weighted changed lines, ceiling $ceiling"
  if [ ${#tests[@]} -gt 0 ]; then
    git diff -U0 --output-indicator-new='>' --output-indicator-old='<' "$start" "$commit" -- \
      "${tests[@]}" > "$view/tests.diff"
    ! grep -qE '^>.*(\.skip\(|\.only\(|\bx(it|describe|test)\(|@pytest\.mark\.(skip|xfail)|@unittest\.skip|\bt\.Skip|#\[ignore\]|@Disabled|@Ignore)' \
      "$view/tests.diff" || block "test skipped"
  fi
  sed -n 's/^test-change: /- /p' "$view/summary.md" > "$view/reasons.md"
  while IFS= read -r r; do
    m=""
    for p in ${changed[@]+"${changed[@]}"}; do
      [[ $r != "- $p: "* || ${#p} -le ${#m} ]] || m=$p
    done
    [ -n "$m" ] || block "test-change line names no changed existing test: $r"
    [[ ${r#"- $m: "} = *[![:space:]]* ]] || block "blank test-change reason for $m"
    [[ $seen != *$'\n'"$m"$'\n'* ]] || block "duplicate test-change for $m"
    seen+="$m"$'\n'
  done < "$view/reasons.md"
  for p in ${changed[@]+"${changed[@]}"}; do
    [[ $seen == *$'\n'"$p"$'\n'* ]] || block "no test-change reason for $p"
  done
  python3 -I -c "$deps_py" "$start" "$commit" "$view/summary.md" "$locks_re" ${guarded[@]+"${guarded[@]}"} \
    > "$view/deps.md" 2> "$view/deps.err" ||
    block "$(tail -n 1 "$view/deps.err")"
  scope_gate
  (cd "$work" && timeout "${minutes}m" sh -c "$test_cmd") > "$out/$day-tests.log" 2>&1 ||
    block "tests failed, exit $?"
  refactor_tests
  if [ ${#changed[@]} -gt 0 ]; then
    git worktree add -q --detach "$view/old" "$commit"
    git -C "$view/old" checkout -q "$start" -- "${changed[@]}"
    rc=0
    (cd "$view/old" && timeout "${minutes}m" sh -c "$test_cmd") > "$view/old.log" 2>&1 || rc=$?
    { printf '## Modifies existing tests\n\nNeeds human approval; the factory never merges.\n\n'
      clip 50 < "$view/reasons.md"
      if [ "$rc" = 124 ]; then
        printf '\nOld tests timed out after %s minutes: no evidence.\n' "$minutes"
      elif [ "$rc" = 0 ]; then
        printf '\nOld tests still pass on the new code: test edit not needed for this fix, review closely.\n'
      else
        printf '\nOld tests fail on the new code (exit %s): change needed.\n\n' "$rc"
        tail -n 20 "$view/old.log" | clip 20 | sed 's/^/    /'
      fi
      [ ${#deleted[@]} = 0 ] || printf '\nDeleted: %s\n' "${deleted[@]}"
      printf '\nChanged test lines:\n\n'
      git diff --diff-filter=d "$start" "$commit" -- "${changed[@]}" | clip 80 | sed 's/^/    /'
      echo; } > "$view/section.md"
  fi
  { git diff "$start" "$commit"; git log --format=%B "$start..$commit"; cat "$view/summary.md" "$view/deps.md"; [ ! -e "$view/section.md" ] || cat "$view/section.md"; } |
    no_creds || block "credential-shaped text"
  [ ! -e "$view/section.md" ] || cp "$view/section.md" "$out/$day-test-change.md"
  gated=$start:$commit
  echo passed >> "$gates_log"
}

add_label() {
  gh label create "$1" --repo "$repo" --description "$2" > /dev/null 2>&1 || true
  gh pr edit "$url" --repo "$repo" --add-label "$1" > /dev/null || echo "publish: label $1 not added" >&2
}

publish() {
  local draft=() url disclosed=""
  if [ -z "$commit" ] || [ "$gated" != "$start:$commit" ]; then gates; fi
  [ ${#changed[@]} = 0 ] && [ ! -s "$view/deps.md" ] && [ "$scope" = minimal ] || disclosed=1
  [ "$level" != draft-pr ] && [ -z "$disclosed" ] || draft=(--draft)
  { [ "$scope" = minimal ] || printf '## Refactor scope\n\n%s\n\n%s\n\n' "${why:0:500}" \
      "Refactor commits first, existing tests unchanged and passing at each; the last commit changes behaviour."
    cat "$view/deps.md"
    [ ${#changed[@]} = 0 ] || cat "$view/section.md"
    printf 'Automation `%s`, %s. Base %s, start %s, commit %s. Gates passed. Scope %s, %s weighted lines.\n\n' \
    "$entry" "$day" "$(git rev-parse "$ref")" "$start" "$commit" "$scope" "$weighted"
    cat "$view/summary.md"; } > "$view/body.md"
  sendable "$view/body.md" || return 0
  ledger_ok
  if [ -n "$pr" ] && [ -n "$disclosed" ]; then
    gh pr ready "$pr" --repo "$repo" --undo || block "could not return PR $pr to draft"
  fi
  git push -q "$remote" "$commit:refs/heads/$branch"
  if [ -n "$pr" ]; then
    ledger "$pr"
    gh pr comment "$pr" --repo "$repo" --body-file "$view/body.md"
    url=$pr
  else
    url=$(gh pr create --repo "$repo" ${draft[@]+"${draft[@]}"} --base "$ref" --head "$branch" --title "$title" \
      --body-file "$view/body.md")
    echo "$url"
    ledger "${url##*/}"
  fi
  [ ${#changed[@]} = 0 ] || add_label factory:test-change "Factory edit changes existing tests"
  [ ! -s "$view/deps.md" ] || add_label factory:dependency "Factory edit adds dependencies"
  [ "$scope" = minimal ] || add_label factory:refactor "Factory edit refactors before the fix"
  run_outcome=published
}

fetch
analyze
post_check
case "$level" in
  comment) if sendable "$out/$day.md"; then post; fi ;;
  draft-pr | pr)
    if declare -F pipeline > /dev/null; then
      pipeline
    else
      edit
      publish
    fi
    ;;
esac
