import datetime
import json
import os
import re
import subprocess
import unittest

import test_run
from test_run import agent_analytics

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_SH = os.path.join(HERE, "..", "assets", "issue-pipeline.sh")
FIX_ISSUES = os.path.abspath(os.path.join(HERE, "..", "..", "fix-issues"))
TRIAGE = os.path.join(FIX_ISSUES, "references", "triage.md")

CLAUDE = r"""#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
ev = os.environ.get("evidence", "")
with open(os.environ["LOG"], "a") as f:
    f.write("claude " + " ".join(a.replace("\n", " ") for a in args[:-1]) + (" evidence=" + ev if ev else "") + "\n")
skills = os.path.join(os.environ.get("check", ""), "skills")
with open(os.environ["LOG"] + ".prompts", "a") as f:
    f.write(json.dumps({"evidence": ev, "args": args[:-1], "prompt": args[-1],
                        "skills": sorted(os.listdir(skills)) if os.environ.get("check") else None}) + "\n")
scen = json.load(open(os.environ["SCEN"]))
tools = args[args.index("--tools") + 1]
fmt = args[args.index("--output-format") + 1] if "--output-format" in args else ""
if fmt == "stream-json":
    prefix = re.search(r"prefix (\S+)", args[-1])[1]
    result = "".join(json.dumps(o) + "\n" for o in scen.get("agent", {}).get(prefix, []))
    print(json.dumps({"type": "system", "subtype": "init", "mcp_servers": []}))
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result}))
elif os.getcwd().endswith("/review"):
    seen = [os.path.join(d, n) for d, _, ns in os.walk(".") for n in ns]
    raw = any("RAW-ISSUE-TEXT" in open(p, errors="replace").read() for p in seen) or "RAW-ISSUE-TEXT" in args[-1]
    with open(os.environ["LOG"] + ".review", "a") as f:
        f.write(json.dumps({"raw": raw, "top": sorted(os.listdir("."))}) + "\n")
    i = re.search(r"/fix-([^/]+)/review$", os.getcwd())[1]
    s = scen["items"].get(i, {})
    out = s.get("review-" + args[args.index("--model") + 1], s.get("review", "- src/1:1: nit\nreview: verdict=approve\n"))
    print(json.dumps({"result": out, "num_turns": 1}))
elif tools == "Read,Grep,Glob":
    sys.stdout.write(open(os.environ["REPORT"]).read())
elif tools == "":
    i, feat = re.search(r"fix-issues: id=(\S+) verdict=\S+ feature=(\S+)", sys.stdin.read()).groups()
    if scen["items"].get(i, {}).get("spec") == "bad":
        print("feature: " + feat + "\n\nsee https://example.invalid")
    elif scen["items"].get(i, {}).get("spec") == "secret":
        print(f"feature: {feat}\n\n## Preconditions and data\n\nd\n\n## Steps\n\ns\n\n"
              "## Expected final state\n\ne\n\n## Broken final state\n\n    sk-ant-1234567890abcdef")
    else:
        print(f"feature: {feat}\n\n## Preconditions and data\n\nd\n\n## Steps\n\ns\n\n"
              "## Expected final state\n\ne\n\n## Broken final state\n\nb")
else:
    i, stage = re.search(r"/fix-([^/]+)/evidence/([a-z]+)$", ev).groups()
    s = scen["items"].get(i, {})
    if s.get("fail") == stage:
        sys.exit(1)
    def put(path, text):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        open(path, "w").write(text)
    if s.get("norecord") == stage:
        put(f"{ev}/{dict(reproduce='repro').get(stage, stage)}.md", "did the work\n")
    elif s.get("escalate") == stage:
        put(f"{ev}/{dict(reproduce='repro').get(stage, stage)}.md", "needs the prod database\nescalated: prod-access\n")
    elif stage == "reproduce":
        put(ev + "/repro.md", "steps\nrepro: outcome=" + s.get("repro", "reproduced") + "\n")
    elif stage == "fix":
        put(".github/ci.yml" if s.get("deny") else "src/" + i, "fixed\n")
        if s.get("instructions"):
            put(s["instructions"], "always\n")
        if s.get("test") == "red":
            put(f"tests/{i}_test.sh", f"test -f src/{i}\n")
        elif s.get("test") == "green":
            put(f"tests/{i}_test.sh", "true\n")
        if s.get("pause"):
            put(os.environ["REPO"] + "/.factory/pause", "")
        if s.get("edit_test"):
            open("tests/run_all.sh", "a").write("true\n")
        put(ev + "/fix.md", "root cause\n" + ("test-change: tests/run_all.sh: tidy\n" if s.get("edit_test") else "")
            + "scope: minimal\nfix: outcome=changed\n")
    else:
        put(ev + "/verify.md", "runs\nverify: outcome=" + s.get("verify", "confirmed") + "\n")
"""

GH = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["LOG"], "a") as f:
    f.write("gh " + " ".join(a.replace("\n", " ") for a in args) + "\n")
path = os.environ["GHSTATE"]
st = json.load(open(path))
cmd, opt, pos, i = " ".join(args[:2]), {}, [], 2
while i < len(args):
    if args[i] in ("--draft", "--name-only"):
        opt[args[i][2:]], i = True, i + 1
    elif args[i].startswith("--"):
        opt[args[i][2:]], i = args[i + 1], i + 2
    else:
        pos, i = pos + [args[i]], i + 1
if cmd in st["fail"]:
    sys.exit(1)
issues = st["issues"]
def out(v):
    jq = opt.get("jq")
    if jq is None:
        print(json.dumps(v))
    elif jq in (".[].number", ".[].url"):
        for x in v:
            print(x[jq[4:]])
    elif jq == ".[] | select(.isCrossRepository | not) | .url":
        for x in v:
            if not x.get("isCrossRepository"):
                print(x["url"])
    elif jq in (".state", ".body"):
        print(v[jq[1:]])
    elif jq.startswith(".closedByPullRequestsReferences[] |"):
        for x in v.get("closedByPullRequestsReferences", []):
            print(x.get("repo", "o/r"), x["number"])
    else:
        sys.exit("stub: jq " + jq)
def save():
    json.dump(st, open(path, "w"))
def read(p):
    return open(p).read()
search = opt.get("search", "")
if cmd == "issue list" and search.startswith('"fix-issues-error:'):
    out([v for v in issues.values() if search.split('"')[1] in v["body"]])
elif cmd in ("issue list", "pr list") and search.startswith("updated:"):
    out([])
elif cmd == "issue list":
    out([v for v in issues.values() if "label" not in opt or opt["label"] in [x["name"] for x in v["labels"]]])
elif cmd == "issue view":
    out(issues[pos[0]])
elif cmd == "issue create":
    n = st["next"]
    st["next"] += 1
    issues[str(n)] = {"number": n, "title": opt["title"], "body": read(opt["body-file"]), "state": "OPEN",
                      "labels": [], "assignees": [], "createdAt": "2026-01-01T00:00:00Z"}
    save()
    print(f"https://github.com/o/r/issues/{n}")
elif cmd == "issue comment":
    st["comments"].append({"issue": pos[0], "body": read(opt["body-file"])})
    save()
elif cmd == "pr list":
    out([p for p in st["prs"] if p["head"] == opt["head"]])
elif cmd == "pr view":
    p = st.get("pulls", {}).get(pos[0]) or sys.exit(1)
    if opt.get("jq") == ".state":
        print(p["state"])
    elif opt.get("json") == "mergeCommit":
        print(p.get("merge", "null"))
    elif opt.get("json") == "state,mergeCommit":
        print(p["state"], p.get("merge", "null"))
    elif opt.get("json") == "state,mergeCommit,title,reviews":
        print(p["state"], p.get("changes", 0), p.get("merge", "null"), p.get("title", "t"))
    elif opt.get("json", "").startswith("state,isDraft,"):
        print(p["state"], str(p.get("draft", False)).lower(), p["head"], p.get("mergeable", "MERGEABLE"),
              p.get("base", "main"), p.get("branch", "factory/fix-1"), str(p.get("cross", False)).lower())
    else:
        print(p["state"], str(p.get("cross", False)).lower(), p.get("base", "main"), p.get("merge", "null"),
              p.get("commits", 1))
elif cmd == "pr diff":
    print("\n".join(st["pulls"][pos[0]].get("files", [])))
elif cmd == "pr ready":
    st["ready"] = st.get("ready", []) + [pos[0]]
    save()
elif cmd == "pr merge":
    st["merged"] = st.get("merged", []) + [pos[0]]
    st["pulls"][pos[0]].update(state="MERGED", merge=st["merge_sha"])
    save()
elif cmd == "api graphql":
    print(st.get("ci", {}).get(next(a[2:] for a in pos if a.startswith("s=")), "SUCCESS"))
elif cmd == "pr create":
    url = f"https://github.com/o/r/pull/{len(st['prs']) + 1}"
    st["prs"].append({"head": opt["head"], "url": url, "title": opt["title"], "draft": opt.get("draft", False),
                      "body": read(opt["body-file"])})
    save()
    print(url)
else:
    sys.exit("stub: " + cmd)
"""

OK = " issue-pipeline claude:sonnet=approve,claude:opus=approve, 0 0 minimal 1"
SPEC_HEADINGS = ["## Spec", "## Reproduction", "## Root cause and fix", "## Tests", "## Verification"]


def fetch_functions():
    with open(TRIAGE) as f:
        section = f.read().split("## Fetch", 1)[1].split("### Write back", 1)[0]
    return "\n".join(re.findall(r"```bash\n(.*?)```", section, re.S))


class PipelineTest(unittest.TestCase):
    setUp_repo = test_run.RunShTest.setUp
    tearDown = test_run.RunShTest.tearDown
    git = test_run.RunShTest.git
    write = test_run.RunShTest.write
    calls = test_run.RunShTest.calls
    remote_heads = test_run.RunShTest.remote_heads

    def setUp(self):
        self.setUp_repo()
        t = self.tmp.name
        for name, body in (("claude", CLAUDE), ("gh", GH)):
            with open(f"{t}/bin/{name}", "w") as f:
                f.write(body)
        os.makedirs(f"{t}/debugging")
        with open(f"{t}/debugging/SKILL.md", "w") as f:
            f.write("debug\n")
        self.write("tests/run_all.sh", 'for t in tests/*_test.sh; do sh "$t" || exit 1; done\n')
        self.write(".cursor/skills/verify-app/SKILL.md", "verify\n")
        for feat in "abcd":
            self.write(f".cursor/skills/verify-app/features/{feat}.md", f"journey {feat}\n")
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "verify skill")
        self.write(".factory/automations/issue-pipeline.md", "judge\n")
        self.write(".factory/automations/issue-pipeline.spec.md", "spec\n")
        for p in ("err-sentry", "lin"):
            self.write(f".factory/automations/{p}.fetch.md", f"prefix {p}\n")
        self.state = f"{t}/gh.json"
        self.env.update(REPO=self.repo, SCEN=f"{t}/scen.json", GHSTATE=self.state, REPORT=f"{t}/report.md")
        self.gh_state({}, [])
        self.out = f"{self.repo}/.factory/reports/issue-pipeline"
        self.fx = f"{self.repo}/.factory/reports/fix-issues"

    def gh_state(self, issues, fail, **extra):
        state = {"issues": {}, "prs": [], "comments": [], "next": 100, "fail": fail, **extra}
        for n, v in issues.items():
            state["issues"][str(n)] = {"number": n, "title": f"t{n}", "body": "b", "author": {"login": "u"},
                                       "createdAt": f"2026-11-0{n}T00:00:00Z", "labels": [], "comments": [],
                                       "url": f"https://github.com/o/r/issues/{n}", "state": "OPEN",
                                       "assignees": [], **v}
        with open(self.state, "w") as f:
            json.dump(state, f)

    def gh(self):
        with open(self.state) as f:
            return json.load(f)

    def run_pipeline(self, items, trust=("#",), label="", agent=None, dry=False, extra_fetch="", main="",
                     report_extra="", cap="3", flow="fix", verify_fixed="on", merge_level="draft",
                     reviewers="claude:sonnet", needs_human=None, run_minutes="240", models="", skills="",
                     stage_skills="", extra_skills=""):
        report = "".join(f"## {i}\n\nx\n\nfix-issues: id={i} verdict={v.get('verdict', 'new-bug')} "
                         f"feature={v.get('feature', 'a')} ref={v.get('ref', 'none')}\n\n" for i, v in items.items())
        with open(self.env["REPORT"], "w") as f:
            f.write(report + report_extra)
        with open(self.env["SCEN"], "w") as f:
            json.dump({"items": items, "agent": agent or {}}, f)
        with open(test_run.RUN_SH) as f:
            script = f.read()
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1",
                     "<level>": "draft-pr", "<remote url>": self.remote, "<test command>": "sh tests/run_all.sh",
                     "<path glob>": "*", "<weekly usd>": ""}.items():
            script = script.replace(k, v)
        with open(PIPELINE_SH) as f:
            pipeline = f.read()
        pipeline = pipeline.replace('("<trust prefix>")', "(" + " ".join(f'"{p}"' for p in trust) + ")")
        for k, v in {"<label>": label, "<run minutes>": run_minutes, "<app>": "app", "<cap>": cap, "<flow>": flow,
                     "<verify-fixed>": verify_fixed, "<merge level>": merge_level,
                     "reviewers=(claude:sonnet)": f"reviewers=({reviewers})"}.items():
            pipeline = pipeline.replace(k, v)
        pipeline = pipeline.replace("declare -A stage_skills=()", f"declare -A stage_skills=({stage_skills})")
        pipeline = pipeline.replace("extra_skills=()", f"extra_skills=({extra_skills})")
        if needs_human is not None:
            pipeline = pipeline.replace("needs_human=(test-change dependency refactor)", f"needs_human=({needs_human})")
        fetch = "fetch_new; fetch_deferred; " + (f"fetch_labeled {label}; " if label else "") + extra_fetch + "fetch_context"
        if models:
            self.assertIn(test_run.MODELS, script)
            script = script.replace(test_run.MODELS, f"declare -A models=({models})")
        script = script.replace("skills=()", f'skills=("{FIX_ISSUES}" "{self.tmp.name}/debugging" {skills})')
        script = script.replace("fetch() { :; }", fetch_functions() + f"\nfetch() {{ {fetch}; }}")
        script = script.replace("\nfetch\nanalyze\n", "\n" + pipeline + "\nfetch\nanalyze\n")
        if main:
            script = script[:script.index("\nfetch\nanalyze\npost_check\n")] + "\npreflight\n" + main
        path = f"{self.repo}/.factory/automations/issue-pipeline.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        for p in (self.log, self.log + ".prompts"):
            if os.path.exists(p):
                os.remove(p)
        env = dict(self.env, **({"FACTORY_DRY_RUN": "1"} if dry else {}))
        return subprocess.run([path], env=env, capture_output=True, text=True, timeout=300)

    def prompts(self):
        with open(self.log + ".prompts") as f:
            return [json.loads(x) for x in f]

    def report(self):
        with open(f"{self.out}/{datetime.date.today()}.md") as f:
            return f.read()

    def outcome(self, i):
        m = re.findall(rf"^pipeline: id={re.escape(i)} outcome=(\S+) reason=(\S+) pr=(\S+)$", self.report(), re.M)
        return m[-1]

    def stage_calls(self, i=None, stage=None):
        return [c for c in self.calls() if c.startswith("claude ") and " evidence=" in c
                and (i is None or f"/fix-{i}/" in c) and (stage is None or c.endswith("/" + stage))]

    def spec_calls(self):
        return [c for c in self.calls() if c.startswith("claude ") and "--output-format json" in c
                and "--tools  " in c + " "]

    def pr_creates(self):
        return [c for c in self.calls() if c.startswith("gh pr create")]

    def gh_writes(self):
        return [c for c in self.calls() if c.startswith("gh ")
                and not re.match(r"gh (issue list|issue view|pr list|pr view) ", c)]

    def rows(self, name):
        p = f"{self.fx}/{name}"
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return f.read().splitlines()

    def test_trusted_item_opens_one_draft_pr_and_links(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        prs = self.gh()["prs"]
        self.assertEqual(len(prs), 1)
        self.assertTrue(prs[0]["draft"])
        self.assertEqual(prs[0]["head"], "factory/fix-1")
        self.assertEqual(prs[0]["title"], "fix: #1 a")
        body = prs[0]["body"].splitlines()
        self.assertTrue(body[0].startswith("Automation `issue-pipeline`"))
        self.assertEqual(body[2], "Fixes #1")
        self.assertEqual([x for x in body if x in SPEC_HEADINGS], SPEC_HEADINGS)
        self.assertEqual(body[body.index("## Spec") + 2], "feature: a")
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/fix-1"])
        comments = self.gh()["comments"]
        self.assertEqual([c["issue"] for c in comments], ["1"])
        self.assertIn(prs[0]["url"], comments[0]["body"])
        self.assertEqual(len(self.rows("pushed.tsv")), 1)
        self.assertEqual(self.rows("linked.tsv"), ["1 " + prs[0]["url"]])
        self.assertEqual(self.outcome("1"), ("fixed", "linked", prs[0]["url"]))
        self.assertFalse(os.path.exists(f"{self.fx}/tmp/fix-1"))
        self.assertTrue(os.path.exists(f"{self.fx}/items/1/evidence/reproduce/repro.md"))

    def test_run_record_lists_items_and_counts_stage_calls(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            [rec] = [json.loads(x) for x in f]
        url = self.gh()["prs"][0]["url"]
        [item] = rec["items"]
        self.assertEqual({k: item[k] for k in ("id", "outcome", "reason", "pr", "start_commit", "diff_stat")},
                         {"id": "1", "outcome": "fixed", "reason": "linked", "pr": url, "start_commit": rec["base"],
                          "diff_stat": "1 file changed, 1 insertion(+)"})
        self.assertEqual(item["end_commit"], self.git("--git-dir", self.remote, "rev-parse", "factory/fix-1").strip())
        self.assertEqual((rec["outcome"], rec["calls"], rec["gates"]), ("completed", 6, ["passed"]))

    def test_item_records_carry_disclosures_once_gated(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b", "spec": "bad"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            [rec] = [json.loads(x) for x in f]
        self.assertEqual([(i["id"], i["test_changes"], i["dependency_change"]) for i in rec["items"]],
                         [("1", 0, False), ("2", None, None)])
        self.assertEqual((rec["test_changes"], rec["dependency_change"]), (None, None))

    def test_run_record_counts_a_failed_spec_call(self):
        stub = f"{self.tmp.name}/bin/claude"
        os.rename(stub, stub + ".orig")
        with open(stub, "w") as f:
            f.write(f"""#!/usr/bin/env python3
import json, subprocess, sys
p = subprocess.run([{stub + ".orig"!r}, *sys.argv[1:]], stdout=subprocess.PIPE, text=True)
spec = sys.argv[sys.argv.index("--tools") + 1] == ""
print(json.dumps({{"type": "result", "subtype": "error_max_turns" if spec else "success", "result": p.stdout,
                  "num_turns": 1, "total_cost_usd": 0.1, "usage": {{"output_tokens": 5}}}}))
sys.exit(1 if spec else p.returncode)
""")
        os.chmod(stub, 0o755)
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertNotEqual(r.returncode, 0)
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            [rec] = [json.loads(x) for x in f]
        self.assertEqual((rec["calls"], rec["turns"], rec["cost_usd"], rec["outcome"]), (2, 2, 0.2, "failed"))
        self.assertEqual(rec["items"][0]["reason"], "runner-error")

    def test_untrusted_assigned_closed_start_no_stage(self):
        self.gh_state({1: {}, 2: {"labels": [{"name": "factory"}], "assignees": [{"login": "x"}]},
                       3: {"labels": [{"name": "factory"}], "state": "CLOSED"}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b"}, "3": {"feature": "c"}},
                              trust=(), label="factory")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.stage_calls() + self.spec_calls(), [])
        self.assertEqual([self.outcome(i)[:2] for i in "123"],
                         [("skipped", "untrusted"), ("skipped", "assigned"), ("skipped", "closed")])

    def test_spec_rejected_starts_no_stage(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"spec": "bad"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.spec_calls()), 1)
        self.assertEqual(self.stage_calls(), [])
        self.assertEqual(self.outcome("1")[:2], ("blocked", "spec"))

    def test_not_reproduced_runs_no_fix(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"repro": "not-reproduced"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.stage_calls("1", "reproduce")), 1)
        self.assertEqual(self.stage_calls("1", "fix"), [])
        self.assertEqual(self.outcome("1")[:2], ("not-reproduced", "reproduce"))
        self.assertIn("1 repro: outcome=not-reproduced", r.stdout)
        with open(f"{self.fx}/items/1/summary.md") as f:
            self.assertIn("outcome=not-reproduced", f.read())

    def test_gate_block_skips_only_that_item(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "deny": True}, "2": {"feature": "b"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gate: CI, hook or policy path .github/ci.yml", r.stderr)
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/fix-2"])
        self.assertEqual(self.outcome("1")[:2], ("blocked", "gates"))
        self.assertEqual(self.outcome("2")[0], "fixed")

    def test_verify_not_confirmed_no_push_no_ticket(self):
        agent = {"err-sentry": [{"id": "C1", "title": "e", "body": "b", "url": "https://s.invalid/C1",
                                 "created": "2026-11-01T00:00:00Z", "updated": "2026-11-01T00:00:00Z",
                                 "labels": []}]}
        r = self.run_pipeline({"err-sentry-C1": {"verify": "insufficient"}}, trust=("err-sentry",), agent=agent,
                              extra_fetch="agent_fetch_new err-sentry < /dev/null; ")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.stage_calls("err-sentry-C1", "verify")), 1)
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])
        self.assertEqual(self.outcome("err-sentry-C1")[:2], ("blocked", "verify"))

    def test_red_green_line(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "test": "red"}, "2": {"feature": "b", "test": "green"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        bodies = {p["head"]: p["body"] for p in self.gh()["prs"]}
        self.assertIn("New tests fail on base (exit 1) and pass on the fix.", bodies["factory/fix-1"])
        self.assertIn("New tests pass on base: they do not capture the bug, review closely.",
                      bodies["factory/fix-2"])

    def test_cap_defers_fourth_and_refetches_it(self):
        self.gh_state({n: {} for n in (1, 2, 3, 4)}, [])
        items = {str(n): {"feature": f} for n, f in zip((1, 2, 3, 4), "abcd")}
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.gh()["prs"]), 3)
        self.assertEqual(self.outcome("4"), ("deferred", "cap", "none"))
        self.assertEqual(self.stage_calls("4"), [])
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        os.rename(f"{self.out}/{datetime.date.today()}.md", f"{self.out}/{yesterday}.md")
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        views = [c.split()[3] for c in self.calls() if c.startswith("gh issue view") and "--json number," in c]
        self.assertEqual(views, ["4"])
        self.assertEqual(self.outcome("4")[0], "fixed")

    def test_cap_from_profile_applied(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b"}}, cap="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.gh()["prs"]), 1)
        self.assertEqual(self.outcome("2"), ("deferred", "cap", "none"))
        self.assertEqual(self.stage_calls("2"), [])

    def test_local_overlays_reach_each_prompt_before_its_record_rules(self):
        names = ("judge", "spec", "reproduce", "fix", "verify", "review")
        for n in names:
            self.write(f".factory/automations/issue-pipeline.{n}.local.md", f"overlay-{n}" + "\n" * (n != "reproduce"))
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[0], "fixed")
        seen = {}
        for c in self.prompts():
            ev, args = c["evidence"], c["args"]
            n = ev.rsplit("/", 1)[1] if ev else "review" if "--model" in args else "judge" if "--restricted" in args and "Read,Grep,Glob" in args else "spec"
            seen[n] = c["prompt"]
        self.assertEqual(sorted(seen), sorted(names))
        for n, prompt in seen.items():
            with self.subTest(n):
                self.assertEqual([x for x in names if f"overlay-{x}" in prompt], [n])
                if n in ("reproduce", "fix", "verify"):
                    self.assertLess(prompt.index(f"overlay-{n}"), prompt.index("end your record with escalated:"))
                    self.assertRegex(prompt, rf"overlay-{n}\n+No git commit")
                    self.assertTrue(prompt.endswith(f"Stage: {n}."))
        for n in names:
            with open(f"{self.repo}/.factory/automations/issue-pipeline.{n}.local.md") as f:
                self.assertEqual(f.read(), f"overlay-{n}" + "\n" * (n != "reproduce"))

    def test_non_positive_cap_fails_before_any_stage(self):
        self.gh_state({1: {}}, [])
        for cap in ("0", "-1"):
            with self.subTest(cap):
                r = self.run_pipeline({"1": {}}, cap=cap)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f"gate: cap {cap} is not a positive whole number", r.stderr)
                self.assertEqual(self.stage_calls() + self.spec_calls(), [])
                self.assertEqual(self.gh_writes(), [])

    def test_unknown_flow_or_verify_fixed_fails_before_any_stage(self):
        self.gh_state({1: {}}, [])
        for kw, msg in (({"flow": "fix-only"}, "flow fix-only is not fix or repro-only"),
                        ({"flow": "<flow>"}, "flow <flow> is not fix or repro-only"),
                        ({"verify_fixed": "no"}, "verify-fixed no is not on or off")):
            with self.subTest(kw):
                r = self.run_pipeline({"1": {}}, **kw)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f"gate: {msg}", r.stderr)
                self.assertEqual(self.stage_calls() + self.spec_calls(), [])
                self.assertEqual(self.gh_writes(), [])

    def test_repro_only_posts_one_evidence_comment_and_starts_no_fix(self):
        self.gh_state({1: {}, 2: {}}, [])
        items = {"1": {"feature": "a"}, "2": {"feature": "b", "repro": "not-reproduced"}}
        r = self.run_pipeline(items, flow="repro-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("reproduced", "linked", "none"))
        self.assertEqual(self.outcome("2")[:2], ("not-reproduced", "reproduce"))
        self.assertEqual([c.rsplit("/", 1)[1] for c in self.stage_calls()], ["reproduce", "reproduce"])
        comments = self.gh()["comments"]
        self.assertEqual([c["issue"] for c in comments], ["1"])
        start = self.git("-C", self.repo, "rev-parse", "main").strip()
        self.assertTrue(comments[0]["body"].startswith(f"Reproduced on {start} by a scheduled run."))
        self.assertIn("## Spec\n\nfeature: a\n", comments[0]["body"])
        self.assertIn("repro: outcome=reproduced", comments[0]["body"])
        self.assertEqual(self.gh_writes(), [c for c in self.calls() if c.startswith("gh issue comment")])
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.rows("pushed.tsv") + self.rows("tickets.tsv"), [])
        self.assertEqual(self.rows("linked.tsv"), [f"1 {start}"])
        r = self.run_pipeline(items, flow="repro-only")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("skipped", "linked"))
        self.assertEqual(self.stage_calls("1") + self.gh_writes(), [])
        self.assertEqual(len(self.gh()["comments"]), 1)

    def test_repro_only_without_a_comment_destination_or_in_dry_run_writes_nothing(self):
        agent = {"err-sentry": [{"id": "C1", "title": "e", "body": "b", "url": "https://s.invalid/C1",
                                 "created": "2026-11-01T00:00:00Z", "updated": "2026-11-01T00:00:00Z",
                                 "labels": []}]}
        r = self.run_pipeline({"err-sentry-C1": {}}, trust=("err-sentry",), agent=agent, flow="repro-only",
                              extra_fetch="agent_fetch_new err-sentry < /dev/null; ")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("err-sentry-C1")[:2], ("skipped", "no-ticket"))
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}}, flow="repro-only", dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 repro: outcome=reproduced", r.stdout)
        self.assertEqual(self.outcome("1")[:2], ("deferred", "dry-run"))
        self.assertEqual(self.gh_writes() + self.rows("linked.tsv"), [])

    def test_verify_fixed_off_sends_fixed_items_to_the_report(self):
        sha = self.fix_commit()
        self.push_main()
        self.gh_state({1: {}, 2: {}}, [])
        items = {"1": {"verdict": "fixed", "ref": sha}, "2": {"feature": "a"}}
        r = self.run_pipeline(items, verify_fixed="off", cap="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("skipped", "verdict", "none"))
        self.assertEqual(self.stage_calls("1"), [])
        self.assertEqual([c["issue"] for c in self.gh()["comments"]], ["2"])
        self.assertEqual(self.outcome("2")[0], "fixed")

    def test_escalation_is_final_with_one_deduped_comment(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"escalate": "reproduce"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("escalated", "prod-access", "none"))
        self.assertEqual(self.stage_calls("1", "fix") + self.pr_creates(), [])
        [c] = self.gh()["comments"]
        self.assertEqual(c["issue"], "1")
        self.assertTrue(c["body"].startswith("Needs a human: a scheduled run stopped at reproduce on "))
        self.assertIn("## What is missing\n\nneeds the prod database\nescalated: prod-access\n", c["body"])
        self.assertEqual(self.rows("linked.tsv"), ["1 escalated"])
        r = self.run_pipeline({"1": {"escalate": "fix"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("escalated", "prod-access", "none"))
        self.assertEqual(len(self.gh()["comments"]), 1)
        self.assertEqual(self.remote_heads(), "")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        os.rename(f"{self.out}/{datetime.date.today()}.md", f"{self.out}/{yesterday}.md")
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith("gh issue view 1 ") and "--json number," in c])
        self.assertEqual(self.stage_calls() + self.gh_writes(), [])

    def test_escalation_in_dry_run_writes_nothing(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"escalate": "fix"}}, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry run: 1 escalated prod-access", r.stdout)
        self.assertEqual(self.outcome("1")[:2], ("deferred", "dry-run"))
        self.assertEqual(self.gh_writes() + self.rows("linked.tsv"), [])
        self.assertEqual(self.remote_heads(), "")

    def test_pause_during_item_defers_the_next(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "pause": True}, "2": {"feature": "b"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[0], "fixed")
        self.assertEqual(self.outcome("2"), ("deferred", "paused", "none"))
        self.assertEqual(self.stage_calls("2"), [])

    def test_rerun_with_pr_or_branch_skips(self):
        self.gh_state({1: {}, 2: {}}, [])
        self.git("-C", self.repo, "push", "-q", self.remote, "main:refs/heads/factory/fix-2")
        items = {"1": {"feature": "a"}, "2": {"feature": "b"}}
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("2")[:2], ("skipped", "branch-exists"))
        self.assertEqual(len(self.pr_creates()), 1)
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("skipped", "pr-exists"))
        self.assertEqual(self.pr_creates(), [])
        self.assertEqual(self.stage_calls(), [])
        self.assertEqual(len(self.gh()["prs"]), 1)

    def test_pr_create_failure_recovered_without_stages(self):
        self.gh_state({1: {}}, ["pr create"])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("blocked", "publish"))
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/fix-1"])
        self.assertEqual(len(self.rows("pushed.tsv")), 1)
        state = self.gh()
        state["fail"] = []
        with open(self.state, "w") as f:
            json.dump(state, f)
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.stage_calls() + self.spec_calls(), [])
        prs = self.gh()["prs"]
        self.assertEqual(len(prs), 1)
        self.assertTrue(prs[0]["draft"])
        with open(f"{self.fx}/items/1/body.md") as f:
            self.assertEqual(prs[0]["body"], f.read())
        self.assertEqual(self.rows("linked.tsv"), ["1 " + prs[0]["url"]])
        self.assertEqual([c["issue"] for c in self.gh()["comments"]], ["1"])

    def test_err_item_ticket_filed_once_and_reused(self):
        agent = {"err-sentry": [{"id": "C1", "title": "e", "body": "b", "url": "https://s.invalid/C1",
                                 "created": "2026-11-01T00:00:00Z", "updated": "2026-11-01T00:00:00Z",
                                 "labels": []}]}
        hook = f"{self.remote}/hooks/pre-receive"
        with open(hook, "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        kw = dict(trust=("err-sentry",), agent=agent, extra_fetch="agent_fetch_new err-sentry < /dev/null; ")
        r = self.run_pipeline({"err-sentry-C1": {}}, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("err-sentry-C1")[:2], ("blocked", "publish"))
        ticket = self.gh()["issues"]["100"]
        self.assertEqual(ticket["title"], "Error sentry-C1: a")
        self.assertEqual(ticket["body"].splitlines()[-1], "fix-issues-error: sentry-C1")
        self.assertEqual(self.rows("tickets.tsv"), ["sentry-C1 100"])
        os.remove(hook)
        r = self.run_pipeline({"err-sentry-C1": {}}, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([c for c in self.calls() if c.startswith("gh issue create")], [])
        self.assertEqual(self.rows("tickets.tsv"), ["sentry-C1 100"])
        prs = self.gh()["prs"]
        self.assertEqual(prs[0]["title"], "fix: err-sentry-C1 a")
        self.assertEqual(prs[0]["body"].splitlines()[2], "Fixes #100")
        self.assertEqual([c["issue"] for c in self.gh()["comments"]], ["100"])

    def test_secret_in_spec_files_no_ticket(self):
        agent = {"err-sentry": [{"id": "C1", "title": "e", "body": "b", "url": "https://s.invalid/C1",
                                 "created": "2026-11-01T00:00:00Z", "updated": "2026-11-01T00:00:00Z",
                                 "labels": []}]}
        r = self.run_pipeline({"err-sentry-C1": {"spec": "secret"}}, trust=("err-sentry",), agent=agent,
                              extra_fetch="agent_fetch_new err-sentry < /dev/null; ")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gate: credential-shaped text", r.stderr)
        self.assertEqual(len(self.stage_calls("err-sentry-C1", "verify")), 1)
        self.assertEqual(self.gh_writes(), [])
        self.assertEqual(self.gh()["issues"], {})
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.outcome("err-sentry-C1")[:2], ("blocked", "verify"))

    def test_crashed_claim_with_symlink_does_not_block_run(self):
        claim = f"{self.fx}/tmp/fix-9/patch/node_modules/.bin"
        os.makedirs(claim)
        os.symlink("../tool/cli.js", f"{claim}/tool")
        self.gh_state({1: {}, 9: {}}, [])
        r = self.run_pipeline({"9": {"feature": "b"}, "1": {"feature": "a"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("9")[:2], ("skipped", "claimed"))
        self.assertEqual(self.outcome("1")[0], "fixed")
        self.assertTrue(os.path.islink(f"{claim}/tool"))
        self.assertEqual(self.stage_calls("9"), [])

    def test_symlinked_claim_dir_still_blocks(self):
        os.makedirs(f"{self.fx}/tmp")
        os.symlink(self.tmp.name, f"{self.fx}/tmp/fix-9")
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: symlink under", r.stderr)
        self.assertEqual(self.stage_calls() + self.spec_calls(), [])

    def test_recover_ignores_fork_pr(self):
        self.gh_state({1: {}}, ["pr create"])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(self.outcome("1")[:2], ("blocked", "publish"), r.stderr)
        state = self.gh()
        state["fail"] = []
        state["prs"].append({"head": "factory/fix-1", "url": "https://github.com/x/r/pull/9", "title": "t",
                             "draft": False, "body": "b", "isCrossRepository": True})
        with open(self.state, "w") as f:
            json.dump(state, f)
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        ours = [p for p in self.gh()["prs"] if not p.get("isCrossRepository")]
        self.assertEqual(len(ours), 1)
        self.assertEqual(self.rows("linked.tsv"), ["1 " + ours[0]["url"]])
        comments = self.gh()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertIn(ours[0]["url"], comments[0]["body"])
        base = subprocess.run(["git", "-C", self.repo, "rev-parse", "main"], capture_output=True, text=True).stdout
        self.assertIn(f"reproduced on {base.strip()},", comments[0]["body"])

    def test_non_github_source_comment_script(self):
        agent = {"lin": [{"id": "ENG-12", "title": "e", "body": "b", "url": "https://l.invalid/ENG-12",
                          "created": "2026-11-01T00:00:00Z", "updated": "2026-11-01T00:00:00Z", "labels": []}]}
        got = f"{self.tmp.name}/comment"
        self.write(".factory/automations/lin.comment.sh", f'set -euo pipefail\n{{ echo "$1"; cat; }} > {got}\n')
        r = self.run_pipeline({"lin-ENG-12": {}}, trust=("lin",), agent=agent,
                              extra_fetch="agent_fetch_new lin < /dev/null; ")
        self.assertEqual(r.returncode, 0, r.stderr)
        url = self.gh()["prs"][0]["url"]
        with open(got) as f:
            native, comment = f.read().split("\n", 1)
        self.assertEqual(native, "ENG-12")
        self.assertIn(url, comment)
        self.assertEqual(self.gh()["comments"], [])
        self.assertEqual(self.outcome("lin-ENG-12"), ("fixed", "linked", url))

    def test_runner_error_stops_loop(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "fail": "reproduce"}, "2": {"feature": "b"}})
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.outcome("1")[:2], ("deferred", "runner-error"))
        self.assertEqual(self.outcome("2")[:2], ("deferred", "runner-error"))
        self.assertEqual(self.stage_calls("2"), [])
        self.assertFalse(os.path.exists(f"{self.fx}/items/1/summary.md"))

    def test_dry_run_one_item_no_writes(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b"}}, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.stage_calls("1")), 3)
        self.assertEqual(self.stage_calls("2"), [])
        self.assertIn("1 repro: outcome=reproduced", r.stdout)
        self.assertNotIn("gate:", r.stderr)
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])
        for name in ("pushed.tsv", "linked.tsv", "tickets.tsv"):
            self.assertEqual(self.rows(name), [])
        self.assertFalse(os.path.exists(f"{self.fx}/items/1/summary.md"))
        self.assertEqual([self.outcome(i)[:2] for i in "12"], [("deferred", "dry-run")] * 2)

    def reviews(self):
        with open(self.log + ".review") as f:
            return [json.loads(x) for x in f]

    def test_shadow_review_sees_no_item_text_and_lands_in_body_and_record(self):
        self.gh_state({1: {"body": "RAW-ISSUE-TEXT"}, 2: {"body": "RAW-ISSUE-TEXT"}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b", "review": "looks fine"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.reviews(), [{"raw": False, "top": ["input", "repo"]}] * 2)
        [call] = {c for c in self.calls() if "--model" in c and "--tools Read,Grep,Glob" in c and "--restricted" in c}
        self.assertIn("--model sonnet", call)
        bodies = {p["head"]: p["body"] for p in self.gh()["prs"]}
        self.assertIn("## Shadow review\n\nAdvisory; nothing merges on it.\n\n- claude:sonnet (same family): approve\n\n"
                      "    - src/1:1: nit\n", bodies["factory/fix-1"])
        self.assertIn("- claude:sonnet (same family): changes (invalid output)\n", bodies["factory/fix-2"])
        self.assertNotIn("looks fine", bodies["factory/fix-2"])
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            [rec] = [json.loads(x) for x in f]
        self.assertEqual([(i["id"], i["scope"], i["weighted_lines"], i["reviews"]) for i in rec["items"]], [
            ("1", "minimal", 1, [{"model": "claude:sonnet", "family": "same family", "verdict": "approve", "valid": True}]),
            ("2", "minimal", 1, [{"model": "claude:sonnet", "family": "same family", "verdict": "changes", "valid": False}])])

    def test_shadow_review_in_dry_run_writes_nothing(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}}, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 review: claude:sonnet approve", r.stdout)
        self.assertEqual(self.remote_heads() + "".join(self.gh_writes()), "")
        self.assertEqual(self.rows("pushed.tsv") + self.rows("linked.tsv"), [])

    def merge_calls(self):
        return [c for c in self.calls() if c.startswith("gh pr merge")]

    def test_default_draft_marks_nothing_ready_and_records_no_merge(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ready", self.gh())
        self.assertEqual(self.rows("merges.tsv") + self.merge_calls(), [])
        self.assertTrue(self.gh()["comments"][0]["body"].startswith("Draft PR "))

    def test_ready_marks_ready_only_when_every_reviewer_approves(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b", "review-opus": "review: verdict=changes"}},
                              merge_level="ready", reviewers="claude:sonnet claude:opus")
        self.assertEqual(r.returncode, 0, r.stderr)
        url = {p["head"]: p["url"] for p in self.gh()["prs"]}
        self.assertEqual(self.gh()["ready"], [url["factory/fix-1"]])
        self.assertEqual(self.rows("merges.tsv") + self.merge_calls(), [])
        bodies = {c["issue"]: c["body"] for c in self.gh()["comments"]}
        self.assertTrue(bodies["1"].startswith(f"PR {url['factory/fix-1']}: "))
        self.assertTrue(bodies["2"].startswith("Draft PR "))

    def test_merge_level_approves_only_without_needs_human_disclosure_and_never_merges_in_the_same_run(self):
        for needs_human, approved in ((None, "1"), ("dependency refactor", "13")):
            with self.subTest(needs_human=needs_human):
                self.setUp()
                self.gh_state({1: {}, 2: {}, 3: {}}, [])
                r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b", "review-opus": "x"},
                                       "3": {"feature": "c", "edit_test": True}},
                                      merge_level="merge", reviewers="claude:sonnet claude:opus", needs_human=needs_human)
                self.assertEqual(r.returncode, 0, r.stderr)
                prs = {p["head"]: p for p in self.gh()["prs"]}
                urls = [prs[f"factory/fix-{i}"]["url"] for i in approved]
                self.assertEqual(self.gh()["ready"], urls)
                heads = [self.git("--git-dir", self.remote, "rev-parse", f"factory/fix-{i}").strip() for i in approved]
                self.assertEqual(self.rows("merges.tsv"), [f"{i} approved {u} {h} issue-pipeline claude:sonnet=approve,claude:opus=approve, "
                                                           f"{int(i == '3')} 0 minimal {1 + int(i == '3')}" for i, u, h in zip(approved, urls, heads)])
                self.assertIn("then squash-merged by a later run once CI is green on", prs["factory/fix-1"]["body"])
                self.assertEqual(self.merge_calls(), [])
                self.tearDown()

    def test_agent_instruction_change_is_never_marked_ready_or_approved_for_merge(self):
        self.gh_state({1: {}, 2: {}, 3: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "instructions": "AGENTS.md"},
                               "2": {"feature": "b", "instructions": ".claude/skills/s/SKILL.md"}, "3": {"feature": "c"}},
                              merge_level="merge", reviewers="claude:sonnet claude:opus", needs_human="")
        self.assertEqual(r.returncode, 0, r.stderr)
        prs = {p["head"]: p for p in self.gh()["prs"]}
        self.assertEqual(self.gh()["ready"], [prs["factory/fix-3"]["url"]])
        self.assertEqual([x.split()[0] for x in self.rows("merges.tsv")], ["3"])
        for i, path in (("1", "AGENTS.md"), ("2", ".claude/skills/s/SKILL.md")):
            pr = prs[f"factory/fix-{i}"]
            self.assertTrue(pr["draft"])
            self.assertTrue(pr["body"].startswith("## Changes agent instructions\n\nNeeds human review"))
            self.assertIn(f"- {path}\n", pr["body"])
            self.assertIn(f"gh pr edit {pr['url']} --repo o/r --add-label factory:instructions", self.calls())
        self.assertNotIn(f"gh pr edit {prs['factory/fix-3']['url']} --repo o/r --add-label factory:instructions", self.calls())
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            rec = json.loads(f.read().splitlines()[-1])
        self.assertEqual([(i["id"], i["instruction_change"]) for i in rec["items"]], [("1", True), ("2", True), ("3", False)])
        self.assertEqual(self.merge_calls(), [])

    def test_pending_merge_that_changes_agent_instructions_is_left(self):
        url, sha = "https://github.com/o/r/pull/1", "a" * 40
        self.main_commit("skills/own/SKILL.md", "skill")
        for files, after in ((["src/1", "AGENTS.md"], "left"), ([".claude/skills/s/x.md"], "left"),
                             (["skills/own/ref.md"], "left"), (["src/1"], "merged")):
            with self.subTest(files):
                self.land([f"1 approved {url} {sha}{OK}"], {url: {"state": "OPEN", "head": sha, "files": files}},
                          {sha: "SUCCESS"}, merge_level="merge", reviewers="claude:sonnet claude:opus", needs_human="")
                self.assertEqual(self.rows("merges.tsv")[-1].split()[1], after)
                self.assertEqual(len(self.merge_calls()), int(after == "merged"))
                if after == "left":
                    self.assertIn(f"land: 1 {url} not merged: changes agent instructions; needs a human.", self.report())

    def test_merge_level_needs_two_reviewers_and_known_settings_before_any_write(self):
        for kw, msg in (({"merge_level": "merge"}, "merge_level merge needs at least 2 reviewers"),
                        ({"merge_level": "<merge level>"}, "merge_level <merge level> is not draft, ready or merge"),
                        ({"merge_level": "auto"}, "merge_level auto is not draft, ready or merge"),
                        ({"needs_human": "tests"}, "needs_human tests is not test-change, dependency or refactor")):
            with self.subTest(msg):
                self.gh_state({1: {}}, [])
                r = self.run_pipeline({"1": {}}, **kw)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual(self.stage_calls() + self.gh_writes(), [])
                self.assertFalse(os.path.exists(self.fx))

    def test_pending_merge_rechecks_its_entry_and_current_reviewers_and_needs_human(self):
        url, sha = "https://github.com/o/r/pull/1", "a" * 40
        for name, row, kw, after in (
                ("reviewer added", OK, {"reviewers": "claude:sonnet claude:opus claude:haiku"}, "left"),
                ("needs_human widened", OK.replace(" 0 0 ", " 1 0 "), {}, "left"),
                ("needs_human narrowed", OK.replace(" 0 0 ", " 1 0 "), {"needs_human": "dependency"}, "merged"),
                ("other entry", OK.replace("issue-pipeline", "other"), {}, "approved")):
            with self.subTest(name):
                self.land([f"1 approved {url} {sha}{row}"], {url: {"state": "OPEN", "head": sha}}, {sha: "SUCCESS"},
                          **dict({"merge_level": "merge", "reviewers": "claude:sonnet claude:opus"}, **kw))
                self.assertEqual(self.rows("merges.tsv")[-1].split()[1], after)
                self.assertEqual(len(self.merge_calls()), int(after == "merged"))
                if after == "left":
                    self.assertIn("not merged: reviewers or needs_human changed since review", self.report())

    def test_unknown_merge_commit_is_looked_up_again_then_escalated(self):
        url = "https://github.com/o/r/pull/2"
        m = self.main_commit("src/two", "fix: #2 b (#2)")
        self.push_main()
        self.land([f"2 merged {url} -"], {url: {"state": "MERGED", "merge": m}}, {m: "FAILURE"})
        self.assertEqual(self.rows("merges.tsv")[1:], [f"2 merged {url} {m}", f"2 reverted {url} {m}"])
        self.assertEqual([p["head"] for p in self.gh()["prs"]], ["factory/revert-2"])
        for _ in range(6):
            self.land([f"2 merged {url} -"], {url: {"state": "OPEN"}})
            self.assertEqual(self.rows("merges.tsv"), [f"2 merged {url} -"])
        self.land([f"2 merged {url} -"] * 5, {})
        self.assertEqual(self.rows("merges.tsv")[5:], [f"2 merged {url} -"])
        self.assertIn(f"land: 2 {url} merge commit lookup failed 5 times: check CI on main; needs a human.", self.report())
        self.land([f"2 merged {url} -"] * 9, {url: {"state": "MERGED", "merge": m}}, {m: "FAILURE"})
        self.assertEqual(self.rows("merges.tsv")[9:], [f"2 merged {url} {m}", f"2 reverted {url} {m}"])

    def test_merge_commit_lookup_escalates_at_the_fifth_failed_lookup_not_before(self):
        url = "https://github.com/o/r/pull/2"
        for earlier, says in ((4, False), (5, True)):
            with self.subTest(earlier=earlier):
                self.land([f"2 merged {url} -"] * earlier, {})
                self.assertEqual("merge commit lookup failed 5 times" in self.report(), says)

    def test_pending_merge_closed_unmerged_leaves_polling_with_one_line(self):
        url = "https://github.com/o/r/pull/2"
        self.land([f"2 merged {url} -"], {url: {"state": "CLOSED"}})
        self.assertEqual(self.rows("merges.tsv"), [f"2 merged {url} -", f"2 closed {url} -"])
        self.assertEqual(self.report().count(f"land: 2 {url} closed without merging; no longer watched.\n"), 1)
        self.land(self.rows("merges.tsv"), {url: {"state": "CLOSED"}})
        self.assertEqual([c for c in self.calls() if c.startswith("gh pr view")], [])
        self.assertNotIn("closed without merging", self.report())

    def test_revert_waits_for_a_run_with_time_for_its_tests(self):
        url = "https://github.com/o/r/pull/2"
        m = self.main_commit("src/two", "fix: #2 b (#2)")
        self.push_main()
        self.land([f"2 merged {url} {m}"], {}, {m: "FAILURE"}, run_minutes="1")
        self.assertEqual((self.gh()["prs"], self.rows("merges.tsv")), ([], [f"2 merged {url} {m}"]))
        self.assertIn(f"land: 2 {url} revert waits for a run with time for its tests.", self.report())

    def test_refactor_test_runs_wait_for_run_time(self):
        r = self.run_pipeline({}, main="run_minutes=1 refactors=(abc); refactor_tests; echo ran\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ran", r.stdout)

    def test_added_test_run_on_base_waits_for_run_time(self):
        self.git("-C", self.repo, "checkout", "-qb", "t")
        sha = self.main_commit("tests/new_test.sh", "t")
        self.git("-C", self.repo, "checkout", "-q", "main")
        r = self.run_pipeline({}, main=f'run_minutes=1 commit={sha} item=$view outcome=""\n'
                              'start=$(git rev-parse main); red_green; echo ran\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ran", r.stdout)
        self.assertFalse(any("red" in n for n in os.listdir(f"{self.repo}/.factory/tmp")))

    def test_reviewers_must_be_valid_claude_picks_before_any_call(self):
        for reviewers, msg in (('"claude:haiku sonnet"', "model claude:haiku sonnet is not <cli>:<model>[@effort]"),
                               ("sonnet", "model sonnet is not <cli>:<model>[@effort]"),
                               ("claude:sonnet codex:gpt-6.1-sol", "model codex:gpt-6.1-sol: CLI codex is not supported yet, only claude")):
            with self.subTest(reviewers):
                self.gh_state({1: {}}, [])
                r = self.run_pipeline({"1": {}}, reviewers=reviewers)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual(self.calls(), [])

    def test_per_stage_models_reach_each_stage_call_and_the_record(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}}, models="[default]=claude:haiku [fix]=claude:opus@high [verify]=claude:default@low",
                              reviewers="claude:sonnet@max claude:haiku")
        self.assertEqual(r.returncode, 0, r.stderr)
        seen = []
        for c in self.prompts():
            ev, args = c["evidence"], c["args"]
            n = ev.rsplit("/", 1)[1] if ev else "spec" if args[args.index("--tools") + 1] == "" else \
                "review" if c["prompt"].startswith("Review the change") else "analyze"
            seen.append((n, " ".join(re.findall(r"--(?:model|effort) \S+", " ".join(args)))))
        self.assertEqual(seen, [("analyze", "--model haiku"), ("spec", "--model haiku"), ("reproduce", "--model haiku"),
                                ("fix", "--model opus --effort high"), ("verify", "--effort low"),
                                ("review", "--model sonnet --effort max"), ("review", "--model haiku")])
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            [rec] = [json.loads(x) for x in f]
        self.assertEqual([(s["stage"], s["model"], s["effort"], s["isolation"]) for s in rec["stages"]], [
            ("analyze", "haiku", None, "restricted"), ("spec", "haiku", None, "restricted"),
            ("reproduce", "haiku", None, "environment"), ("fix", "opus", "high", "environment"),
            ("verify", "default", "low", "environment"), ("review", "sonnet", "max", "restricted"),
            ("review", "haiku", None, "restricted")])
        self.assertEqual([i["reviews"] for i in rec["items"]][0][0]["model"], "claude:sonnet@max")

    def land(self, merges, pulls, ci=None, fail=(), **kw):
        os.makedirs(self.fx, exist_ok=True)
        with open(f"{self.fx}/merges.tsv", "w") as f:
            f.write("".join(m + "\n" for m in merges))
        self.gh_state({}, list(fail), pulls=pulls, ci=ci or {}, merge_sha="b" * 40)
        r = self.run_pipeline({}, report_extra="No new issues\n", **kw)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def test_merge_runs_only_when_every_condition_holds(self):
        url, sha = "https://github.com/o/r/pull/1", "a" * 40
        ok = {"state": "OPEN", "head": sha}
        for name, pull, ci, fail, kw, row in (
                ("all hold", {}, "SUCCESS", (), {}, "merged"),
                ("closed", {"state": "CLOSED"}, "SUCCESS", (), {}, "left"),
                ("merged by a human", {"state": "MERGED"}, "SUCCESS", (), {}, "left"),
                ("back in draft", {"draft": True}, "SUCCESS", (), {}, "left"),
                ("head moved", {"head": "c" * 40}, "SUCCESS", (), {}, "left"),
                ("a revert branch", {"branch": "factory/revert-1"}, "SUCCESS", (), {}, "left"),
                ("a fork", {"cross": True}, "SUCCESS", (), {}, "left"),
                ("other base", {"base": "dev"}, "SUCCESS", (), {}, "left"),
                ("conflicting", {"mergeable": "CONFLICTING"}, "SUCCESS", (), {}, "left"),
                ("mergeable unknown", {"mergeable": "UNKNOWN"}, "SUCCESS", (), {}, "approved"),
                ("CI red", {}, "FAILURE", (), {}, "left"),
                ("CI pending", {}, "PENDING", (), {}, "approved"),
                ("CI none", {}, "", (), {}, "approved"),
                ("level lowered", {}, "SUCCESS", (), {"merge_level": "ready"}, "approved"),
                ("merge refused", {}, "SUCCESS", ("pr merge",), {}, "left")):
            with self.subTest(name):
                self.land([f"1 approved {url} {sha}{OK}"], {url: dict(ok, **pull)}, {sha: ci}, fail,
                          **dict({"merge_level": "merge", "reviewers": "claude:sonnet claude:opus"}, **kw))
                calls = self.merge_calls()
                self.assertEqual(calls, [f"gh pr merge {url} --repo o/r --squash --match-head-commit {sha}"]
                                 if name in ("all hold", "merge refused") else [])
                self.assertEqual(self.rows("merges.tsv")[-1].split()[1], row)
                if row == "merged":
                    self.assertEqual(self.rows("merges.tsv")[-1], f"1 merged {url} {'b' * 40}")
                    self.assertIn(f"land: 1 {url} merged as {'b' * 40}", self.report())
                if row == "left":
                    self.assertIn(f"land: 1 {url} not merged: ", self.report())

    def test_pause_stops_a_pending_merge(self):
        url, sha = "https://github.com/o/r/pull/1", "a" * 40
        self.write(".factory/pause", "")
        self.land([f"1 approved {url} {sha}{OK}"], {url: {"state": "OPEN", "head": sha}}, {sha: "SUCCESS"},
                  merge_level="merge", reviewers="claude:sonnet claude:opus")
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.rows("merges.tsv"), [f"1 approved {url} {sha}{OK}"])

    def main_commit(self, path, msg):
        self.write(path, "x\n")
        self.git("-C", self.repo, "add", path)
        self.git("-C", self.repo, "commit", "-qm", msg)
        return self.git("-C", self.repo, "rev-parse", "HEAD").strip()

    def test_red_main_after_a_factory_merge_opens_a_draft_revert_and_escalates(self):
        u1, u2 = "https://github.com/o/r/pull/1", "https://github.com/o/r/pull/2"
        m1, m2 = self.main_commit("src/one", "fix: #1 a (#1)"), self.main_commit("src/two", "fix: #2 b (#2)")
        self.push_main()
        self.land([f"1 merged {u1} {m1}", f"2 merged {u2} {m2}"], {}, {m1: "SUCCESS", m2: "FAILURE"})
        [pr] = self.gh()["prs"]
        self.assertEqual((pr["head"], pr["draft"], pr["title"]), ("factory/revert-2", True, f"revert: #2 factory merge {m2[:12]}"))
        self.assertIn(f"Reverts the factory merge {m2} of {u2}", pr["body"])
        tip = self.git("--git-dir", self.remote, "rev-parse", "factory/revert-2").strip()
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", f"{tip}^").strip(), m2)
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", f"{tip}^{{tree}}").strip(),
                         self.git("-C", self.repo, "rev-parse", f"{m1}^{{tree}}").strip())
        self.assertEqual(sorted(self.rows("merges.tsv")[2:]), [f"1 green {u1} {m1}", f"2 reverted {u2} {m2}"])
        self.assertIn(f"escalated: main-red: CI failed on main for the factory merge {m2} of {u2}; revert PR {pr['url']}; "
                      "needs a human.", self.report())
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            rec = json.loads(f.read().splitlines()[-1])
        self.assertEqual([(i["id"], i["outcome"], i["reason"], i["pr"]) for i in rec["items"]],
                         [("revert-2", "escalated", "main-red", pr["url"])])
        self.assertEqual(self.merge_calls(), [])
        self.git("-C", self.repo, "checkout", "-q", "main")
        r = self.run_pipeline({}, report_extra="No new issues\n", merge_level="merge", reviewers="claude:sonnet claude:opus")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(self.gh()["prs"]), self.merge_calls()), (1, []))

    def test_revert_pr_that_failed_to_open_is_opened_by_a_later_run(self):
        url = "https://github.com/o/r/pull/2"
        m = self.main_commit("src/two", "fix: #2 b (#2)")
        self.push_main()
        for _ in range(2):
            self.land(self.rows("merges.tsv") or [f"2 merged {url} {m}"], {}, {m: "FAILURE"}, fail=["pr create"])
            self.assertEqual((self.gh()["prs"], self.rows("merges.tsv")), ([], [f"2 merged {url} {m}"]))
            self.assertIn(f"land: 2 {url} revert pushed to factory/revert-2, PR not opened", self.report())
        tip = self.git("--git-dir", self.remote, "rev-parse", "factory/revert-2").strip()
        self.land(self.rows("merges.tsv"), {}, {m: "FAILURE"})
        [pr] = self.gh()["prs"]
        self.assertEqual((pr["head"], pr["draft"]), ("factory/revert-2", True))
        self.assertIn(f"Reverts the factory merge {m} of {url}", pr["body"])
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", "factory/revert-2").strip(), tip)
        self.assertEqual(self.rows("merges.tsv")[1:], [f"2 reverted {url} {m}"])
        self.assertIn(f"revert PR {pr['url']}; needs a human.", self.report())
        r = self.run_pipeline({}, report_extra="No new issues\n", merge_level="merge", reviewers="claude:sonnet claude:opus")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(self.gh()["prs"]), self.merge_calls(), self.pr_creates()), (1, [], []))

    def test_revert_branch_nobody_recorded_is_not_given_a_pr(self):
        url = "https://github.com/o/r/pull/2"
        m = self.main_commit("src/two", "fix: #2 b (#2)")
        self.push_main()
        self.git("-C", self.repo, "push", "-q", self.remote, "main:refs/heads/factory/revert-2")
        self.land([f"2 merged {url} {m}"], {}, {m: "FAILURE"})
        self.assertEqual(self.gh()["prs"], [])
        self.assertIn("revert PR none; needs a human.", self.report())

    def test_pr_fates_feed_agreement_metrics(self):
        m1 = self.main_commit("src/one", "fix: #1 a (#1)")
        m2 = self.main_commit("src/two", "fix: #2 b (#2)")
        m4 = self.main_commit("src/four", "fix: #4 d (#4)")
        m6 = self.main_commit("src/six", "fix: #6 f (#6)")
        self.git("-C", self.repo, "revert", "--no-edit", m1)
        self.push_main()
        u = {i: f"https://github.com/o/r/pull/{i}" for i in "123456"}
        pulls = {u["1"]: {"state": "MERGED", "merge": m1, "title": "fix: #1 a"},
                 u["2"]: {"state": "MERGED", "merge": m2, "changes": 1},
                 u["3"]: {"state": "CLOSED"}, u["4"]: {"state": "MERGED", "merge": m4},
                 u["5"]: {"state": "OPEN"}, u["6"]: {"state": "MERGED", "merge": m6}}
        os.makedirs(self.fx)
        with open(f"{self.fx}/linked.tsv", "w") as f:
            f.write("".join(f"{i} {u[i]}\n" for i in "123456") + "7 abc123\n")
        approve = [{"model": "sonnet", "family": "same family", "verdict": "approve", "valid": True}]
        items = [{"id": i, "pr": u[i], "scope": "refactor" if i == "3" else "minimal",
                  "reviews": [dict(approve[0], verdict="changes")] if i == "3" else approve} for i in "123456"]
        os.makedirs(f"{self.repo}/.factory/reports", exist_ok=True)
        with open(f"{self.repo}/.factory/reports/runs.jsonl", "w") as f:
            f.write(json.dumps({"entry": "issue-pipeline", "started": "2026-11-01T00:00:00Z", "outcome": "completed",
                                "items": items}) + "\n")
        self.land([f"4 merged {u['4']} {m4}"], pulls)
        rows = {r.split()[0]: r.split()[1:4] for r in self.rows("fates.tsv")}
        self.assertEqual({k[-1]: v for k, v in rows.items()}, {
            "1": ["reverted", "0", m1], "2": ["merged", "1", m2], "3": ["closed", "0", "-"],
            "4": ["factory-merged", "0", m4], "5": ["open", "0", "-"], "6": ["merged", "0", m6]})
        n = len(self.rows("fates.tsv"))
        self.run_pipeline({}, report_extra="No new issues\n")
        self.assertEqual(len(self.rows("fates.tsv")), n)
        self.assertEqual(len([c for c in self.calls() if c.startswith("gh pr view")]), 1)
        report = "\n".join(agent_analytics.render_runs(agent_analytics.factory_runs(self.repo, None)))
        self.assertIn("Review: approved 5 of 6 reviewed PRs; human outcome known for 4, agreeing 2; misses 1 "
                      "(approved, then closed or reverted). Merged of resolved PRs: minimal 3 of 4, refactor 0 of 1.",
                      report)

    def test_merge_and_fate_state_must_be_regular_files(self):
        for name in ("merges.tsv", "fates.tsv"):
            with self.subTest(name):
                os.makedirs(f"{self.fx}/{name}")
                self.gh_state({1: {}}, [])
                r = self.run_pipeline({"1": {}})
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f"{name} is a symlink or not a regular file", r.stderr)
                self.assertEqual(self.stage_calls() + self.gh_writes(), [])
                os.rmdir(f"{self.fx}/{name}")

    def test_every_ledger_must_be_a_regular_file(self):
        for name in ("pushed.tsv", "linked.tsv", "tickets.tsv", "merges.tsv", "fates.tsv"):
            with self.subTest(name):
                os.makedirs(f"{self.fx}/{name}")
                self.gh_state({1: {}}, [])
                r = self.run_pipeline({"1": {}})
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f"{name} is a symlink or not a regular file", r.stderr)
                self.assertEqual(self.stage_calls() + self.gh_writes(), [])
                os.rmdir(f"{self.fx}/{name}")

    def test_ledger_broken_during_an_item_stops_its_push_and_defers_the_rest(self):
        self.write("tests/ledger_test.sh", "mkdir -p ../../../pushed.tsv\n")
        self.git("-C", self.repo, "add", "tests")
        self.git("-C", self.repo, "commit", "-qm", "test")
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a"}, "2": {"feature": "b"}})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fix-issues/pushed.tsv is a symlink or not a regular file", r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("blocked", "publish"))
        self.assertEqual(self.outcome("2"), ("deferred", "ledger", "none"))
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.stage_calls("2") + self.gh_writes(), [])

    def test_stage_prompts_name_the_stage_and_keep_fix_rules_to_the_fix_stage(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        seen = {c["evidence"].rsplit("/", 1)[1]: c["prompt"] for c in self.prompts() if c["evidence"]}
        self.assertEqual(sorted(seen), ["fix", "reproduce", "verify"])
        for n, prompt in seen.items():
            with self.subTest(n):
                self.assertIn("do only the part for the stage named on the last line.", prompt)
                self.assertTrue(prompt.endswith(f"Stage: {n}."))
                self.assertEqual("In fix.md" in prompt, n == "fix")
                self.assertEqual("dependency: <name> <why not in-house>." in prompt, n == "fix")

    STAGE_SKILLS = "[reproduce]=my-repro [fix]=my-fix [verify]=my-verify [review]=my-review"

    def user_skills(self):
        for name in ("my-repro", "my-fix", "my-verify", "my-review", "house"):
            self.write(f".claude/skills/{name}/SKILL.md", f"{name} steps\n")
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "user skills")
        return " ".join(f'".claude/skills/{n}"' for n in ("my-repro", "my-fix", "my-verify", "my-review", "house"))

    def test_replaced_stages_follow_the_user_skill_and_carry_the_record_contract(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}}, skills=self.user_skills(), stage_skills=self.STAGE_SKILLS,
                              extra_skills="house")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[0], "fixed")
        records = {"reproduce": ("repro.md", "repro: outcome=reproduced", "repro: outcome=not-reproduced",
                                 "repro: outcome=blocked"),
                   "fix": ("fix.md", "fix: outcome=changed", "fix: outcome=stopped"),
                   "verify": ("verify.md", "verify: outcome=confirmed", "verify: outcome=insufficient",
                              "verify: outcome=inconclusive")}
        seen = {c["evidence"].rsplit("/", 1)[1]: c for c in self.prompts() if c["evidence"]}
        self.assertEqual(sorted(seen), ["fix", "reproduce", "verify"])
        for n, c in seen.items():
            with self.subTest(n):
                check, prompt = c["evidence"].replace("/evidence/", "/check/"), c["prompt"]
                skill = {"reproduce": "my-repro"}.get(n, "my-" + n)
                self.assertTrue(prompt.startswith(f"Follow {check}/skills/{skill}/SKILL.md for this stage;"))
                self.assertEqual(c["skills"], sorted([skill, "house"]))
                self.assertNotIn("# Reproduce", prompt)
                self.assertNotIn("# Fix and verify", prompt)
                f, *lines = records[n]
                self.assertIn(f"Write {c['evidence']}/{f}:", prompt)
                for line in lines:
                    self.assertIn(line, prompt)
                self.assertIn(f"Also follow {check}/skills/house/SKILL.md where it applies.", prompt)
                self.assertIn("end your record with escalated:", prompt)
                self.assertTrue(prompt.endswith(f"Stage: {n}."))
        [review] = [c["prompt"] for c in self.prompts() if not c["evidence"] and "--model" in c["args"]]
        self.assertIn("Judge it by skills/my-review/SKILL.md.\nAlso follow skills/house/SKILL.md where it applies.", review)
        self.assertNotIn("Judge whether it fixes", review)
        self.assertIn("Last line review: verdict=approve\nor review: verdict=changes.", review)
        self.assertEqual(self.reviews(), [{"raw": False, "top": ["input", "repo", "skills"]}])
        [pr] = self.gh()["prs"]
        for h in SPEC_HEADINGS:
            self.assertIn(h, pr["body"])

    def test_built_in_stages_carry_the_same_record_contract(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        for c in self.prompts():
            if c["evidence"]:
                n = c["evidence"].rsplit("/", 1)[1]
                with self.subTest(n):
                    self.assertTrue(c["prompt"].startswith("# "))
                    self.assertIn(f"Write {c['evidence']}/{dict(reproduce='repro').get(n, n)}.md:", c["prompt"])
                    self.assertEqual(c["skills"], [])
        [review] = [c["prompt"] for c in self.prompts() if not c["evidence"] and "--model" in c["args"]]
        self.assertIn("Judge whether it fixes", review)

    def test_every_record_rule_keeps_escalation_and_defines_its_outcomes(self):
        skills = self.user_skills()
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}}, skills=skills, stage_skills="[verify]=my-verify")
        self.assertEqual(r.returncode, 0, r.stderr)
        esc = "end instead with escalated: <credentials|prod-access|ambiguous|out-of-scope> in place of the outcome line"
        seen = {c["evidence"].rsplit("/", 1)[1]: c["prompt"] for c in self.prompts() if c["evidence"]}
        self.assertEqual(sorted(seen), ["fix", "reproduce", "verify"])
        for n, prompt in seen.items():
            with self.subTest(n):
                rule = prompt[prompt.index(f"/evidence/{n}/"):]
                self.assertIn(esc, rule)
        self.assertIn("Mode: this run's fix;", seen["verify"])
        for o in ("confirmed (broken twice on base/", "insufficient (broken on both)", "inconclusive (base/ did not reproduce"):
            self.assertIn("verify: outcome=" + o, seen["verify"])
        self.gh_state({2: {}}, [])
        r = self.run_pipeline({"2": {"escalate": "verify"}}, skills=skills, stage_skills="[verify]=my-verify")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("2")[:2], ("escalated", "prod-access"))

    def test_a_replaced_verify_is_told_it_checks_an_existing_fix(self):
        skills = self.user_skills()
        sha = self.fix_commit()
        self.push_main()
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"verdict": "fixed", "ref": sha[:7]}}, skills=skills, stage_skills="[verify]=my-verify")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("fixed", "linked"))
        [prompt] = [c["prompt"] for c in self.prompts() if c["evidence"]]
        self.assertTrue(prompt.startswith("Follow "))
        self.assertIn("Mode: an existing merged fix;", prompt)
        self.assertNotIn("Mode: this run's fix;", prompt)

    def test_a_replaced_stage_without_its_record_line_fails_the_gate(self):
        self.gh_state({1: {}, 2: {}}, [])
        r = self.run_pipeline({"1": {"feature": "a", "norecord": "reproduce"}, "2": {"feature": "b", "norecord": "fix"}},
                              skills=self.user_skills(), stage_skills=self.STAGE_SKILLS)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("blocked", "reproduce"))
        self.assertEqual(self.outcome("2")[:2], ("blocked", "fix"))
        self.assertEqual(self.stage_calls("1", "fix"), [])
        self.assertEqual(self.stage_calls("2", "verify"), [])
        self.assertEqual(self.pr_creates(), [])
        self.assertEqual(self.remote_heads(), "")

    def test_an_in_repo_stage_skill_is_consumed_and_denied(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"instructions": ".claude/skills/my-fix/SKILL.md"}},
                              skills=self.user_skills(), stage_skills="[fix]=my-fix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gate: CI, hook or policy path .claude/skills/my-fix/SKILL.md", r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("blocked", "gates"))
        self.assertEqual(self.pr_creates(), [])
        self.assertEqual(self.remote_heads(), "")

    def test_only_the_four_stages_take_a_skill_and_only_one_in_skills(self):
        skills = self.user_skills()
        for kw, msg in ((dict(stage_skills="[gates]=my-fix"), "stage_skills: gates is not reproduce, fix, verify or review"),
                        (dict(stage_skills="[spec]=my-fix"), "stage_skills: spec is not"),
                        (dict(stage_skills="[fix]=elsewhere"), "skill elsewhere is not a skill in skills"),
                        (dict(extra_skills="../my-fix"), "skill ../my-fix is not a skill in skills")):
            with self.subTest(kw):
                self.gh_state({1: {}}, [])
                r = self.run_pipeline({"1": {}}, skills=skills, **kw)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual([c for c in self.calls() if c.startswith("claude ")], [])

    def test_triage_prompts_carry_the_record_contract_outside_judge(self):
        line = ("fix-issues: id=<id> verdict=<new-bug|fixed|duplicate|related|owned|not-a-bug|needs-info> "
                "feature=<feature file name without .md, or none> ref=<#number, short SHA, item id, or none>")
        catalog = os.path.join(HERE, "..", "references", "catalog")
        for path, head in ((TRIAGE, "## Analyze"), (f"{catalog}/issue-pipeline.md", "## Prompt"),
                           (f"{catalog}/new-error-triage.md", "## Prompt")):
            with self.subTest(path), open(path) as f:
                prompt = re.search(r"```text\n(.*?)```", f.read().split(head + "\n", 1)[1], re.S)[1]
                self.assertRegex(prompt, r"section\s+headed\s+## <id>")
                self.assertIn(line + "\n", prompt)
        with open(TRIAGE) as f:
            judge = f.read().split("## Judge\n", 1)[1].split("## Projection", 1)[0]
        self.assertNotIn("fix-issues: id=", judge)

    def test_reproduce_blocked_is_recorded_as_such(self):
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"repro": "blocked"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("blocked", "repro-blocked", "none"))
        self.assertIn("1 repro: outcome=blocked", r.stdout)
        self.assertEqual(self.stage_calls("1", "fix") + self.gh_writes(), [])

    def test_reproduced_item_blocked_before_push_comments_the_reproduction_once(self):
        self.gh_state({1: {}, 2: {}}, [])
        items = {"1": {"feature": "a", "verify": "insufficient"}, "2": {"feature": "b", "deny": True}}
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.outcome(i)[:2] for i in "12"], [("blocked", "verify"), ("blocked", "gates")])
        start = self.git("-C", self.repo, "rev-parse", "main").strip()
        comments = self.gh()["comments"]
        self.assertEqual([c["issue"] for c in comments], ["1", "2"])
        for c, step in zip(comments, ("verify", "gates")):
            self.assertTrue(c["body"].startswith(f"Reproduced on {start} by a scheduled run. The automated fix stopped "
                                                 f"at {step} and nothing was pushed; needs a human.\n"))
            self.assertIn("repro: outcome=reproduced", c["body"])
            self.assertNotIn("root cause", c["body"])
        self.assertEqual(self.gh_writes(), [c for c in self.calls() if c.startswith("gh issue comment")])
        self.assertEqual(self.rows("linked.tsv"), [f"1 {start}", f"2 {start}"])
        self.assertEqual(self.remote_heads() + "".join(self.rows("pushed.tsv")), "")
        self.assertFalse(os.path.exists(f"{self.fx}/tmp/fix-1"))
        r = self.run_pipeline({"3": {"feature": "c", "verify": "insufficient"}}, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.gh()["comments"]), 2)

    def fix_commit(self, branch=None):
        if branch:
            self.git("-C", self.repo, "checkout", "-qb", branch)
        self.write(f"src/{branch or 'fix'}", "fixed\n")
        self.git("-C", self.repo, "add", "src")
        self.git("-C", self.repo, "commit", "-qm", "fix")
        sha = self.git("-C", self.repo, "rev-parse", "HEAD").strip()
        if branch:
            self.git("-C", self.repo, "checkout", "-q", "main")
        return sha

    def merge(self, branch):
        self.git("-C", self.repo, "merge", "-q", "--no-ff", "-m", "merge", branch)
        return self.git("-C", self.repo, "rev-parse", "HEAD").strip()

    def push_main(self):
        self.git("-C", self.repo, "push", "-q", self.remote, "main")

    def test_fixed_merged_commit_verified_comments_once(self):
        sha = self.fix_commit()
        parent = self.git("-C", self.repo, "rev-parse", "HEAD^").strip()
        self.push_main()
        self.gh_state({1: {}}, [])
        items = {"1": {"verdict": "fixed", "ref": sha[:7]}}
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("fixed", "linked", "none"))
        self.assertEqual(len(self.spec_calls()), 1)
        self.assertEqual(len(self.stage_calls("1", "verify")), 1)
        self.assertEqual(len(self.stage_calls()), 1)
        comments = self.gh()["comments"]
        self.assertEqual([c["issue"] for c in comments], ["1"])
        body = comments[0]["body"]
        self.assertTrue(body.startswith(f"Verified: the merged fix {sha[:7]} ({sha}) resolves this; "
                                        f"its parent {parent} showed"))
        self.assertIn("## Spec\n\nfeature: a\n", body)
        self.assertIn("verify: outcome=confirmed", body)
        self.assertEqual(self.rows("linked.tsv"), [f"1 {sha}"])
        self.assertEqual(self.rows("pushed.tsv"), [])
        self.assertEqual(self.remote_heads().split(), ["refs/heads/main"])
        self.assertEqual(self.pr_creates(), [])
        self.assertEqual(self.gh_writes(), [c for c in self.calls() if c.startswith("gh issue comment")])
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("skipped", "linked"))
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        self.assertEqual(len(self.gh()["comments"]), 1)

    def test_fixed_merged_pr_not_confirmed_comments_and_stops(self):
        self.fix_commit("feat")
        merge = self.merge("feat")
        self.push_main()
        self.gh_state({1: {}}, [], pulls={"12": {"state": "MERGED", "merge": merge, "commits": 2}})
        items = {"1": {"verdict": "fixed", "ref": "#12", "verify": "insufficient"}}
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[:2], ("blocked", "not-confirmed"))
        comments = self.gh()["comments"]
        self.assertEqual(len(comments), 1)
        self.assertTrue(comments[0]["body"].startswith(f"Not confirmed: the merged fix #12 ({merge})"))
        self.assertIn("verify: outcome=insufficient", comments[0]["body"])
        self.assertEqual(self.rows("linked.tsv"), [f"1 {merge}"])
        self.assertEqual(self.gh()["issues"].keys(), {"1"})
        self.assertEqual(self.pr_creates(), [])
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        os.rename(f"{self.out}/{datetime.date.today()}.md", f"{self.out}/{yesterday}.md")
        r = self.run_pipeline(items)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pipeline: no candidates", self.report())
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])

    def test_fixed_refs_that_do_not_qualify_start_no_stage(self):
        side = self.fix_commit("side")
        self.fix_commit("feat")
        merge = self.merge("feat")
        self.push_main()
        root = self.git("-C", self.repo, "rev-list", "--max-parents=0", "HEAD").strip()
        pulls = {"12": {"state": "OPEN"}, "13": {"state": "MERGED", "cross": True, "merge": merge},
                 "14": {"state": "MERGED", "base": "dev", "merge": merge}}
        self.gh_state({n: {} for n in range(1, 9)}, [], pulls=pulls)
        refs = {"1": "#12", "2": "#13", "3": side[:12], "4": "none", "5": "#14", "6": "#99", "7": root,
                "8": "fedcba9"}
        items = {i: {"verdict": "fixed", "ref": ref, "feature": f"f{i}"} for i, ref in refs.items()}
        r = self.run_pipeline(dict(list(items.items())[:4]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.outcome(i)[:2] for i in "1234"], [("skipped", "not-merged"), ("skipped", "fork-pr"),
                                                                 ("skipped", "not-ancestor"), ("skipped", "fixed-ref")])
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        r = self.run_pipeline(dict(list(items.items())[4:]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.outcome(i)[:2] for i in "5678"], [("skipped", "other-base"), ("skipped", "unknown-ref"),
                                                                 ("skipped", "root-commit"), ("deferred", "cap")])
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        self.assertEqual(self.rows("linked.tsv"), [])

    def test_fixed_owned_unroutable_or_malformed_starts_no_stage(self):
        sha = self.fix_commit()
        self.push_main()
        self.gh_state({1: {"closedByPullRequestsReferences": [{"number": 99}]}, 2: {}}, [])
        agent = {p: [{"id": "C1", "title": "e", "body": "b", "url": "https://s.invalid/C1",
                      "created": "2026-11-0%dT00:00:00Z" % n, "updated": "2026-11-01T00:00:00Z", "labels": []}]
                 for n, p in ((3, "err-sentry"), (4, "lin"))}
        items = {"1": {"ref": sha}, "2": {"ref": "$(touch x)", "feature": "b"},
                 "err-sentry-C1": {"ref": sha, "feature": "c"}, "lin-C1": {"ref": sha, "feature": "d"}}
        r = self.run_pipeline({i: dict(v, verdict="fixed") for i, v in items.items()},
                              trust=("#", "err-sentry", "lin"), agent=agent,
                              extra_fetch="agent_fetch_new err-sentry < /dev/null; agent_fetch_new lin < /dev/null; ")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.outcome(i)[:2] for i in items],
                         [("skipped", "linked-pr"), ("skipped", "fixed-ref"), ("skipped", "no-ticket"),
                          ("skipped", "no-comment-write")])
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        self.assertEqual(self.rows("linked.tsv"), [])

    def test_fixed_linked_merged_pr_verifies_and_linked_open_pr_skips(self):
        self.fix_commit("feat")
        merge = self.merge("feat")
        self.push_main()
        self.gh_state({1: {"closedByPullRequestsReferences": [{"number": 12}]},
                       2: {"closedByPullRequestsReferences": [{"number": 13}]}}, [],
                      pulls={"12": {"state": "MERGED", "merge": merge, "commits": 2}, "13": {"state": "OPEN"}})
        r = self.run_pipeline({"1": {"verdict": "fixed", "ref": "#12"},
                               "2": {"verdict": "fixed", "ref": merge, "feature": "b"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1"), ("fixed", "linked", "none"))
        self.assertEqual(self.outcome("2")[:2], ("skipped", "linked-pr"))
        self.assertEqual(len(self.stage_calls("1", "verify")), 1)
        self.assertEqual(self.stage_calls("2"), [])
        self.assertEqual(len(self.spec_calls()), 1)
        self.assertEqual([c["issue"] for c in self.gh()["comments"]], ["1"])

    def test_fixed_foreign_linked_pr_skips_without_local_lookup(self):
        self.fix_commit("feat")
        merge = self.merge("feat")
        self.push_main()
        self.gh_state({1: {"closedByPullRequestsReferences": [{"number": 12, "repo": "x/r"}]},
                       2: {"closedByPullRequestsReferences": [{"number": 13, "repo": "x/r"}]}}, [],
                      pulls={"12": {"state": "MERGED", "merge": merge, "commits": 2}, "13": {"state": "OPEN"}})
        r = self.run_pipeline({"1": {"verdict": "fixed", "ref": "#12"},
                               "2": {"verdict": "fixed", "ref": merge, "feature": "b"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([self.outcome(i)[:2] for i in "12"], [("skipped", "linked-pr")] * 2)
        self.assertEqual(self.stage_calls() + self.spec_calls() + self.gh_writes(), [])
        self.assertEqual([c for c in self.calls() if c.startswith("gh pr view")], [])

    def test_fixed_dry_run_writes_nothing(self):
        sha = self.fix_commit()
        self.push_main()
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {"verdict": "fixed", "ref": sha}}, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.stage_calls("1", "verify")), 1)
        self.assertIn("1 verify: outcome=confirmed", r.stdout)
        self.assertEqual(self.gh_writes(), [])
        self.assertEqual(self.gh()["comments"], [])
        for name in ("pushed.tsv", "linked.tsv", "tickets.tsv"):
            self.assertEqual(self.rows(name), [])
        self.assertEqual(self.outcome("1")[:2], ("deferred", "dry-run"))

    def test_unposted_report_with_credential_or_oversize_passes(self):
        self.gh_state({1: {}, 2: {}}, [])
        items = {"1": {"feature": "a"}, "2": {"feature": "b", "verdict": "not-a-bug"}}
        extra = "sk-ant-1234567890abcdef\n" + "y" * 66000 + "\n"
        for dry in (True, False):
            with self.subTest(dry=dry):
                r = self.run_pipeline(items, dry=dry, report_extra=extra)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn("gate:", r.stderr)

    def assert_write_refused(self, setup, call, writes):
        for dry, text in ((False, "sk-ant-1234567890abcdef"), (True, "clean")):
            with self.subTest(dry=dry):
                r = self.run_pipeline({}, dry=dry, main=setup.replace("BODY", text) + "\n" + call + "\n")
                if dry:
                    self.assertEqual(r.returncode, 0, r.stderr)
                else:
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("gate: credential-shaped text", r.stderr)
                self.assertEqual([c for c in self.calls() if c.startswith(writes)], [])
                for name in ("pushed.tsv", "linked.tsv", "tickets.tsv"):
                    self.assertEqual(self.rows(name), [])

    def test_ticket_write_refused(self):
        self.assert_write_refused('id=err-sentry-C1 feature=a item=$fx/tmp/t; mkdir -p "$item"\n'
                                  'printf "BODY\\n" > "$item/spec.md"', "ticket_item", "gh issue create")

    def test_comment_write_refused(self):
        self.gh_state({1: {}}, [])
        self.assert_write_refused('printf "BODY\\n" > "$view/c.md"', 'send 1 "$view/c.md" x', "gh issue comment")

    def test_recovery_write_refused(self):
        setup = ('mkdir -p "$items/1"; echo "feature: a" > "$items/1/spec.md"; printf "BODY\\n" > "$items/1/body.md"\n'
                 'c=$(git rev-parse main); git push -q "$remote" "$c:refs/heads/factory/fix-1"')
        self.assert_write_refused(setup, 'recover_item 1 "$c" "$c"', ("gh pr create", "gh issue comment"))
        self.assertEqual(self.gh()["prs"], [])


if __name__ == "__main__":
    unittest.main()
