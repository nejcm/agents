import datetime
import json
import os
import re
import subprocess
import unittest

import test_run

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
with open(os.environ["LOG"] + ".prompts", "a") as f:
    f.write(json.dumps({"evidence": ev, "args": args[:-1], "prompt": args[-1]}) + "\n")
scen = json.load(open(os.environ["SCEN"]))
tools = args[args.index("--tools") + 1]
fmt = args[args.index("--output-format") + 1] if "--output-format" in args else ""
if fmt == "stream-json":
    prefix = re.search(r"prefix (\S+)", args[-1])[1]
    result = "".join(json.dumps(o) + "\n" for o in scen.get("agent", {}).get(prefix, []))
    print(json.dumps({"type": "system", "subtype": "init", "mcp_servers": []}))
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": result}))
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
    if stage == "reproduce":
        put(ev + "/repro.md", "steps\nrepro: outcome=" + s.get("repro", "reproduced") + "\n")
    elif stage == "fix":
        put(".github/ci.yml" if s.get("deny") else "src/" + i, "fixed\n")
        if s.get("test") == "red":
            put(f"tests/{i}_test.sh", f"test -f src/{i}\n")
        elif s.get("test") == "green":
            put(f"tests/{i}_test.sh", "true\n")
        if s.get("pause"):
            put(os.environ["REPO"] + "/.factory/pause", "")
        put(ev + "/fix.md", "root cause\nfix: outcome=changed\n")
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
    if args[i] == "--draft":
        opt["draft"], i = True, i + 1
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
    else:
        print(p["state"], str(p.get("cross", False)).lower(), p.get("base", "main"), p.get("merge", "null"),
              p.get("commits", 1))
elif cmd == "pr create":
    url = f"https://github.com/o/r/pull/{len(st['prs']) + 1}"
    st["prs"].append({"head": opt["head"], "url": url, "title": opt["title"], "draft": opt.get("draft", False),
                      "body": read(opt["body-file"])})
    save()
    print(url)
else:
    sys.exit("stub: " + cmd)
"""

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
                     report_extra="", cap="3", flow="fix", verify_fixed="on"):
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
                     "<path glob>": "*"}.items():
            script = script.replace(k, v)
        with open(PIPELINE_SH) as f:
            pipeline = f.read()
        pipeline = pipeline.replace('("<trust prefix>")', "(" + " ".join(f'"{p}"' for p in trust) + ")")
        for k, v in {"<label>": label, "<run minutes>": "240", "<app>": "app", "<cap>": cap, "<flow>": flow,
                     "<verify-fixed>": verify_fixed}.items():
            pipeline = pipeline.replace(k, v)
        fetch = "fetch_new; fetch_deferred; " + (f"fetch_labeled {label}; " if label else "") + extra_fetch + "fetch_context"
        script = script.replace("skills=()", f'skills=("{FIX_ISSUES}" "{self.tmp.name}/debugging")')
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
        self.assertEqual((rec["outcome"], rec["calls"], rec["gates"]), ("completed", 5, ["passed"]))

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
        names = ("judge", "spec", "reproduce", "fix", "verify")
        for n in names:
            self.write(f".factory/automations/issue-pipeline.{n}.local.md", f"overlay-{n}" + "\n" * (n != "reproduce"))
        self.gh_state({1: {}}, [])
        r = self.run_pipeline({"1": {}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outcome("1")[0], "fixed")
        seen = {}
        for c in self.prompts():
            ev, args = c["evidence"], c["args"]
            n = ev.rsplit("/", 1)[1] if ev else "judge" if "--restricted" in args and "Read,Grep,Glob" in args else "spec"
            seen[n] = c["prompt"]
        self.assertEqual(sorted(seen), sorted(names))
        for n, prompt in seen.items():
            with self.subTest(n):
                self.assertEqual([x for x in names if f"overlay-{x}" in prompt], [n])
                if n in ("reproduce", "fix", "verify"):
                    self.assertLess(prompt.index(f"overlay-{n}"), prompt.index("Never delete or rename a test file."))
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
