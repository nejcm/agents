import datetime
import json
import os
import re
import unittest

import test_run

CATALOG = os.path.join(test_run.HERE, "..", "references", "catalog")

CLAUDE = r"""#!/usr/bin/env bash
echo claude >> "$LOG"
[ ! -f input/range ] || cat input/range >> "$LOG.range"
[ ! -f input/flagged.txt ] || { cat input/flagged.txt; echo --; } >> "$LOG.flagged"
[ -z "${FAIL:-}" ] || exit 1
echo report
"""


def fetch_code(name):
    with open(os.path.join(CATALOG, name + ".md")) as f:
        return "\n".join(re.findall(r"```bash\n(.*?)```", f.read(), re.S)).replace("\n  ", "\n").strip()


class TriggerTest(unittest.TestCase):
    setUp_repo = test_run.RunShTest.setUp
    tearDown = test_run.RunShTest.tearDown
    git = test_run.RunShTest.git
    write = test_run.RunShTest.write
    calls = test_run.RunShTest.calls
    commit_file = test_run.RunShTest.commit_file

    def setUp(self):
        self.setUp_repo()
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write(CLAUDE)
        self.commit_file("README", "r\n")

    def run_entry(self, entry, trigger, fill, dry=False, weekly="", extra=None):
        with open(test_run.RUN_SH) as f:
            script = f.read()
        fetch = fetch_code(entry).replace("<trigger>", trigger)
        for k, v in fill.items():
            fetch = fetch.replace(k, v)
        self.assertIn("fetch() { :; }", script)
        script = script.replace("fetch() { :; }", fetch)
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1", "<level>": "report",
                     "<weekly usd>": weekly}.items():
            script = script.replace(k, v)
        self.write(f".factory/automations/{entry}.md", "p\n")
        path = f"{self.repo}/.factory/automations/{entry}.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        env = dict(self.env, **(extra or {}), **({"FACTORY_DRY_RUN": "1"} if dry else {}))
        return test_run.subprocess.run([path], env=env, capture_output=True, text=True, timeout=120)

    def head(self):
        return self.git("-C", self.repo, "rev-parse", "main").strip()

    def records(self):
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            return [json.loads(x) for x in f]

    def model_calls(self):
        return len([c for c in self.calls() if c == "claude"])

    def report(self, entry):
        p = f"{self.repo}/.factory/reports/{entry}/{datetime.date.today()}.md"
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return f.read()

    def security(self, trigger="changes", **kw):
        return self.run_entry("security-review", trigger, {'"<risk glob>"': '"auth/*" "*.lock"'}, **kw)

    def sha_file(self):
        p = f"{self.repo}/.factory/reports/security-review/reviewed.sha"
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return f.read().strip()

    def test_security_review_without_a_risk_change_skips_and_advances(self):
        first = self.head()
        self.commit_file("src/v", "2\n")
        r = self.security()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 0)
        self.assertIsNone(self.report("security-review"))
        rec = self.records()[-1]
        self.assertEqual((rec["outcome"], rec["reason"], rec["calls"]), ("skipped", "no-risk-change", 0))
        self.assertEqual(self.sha_file(), self.head())
        self.assertIn(f"no risk-path change in {first[:12]}..", r.stdout)

    def test_security_review_with_a_risk_change_reviews_the_range_and_advances_on_success_only(self):
        self.commit_file("src/v", "2\n")
        self.security()
        before = self.head()
        self.commit_file("auth/login.py", "x\n")
        r = self.security(extra={"FAIL": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.model_calls(), self.sha_file()), (1, before))
        self.assertEqual(self.records()[-1]["outcome"], "failed")
        r = self.security()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 2)
        with open(self.log + ".range") as f:
            self.assertEqual(f.read().splitlines(), [f"{before}..{self.head()}"] * 2)
        self.assertEqual(self.report("security-review"), f"Range: {before}..{self.head()}\n\nreport\n\n")
        self.assertEqual(self.sha_file(), self.head())
        self.assertEqual(self.records()[-1]["outcome"], "completed")

    def test_a_second_review_the_same_day_keeps_the_first(self):
        ranges = []
        for path in ("auth/a", "auth/b"):
            before = self.head()
            self.commit_file(path, "1\n")
            r = self.security()
            self.assertEqual(r.returncode, 0, r.stderr)
            ranges.append(f"Range: {before}..{self.head()}")
        self.assertEqual(self.model_calls(), 2)
        self.assertEqual(re.findall(r"^Range: .*$", self.report("security-review"), re.M), ranges)

    def test_a_planted_tmp_symlink_is_never_written_through(self):
        os.makedirs(f"{self.repo}/.factory/reports/security-review")
        victim = f"{self.tmp.name}/victim"
        with open(victim, "w") as f:
            f.write("precious\n")
        os.symlink(victim, f"{self.repo}/.factory/reports/security-review/reviewed.sha.tmp")
        r = self.security()
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(victim) as f:
            self.assertEqual(f.read(), "precious\n")
        self.assertFalse(os.path.islink(f"{self.repo}/.factory/reports/security-review/reviewed.sha"))
        self.assertEqual(self.sha_file(), self.head())

    def test_catalog_code_and_prompt_fences_are_closed(self):
        for name in os.listdir(CATALOG):
            with self.subTest(name), open(os.path.join(CATALOG, name)) as f:
                self.assertEqual(len(re.findall(r"^ *```", f.read(), re.M)) % 2, 0)
        with open(os.path.join(CATALOG, "maintain-verification.md")) as f:
            self.assertIn("## Follow-up (attended)", f.read())

    def test_budget_pause_and_dry_runs_keep_the_reviewed_sha(self):
        self.security()
        before = self.sha_file()
        self.commit_file("auth/a", "1\n")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(f"{self.repo}/.factory/reports/runs.jsonl", "a") as f:
            f.write(json.dumps({"entry": "x", "started": now, "cost_usd": 9}) + "\n")
        r = self.security(weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.records()[-1]["reason"], self.model_calls(), self.sha_file()), ("weekly-budget", 0, before))
        self.write(".factory/pause", "")
        r = self.security()
        self.assertEqual((r.returncode, r.stdout, self.sha_file()), (0, "paused\n", before))
        os.remove(f"{self.repo}/.factory/pause")
        r = self.security(dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.model_calls(), self.sha_file()), (1, before))
        self.assertTrue(self.records()[-1]["dry_run"])

    def test_schedule_mode_reviews_every_run(self):
        self.commit_file("src/v", "2\n")
        r = self.security("schedule")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.model_calls(), 1)
        self.assertIn("\n\nreport\n", self.report("security-review"))
        self.assertEqual(self.sha_file(), self.head())
        r = self.run_entry("security-review", "schedule", {})
        self.assertEqual((r.returncode, self.model_calls()), (0, 2), r.stderr)

    def test_unusable_state_or_unfilled_settings_block_before_any_call(self):
        sha = f"{self.repo}/.factory/reports/security-review/reviewed.sha"
        os.makedirs(os.path.dirname(sha))
        for setup, kw, msg in (
                (lambda: os.symlink(f"{self.tmp.name}/x", sha), {}, f"{sha.split(self.repo + '/')[1]} is a symlink"),
                (lambda: open(sha, "w").close(), {}, "last reviewed SHA unusable"),
                (lambda: self.write(sha.split(self.repo + "/")[1], "f" * 40 + "\n"), {}, "last reviewed SHA unusable"),
                (lambda: None, {"trigger": "hourly"}, "trigger hourly is not schedule or changes"),
                (lambda: None, {"fill": {}}, "path glob '<risk glob>' is empty or unfilled")):
            with self.subTest(msg):
                if os.path.lexists(sha):
                    os.remove(sha)
                setup()
                kw = dict({"trigger": "changes", "fill": {'"<risk glob>"': '"auth/*"'}}, **kw)
                r = self.run_entry("security-review", kw["trigger"], kw["fill"])
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual(self.model_calls(), 0)

    def verification(self, trigger="changes"):
        fill = {"<app>": "app", '[<feature>]="<path glob>"': '[a]="src/a/*" [b]="src/b/* lib/b.py"'}
        return self.run_entry("maintain-verification", trigger, fill)

    def flagged(self):
        with open(self.log + ".flagged") as f:
            return [x.split() for x in f.read().split("--\n")[:-1]]

    def test_maintain_verification_flags_changed_features_until_the_skill_changes(self):
        self.commit_file(".cursor/skills/verify-app/SKILL.md", "v1\n")
        self.commit_file("src/a/x.py", "1\n")
        r = self.verification()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.model_calls(), self.flagged()), (1, [["a"]]))
        self.assertEqual(self.records()[-1]["outcome"], "completed")
        for path in (None, "README.md"):
            with self.subTest(path):
                if path:
                    self.commit_file(path, "r\n")
                r = self.verification()
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.model_calls(), 1)
                rec = self.records()[-1]
                self.assertEqual((rec["outcome"], rec["reason"], rec["calls"]), ("skipped", "no-risk-change", 0))
                self.assertTrue(self.report("maintain-verification").endswith("Maintenance due\n"))
                self.assertIn("still flagged: a\n", self.report("maintain-verification"))
        self.commit_file("lib/b.py", "1\n")
        r = self.verification()
        self.assertEqual((r.returncode, self.model_calls(), self.flagged()[-1]), (0, 2, ["a", "b"]), r.stderr)
        self.commit_file(".cursor/skills/verify-app/SKILL.md", "v2\n")
        r = self.verification()
        self.assertEqual((r.returncode, self.model_calls(), self.flagged()[-1]), (0, 3, []), r.stderr)
        r = self.verification()
        self.assertEqual((r.returncode, self.model_calls()), (0, 3), r.stderr)
        self.assertIn("still flagged: none\n", self.report("maintain-verification"))
        self.assertTrue(self.report("maintain-verification").endswith("No drift signals\n"))

    def test_maintain_verification_schedule_mode_analyzes_every_run(self):
        self.commit_file(".cursor/skills/verify-app/SKILL.md", "v1\n")
        self.commit_file("src/b/y", "1\n")
        for n in (1, 2):
            r = self.verification("schedule")
            self.assertEqual((r.returncode, self.model_calls()), (0, n), r.stderr)
        self.assertEqual(self.flagged(), [["b"], ["b"]])
        self.assertEqual(self.records()[-1]["outcome"], "completed")


if __name__ == "__main__":
    unittest.main()
