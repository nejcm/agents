import datetime
import json
import os
import re
import subprocess
import unittest

import test_run

CATALOG = os.path.join(test_run.HERE, "..", "references", "catalog", "failed-ci-triage.md")
SETTINGS = 'trigger="" daily_cap=6 window="" notify=()\n'
GH = r"""#!/usr/bin/env bash
echo "gh $*" >> "$LOG"
case "$1 $2" in
  "run list") cat "$RUNS" ;;
  "run view") case " $* " in *" --log-failed "*) echo "log $3" ;; *) echo '{"headSha": "x", "jobs": []}' ;; esac ;;
esac
"""
CLAUDE = r"""#!/usr/bin/env bash
echo claude >> "$LOG"
ls input repo > "$LOG.ls"
[ ! -f input/commit.patch ] || cp input/commit.patch "$LOG.patch"
echo report
"""


def blocks():
    with open(CATALOG) as f:
        return [("  " + b).replace("\n  ", "\n").strip() + "\n" for b in re.findall(r"```bash\n(.*?)```", f.read(), re.S)]


def ago(**kw):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(**kw)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(i, sha, wf="CI", status="completed", conclusion="failure", minutes=10):
    return dict(databaseId=i, headSha=sha, workflowName=wf, status=status,
                conclusion=conclusion if status == "completed" else "", createdAt=ago(minutes=minutes))


class FailedCiTest(unittest.TestCase):
    setUp_repo = test_run.RunShTest.setUp
    tearDown = test_run.RunShTest.tearDown
    git = test_run.RunShTest.git
    write = test_run.RunShTest.write
    calls = test_run.RunShTest.calls

    def setUp(self):
        self.setUp_repo()
        for name, body in (("gh", GH), ("claude", CLAUDE)):
            with open(f"{self.tmp.name}/bin/{name}", "w") as f:
                f.write(body)
        self.write(".factory/automations/failed-ci-triage.md", "p\n")
        self.git("-C", self.repo, "push", "-q", self.remote, "main")
        other = f"{self.tmp.name}/other"
        self.git("clone", "-q", "-b", "main", self.remote, other)
        with open(f"{other}/pushed.txt", "w") as f:
            f.write("from the failed sha\n")
        self.git("-C", other, "add", "-A")
        self.git("-C", other, "commit", "-qm", "break")
        self.git("-C", other, "push", "-q", "origin", "main")
        self.sha = self.git("-C", other, "rev-parse", "HEAD").strip()
        self.base = self.git("-C", self.repo, "rev-parse", "main").strip()
        self.out = f"{self.repo}/.factory/reports/failed-ci-triage"
        self.runs_file = f"{self.tmp.name}/runs.json"

    def tick(self, runs, trigger="watch", dry=False, workflows='"CI" "Lint"'):
        with open(self.runs_file, "w") as f:
            json.dump(runs, f)
        watch, fetch = blocks()
        for k, v in {"<trigger>": trigger, "<daily cap>": "6", "<window>": "", "<notify command>": "",
                     '"<workflow>"': workflows}.items():
            watch = watch.replace(k, v)
        with open(test_run.RUN_SH) as f:
            script = f.read()
        self.assertIn(SETTINGS, script)
        script = script.replace(SETTINGS, watch).replace("fetch() { :; }", fetch)
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1", "<level>": "report",
                     "<weekly usd>": "", "<remote url>": self.remote}.items():
            script = script.replace(k, v)
        path = f"{self.repo}/.factory/automations/failed-ci-triage.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        env = dict(self.env, RUNS=self.runs_file, **({"FACTORY_DRY_RUN": "1"} if dry else {}))
        return subprocess.run([path], env=env, capture_output=True, text=True, timeout=120)

    def records(self):
        p = f"{self.repo}/.factory/reports/runs.jsonl"
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [json.loads(x) for x in f]

    def seen(self):
        p = f"{self.out}/seen.tsv"
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [x.split("\t")[:3] for x in f.read().splitlines()]

    def model_calls(self):
        return self.calls().count("claude")

    def report(self, name):
        p = f"{self.out}/{datetime.date.today()}{name}.md"
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return f.read()

    def quiet(self, runs, **kw):
        r = self.tick(runs, **kw)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        return r

    def test_one_fire_per_sha_once_every_in_scope_run_completed(self):
        sha = self.sha
        waiting = [run(1, sha), run(2, sha, "Lint", status="in_progress"), run(3, sha, "Deploy", status="in_progress")]
        self.quiet(waiting)
        self.assertEqual((self.model_calls(), self.records(), self.seen()), (0, [], []))
        done = [run(1, sha), run(2, sha, "Lint"), run(3, sha, "Deploy", status="in_progress")]
        r = self.tick(done)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 1)
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["trigger"], rec["events"]), ("completed", "watch", ["1", "2"]))
        self.assertEqual(self.report(f"-{sha[:12]}"), "report\n")
        self.assertIsNone(self.report(""))
        views = [c for c in self.calls() if c.startswith("gh run view")]
        self.assertEqual(views, [f"gh run view {i} --repo o/r {a}" for i in (1, 2)
                                 for a in ("--log-failed", "--json headSha,workflowName,jobs")])
        self.assertIn("gh run list --repo o/r --branch main --limit 50 --json "
                      "databaseId,headSha,workflowName,status,conclusion,createdAt", self.calls())
        self.assertEqual(self.seen(), [["1", "failed", sha], ["2", "failed", sha], ["1", "done", sha], ["2", "done", sha]])
        self.quiet(done)
        self.assertEqual(self.model_calls(), 1)

    def test_the_failed_sha_is_fetched_as_data_only(self):
        refs = self.git("-C", self.repo, "for-each-ref")
        r = self.tick([run(1, self.sha)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.git("-C", self.repo, "cat-file", "-e", f"{self.sha}^{{commit}}")
        self.assertEqual(self.git("-C", self.repo, "for-each-ref"), refs)
        self.assertEqual(self.git("-C", self.repo, "rev-parse", "main").strip(), self.base)
        self.assertFalse(os.path.exists(f"{self.repo}/.git/FETCH_HEAD"))
        with open(self.log + ".patch") as f:
            self.assertIn("+from the failed sha", f.read())
        with open(self.log + ".ls") as f:
            listing = f.read()
        self.assertIn("commit.patch", listing)
        self.assertNotIn("pushed.txt", listing)

    def test_a_later_success_of_the_workflow_settles_without_a_fire(self):
        b = self.base
        self.quiet([run(2, b, minutes=5, conclusion="success"), run(1, self.sha, minutes=30)])
        self.assertEqual((self.model_calls(), self.records()), (0, []))
        self.assertEqual(self.seen(), [["1", "done", self.sha]])
        self.quiet([run(2, b, minutes=5, conclusion="success"), run(1, self.sha, minutes=30)])
        self.assertEqual(len(self.seen()), 1)

    def test_an_issue_pipeline_merge_is_skipped_with_a_pointer_and_marked_done(self):
        self.write(".factory/reports/fix-issues/merges.tsv",
                   f"gh-7 approved https://x/pull/9 {self.sha} e a 0 0 minimal 3\ngh-7 merged https://x/pull/9 {self.sha}\n")
        runs = [run(1, self.sha), run(2, self.sha, "Lint")]
        r = self.tick(runs)
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        line = f"skipped {self.sha[:12]}: issue-pipeline merged it (https://x/pull/9, item gh-7); its revert: branch factory/revert-gh-7\n"
        self.assertEqual(r.stderr, line)
        self.assertEqual((self.model_calls(), self.records()), (0, []))
        self.assertEqual(self.report(""), line)
        self.assertEqual(self.seen(), [["1", "done", self.sha], ["2", "done", self.sha]])
        self.quiet(runs)
        self.assertEqual(self.report(""), line)

    def test_only_workflows_in_scope_count(self):
        self.quiet([run(1, self.sha, "Deploy")])
        r = self.tick([run(1, self.sha, "Deploy"), run(2, self.sha)], workflows='"CI"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.records()[-1]["events"], ["2"])
        r = self.tick([run(3, self.sha)], workflows='"<workflow>"')
        self.assertIn("gate: workflow '<workflow>' is empty or unfilled", r.stderr)
        self.assertEqual(self.model_calls(), 1)

    def test_the_first_lookback_is_24_hours(self):
        self.quiet([run(1, self.sha, minutes=25 * 60)])
        r = self.tick([run(1, self.sha, minutes=25 * 60), run(2, self.sha, minutes=23 * 60)])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.records()[-1]["events"], ["2"])

    def test_with_a_ledger_the_lookback_starts_24_hours_before_the_newest_done_line(self):
        self.write(".factory/reports/failed-ci-triage/seen.tsv", f"9\tdone\t-\t{ago(days=3)}\n")
        r = self.tick([run(3, self.sha, minutes=int(4.5 * 24 * 60)), run(4, self.sha, minutes=int(3.5 * 24 * 60))])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.records()[-1]["events"], ["4"])

    def test_a_dry_run_takes_the_latest_failed_sha_and_writes_no_ledger(self):
        b = self.base
        self.write(".factory/reports/fix-issues/merges.tsv", f"gh-7 merged https://x/pull/9 {self.sha}\n")
        r = self.tick([run(1, b, minutes=600), run(2, self.sha, minutes=60), run(3, self.base, minutes=5, conclusion="success")],
                      dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 1)
        rec = self.records()[-1]
        self.assertEqual((rec["dry_run"], rec["events"]), (True, ["2"]))
        self.assertEqual(self.seen(), [])
        self.assertIsNotNone(self.report(f"-{self.sha[:12]}"))

    def test_no_failure_in_30_days_passes_a_dry_run_on_detect_alone(self):
        r = self.tick([run(1, self.sha, minutes=31 * 24 * 60), run(2, self.sha, conclusion="success")], dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no event to analyze", r.stdout)
        self.assertEqual(self.model_calls(), 0)
        self.assertEqual(self.seen(), [])

    def test_schedule_mode_triages_the_last_day_of_failures(self):
        r = self.tick([run(5, self.sha), run(6, self.sha, "Deploy"), run(7, self.sha, minutes=25 * 60)], trigger="schedule")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 1)
        self.assertIn("--status failure", [c for c in self.calls() if c.startswith("gh run list")][0])
        self.assertEqual([c for c in self.calls() if c.startswith("gh run view")],
                         ["gh run view 5 --repo o/r --log-failed", "gh run view 5 --repo o/r --json headSha,workflowName,jobs"])
        self.assertEqual(self.report(""), "report\n")
        self.assertEqual((self.records()[-1]["trigger"], self.records()[-1]["events"], self.seen()), ("schedule", None, []))
        self.assertFalse(os.path.exists(f"{self.tmp.name}/log.patch"))


if __name__ == "__main__":
    unittest.main()
