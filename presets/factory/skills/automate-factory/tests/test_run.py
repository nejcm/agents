import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, "..", "assets", "run.sh")

CLAUDE = r"""#!/usr/bin/env bash
echo "claude ${*//$'\n'/ }" >> "$LOG"
case " $* " in *" --restricted "*) echo report; exit 0 ;; esac
case "$SCEN" in
  plain) echo 2 > src/w ;;
  deny) mkdir -p .github; echo x > .github/ci.yml ;;
esac
echo "edit: outcome=changed"
"""

GH = r"""#!/usr/bin/env bash
echo "gh ${*//$'\n'/ }" >> "$LOG"
case "$1 $2" in "pr create") echo https://example.invalid/pr/1 ;; esac
"""


class RunShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.repo, self.remote, self.log = f"{t}/repo", f"{t}/remote.git", f"{t}/log"
        bin_dir = f"{t}/bin"
        os.makedirs(bin_dir)
        os.makedirs(f"{t}/home")
        for name, body in (("claude", CLAUDE), ("gh", GH)):
            with open(f"{bin_dir}/{name}", "w") as f:
                f.write(body)
            os.chmod(f"{bin_dir}/{name}", 0o755)
        self.env = {
            "PATH": bin_dir + os.pathsep + os.environ["PATH"],
            "HOME": f"{t}/home",
            "XDG_CONFIG_HOME": f"{t}/home/.config",
            "GIT_CONFIG_NOSYSTEM": "1",
            "LOG": self.log,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        }
        self.git("init", "-q", "-b", "main", self.repo)
        self.git("init", "-q", "--bare", self.remote)
        self.write("src/v", "1\n")
        self.write("tests/a_test.sh", 'test "$(cat src/v)" = 1\n')
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "init")
        self.write(".factory/automations/e.md", "p\n")
        self.write(".factory/automations/e.edit.md", "e\n")
        self.write(".factory/profile.md", "prof\n")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], env=self.env, check=True, capture_output=True, text=True).stdout

    def write(self, path, text):
        p = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def run_entry(self, level, scen="plain", dry=False):
        with open(RUN_SH) as f:
            script = f.read()
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1",
                     "<level>": level, "<remote url>": self.remote, "<test command>": "sh tests/a_test.sh",
                     "<path glob>": "*"}.items():
            script = script.replace(k, v)
        path = f"{self.repo}/.factory/automations/e.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        env = dict(self.env, SCEN=scen, **({"FACTORY_DRY_RUN": "1"} if dry else {}))
        return subprocess.run([path], env=env, capture_output=True, text=True, timeout=120)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return f.read().splitlines()

    def gh_writes(self):
        return [c for c in self.calls() if c.startswith("gh ") and not c.startswith("gh pr list")]

    def remote_heads(self):
        return self.git("--git-dir", self.remote, "for-each-ref", "--format=%(refname)", "refs/heads")

    def report_written(self):
        d = f"{self.repo}/.factory/reports/e"
        return any(n.endswith(".md") for n in os.listdir(d))

    def test_report_level(self):
        r = self.run_entry("report")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.report_written())
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("claude ") and "--restricted" in calls[0])

    def test_draft_pr_publishes(self):
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/e"])
        self.assertEqual(self.git("--git-dir", self.remote, "show", "factory/e:src/w"), "2\n")
        creates = [c for c in self.gh_writes() if c.startswith("gh pr create")]
        self.assertEqual(len(creates), 1)
        self.assertIn("--draft", creates[0])

    def test_gate_block_publishes_nothing(self):
        r = self.run_entry("draft-pr", scen="deny")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: CI, hook or policy path .github/ci.yml", r.stderr)
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])

    def test_dry_run_no_push_or_gh_write(self):
        r = self.run_entry("draft-pr", dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(c.startswith("claude ") and "--restricted" not in c for c in self.calls()))
        self.assertTrue(self.report_written())
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])

    def test_pause_exits_before_any_call(self):
        self.write(".factory/pause", "")
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "paused\n")
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(f"{self.repo}/.factory/reports"))


if __name__ == "__main__":
    unittest.main()
