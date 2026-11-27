import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, "..", "assets", "run.sh")
ONCUE = os.path.join(HERE, "..", "assets", "oncue.mjs")
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent-analytics", "scripts"))
import agent_analytics  # noqa: E402

CLAUDE = r"""#!/usr/bin/env bash
echo "claude ${*//$'\n'/ }" >> "$LOG"
printf '%s\0' "${@: -1}" >> "$LOG.prompts"
case " $* " in *" --restricted "*) [ "$SCEN" != cred ] || echo sk-ant-1234567890abcdef; echo report; exit 0 ;; esac
case "$SCEN" in
  plain) echo 2 > src/w ;;
  deny) mkdir -p .github; echo x > .github/ci.yml ;;
  skill) echo x >> skills/own/SKILL.md ;;
  relink) ln -sfn ../../skills/other .claude/skills/linked ;;
  target) echo x >> skills/linked/SKILL.md ;;
  other) echo x >> skills/other/SKILL.md ;;
  do) sh -c "$DO" ;;
esac
[ -z "${SAY:-}" ] || printf '%b\n' "$SAY"
echo "${SCOPE-scope: minimal}"
echo "edit: outcome=changed"
"""

GH = r"""#!/usr/bin/env bash
echo "gh ${*//$'\n'/ }" >> "$LOG"
for a; do [ "${prev:-}" != --body-file ] || cp "$a" "$LOG.body"; prev=$a; done
case "$1 $2" in
  "pr create") echo https://example.invalid/pr/1 ;;
  "pr list") [ -z "${PRS:-}" ] || echo "$PRS" ;;
  "api graphql")
    for a; do case $a in s=*) s=${a#s=} ;; esac; done
    [ "${CI:-}" != error ] || { echo "lookup failed" >&2; exit 1; }
    case " ${CI_GREEN:-} " in *" $s "*) echo SUCCESS ;; *) echo "${CI:-SUCCESS}" ;; esac ;;
esac
"""


MODELS = "declare -A models=([default]=claude:default)"


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

    def run_entry(self, level, scen="plain", dry=False, skills="", post="", main="", extra=None, allow="*", dep_files="0",
                  weekly="", models="", minutes="1", subs=()):
        with open(RUN_SH) as f:
            script = f.read()
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": minutes,
                     "<level>": level, "<remote url>": self.remote, "<test command>": "sh tests/a_test.sh",
                     "<path glob>": allow, "<weekly usd>": weekly}.items():
            script = script.replace(k, v)
        for old, new in (("skills=()", f"skills=({skills})"), (MODELS, models if "=(" in models else f"declare -A models=({models})" if models else ""), ("post() { :; }", post),
                         ("      edit\n      publish\n", main),
                         ("dep_files=0", "dep_files=1" if dep_files == "1" else ""), *subs):
            if new:
                self.assertIn(old, script)
                script = script.replace(old, new)
        path = f"{self.repo}/.factory/automations/e.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        env = dict(self.env, SCEN=scen, **(extra or {}), **({"FACTORY_DRY_RUN": "1"} if dry else {}))
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

    def test_runs_without_timeout_on_path(self):
        sys_bin = f"{self.tmp.name}/sys"
        os.makedirs(sys_bin)
        for d in os.environ["PATH"].split(os.pathsep):
            for n in os.listdir(d) if os.path.isdir(d) else ():
                if n not in ("timeout", "gtimeout") and not os.path.lexists(f"{sys_bin}/{n}"):
                    os.symlink(f"{d}/{n}", f"{sys_bin}/{n}")
        self.env["PATH"] = f"{self.tmp.name}/bin" + os.pathsep + sys_bin
        r = self.run_entry("report")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.calls()[0].startswith("claude "))

    def test_an_old_python3_fails_before_any_call(self):
        with open(f"{self.tmp.name}/bin/python3", "w") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(f"{self.tmp.name}/bin/python3", 0o755)
        r = self.run_entry("report")
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs python3 3.11 or later", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_draft_pr_publishes(self):
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/e"])
        self.assertEqual(self.git("--git-dir", self.remote, "show", "factory/e:src/w"), "2\n")
        creates = [c for c in self.gh_writes() if c.startswith("gh pr create")]
        self.assertEqual(len(creates), 1)
        self.assertIn("--draft", creates[0])

    def test_local_overlays_reach_analyze_and_edit_before_the_record_format(self):
        self.write(".factory/automations/e.judge.local.md", "overlay-judge\n")
        self.write(".factory/automations/e.edit.local.md", "overlay-edit\n")
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.log + ".prompts") as f:
            analyze, edit = f.read().split("\0")[:2]
        self.assertTrue(analyze.startswith("p\n\noverlay-judge\nDate: "))
        self.assertNotIn("overlay-edit", analyze)
        self.assertTrue(edit.startswith("e\n\noverlay-edit\nInputs, read-only: "))
        self.assertTrue(edit.endswith("dependency: <name> <why not in-house>."))
        with open(f"{self.repo}/.factory/automations/e.edit.local.md") as f:
            self.assertEqual(f.read(), "overlay-edit\n")

    def test_missing_default_prompt_fails(self):
        self.write(".factory/automations/e.judge.local.md", "overlay-judge\n")
        os.remove(f"{self.repo}/.factory/automations/e.md")
        r = self.run_entry("report")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.calls(), [])

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

    def test_publish_regates_a_commit_changed_after_gates(self):
        main = ('      edit\n      gates\n      mkdir "$work/.github"; echo x > "$work/.github/ci.yml"\n'
                '      git -C "$work" add -A; git -C "$work" commit -qm late\n'
                '      commit=$(git -C "$work" rev-parse HEAD)\n      publish\n')
        r = self.run_entry("draft-pr", main=main)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: CI, hook or policy path .github/ci.yml", r.stderr)
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])

    def skill_repo(self):
        for name in ("own", "linked", "other"):
            self.write(f"skills/{name}/SKILL.md", f"{name}\n")
        os.makedirs(f"{self.repo}/.claude/skills")
        os.symlink("../../skills/linked", f"{self.repo}/.claude/skills/linked")
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "skills")

    def test_consumed_skill_edit_blocked(self):
        self.skill_repo()
        for scen, path in (("skill", "skills/own/SKILL.md"), ("relink", ".claude/skills/linked"),
                           ("target", "skills/linked/SKILL.md")):
            with self.subTest(scen):
                r = self.run_entry("draft-pr", scen=scen, skills='"skills/own" ".claude/skills/linked"')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f"gate: CI, hook or policy path {path}", r.stderr)
                self.assertEqual(self.remote_heads(), "")
                self.assertEqual(self.gh_writes(), [])

    def test_unrelated_skill_edit_publishes(self):
        self.skill_repo()
        r = self.run_entry("draft-pr", scen="other", skills='"skills/own" ".claude/skills/linked"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_heads().split(), ["refs/heads/factory/e"])

    def test_post_refuses_credential_and_dry_run_writes_nothing(self):
        post = 'post() { gh issue comment 1 --repo o/r --body-file "$out/$day.md"; }'
        r = self.run_entry("comment", scen="cred", post=post)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: credential-shaped text", r.stderr)
        self.assertEqual(self.gh_writes(), [])
        r = self.run_entry("comment", post=post, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.gh_writes(), [])
        r = self.run_entry("comment", post=post)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.gh_writes()), 1)

    def records(self):
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            return [json.loads(x) for x in f]

    def json_claude(self, summary):
        stub = (r"""#!/usr/bin/env python3
import json, os, sys
open(os.environ["LOG"], "a").write("claude\n")
r = "report\n" if "--restricted" in sys.argv else SUMMARY
if os.path.isdir("src"):
    open("src/w", "w").write("2\n")
print(json.dumps({"type": "result", "subtype": "success", "result": r, "num_turns": 2, "total_cost_usd": 0.25,
                  "usage": {"input_tokens": 3, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 7,
                            "output_tokens": 11}}))
""").replace("SUMMARY", repr(summary))
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write(stub)

    def test_run_record_has_usage_and_run_fields(self):
        self.json_claude("did it\nscope: minimal\nedit: outcome=changed\n")
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("--git-dir", self.remote, "show", "factory/e:src/w"), "2\n")
        [rec] = self.records()
        base = self.git("-C", self.repo, "rev-parse", "main").strip()
        self.assertEqual({k: rec[k] for k in ("entry", "base", "start_commit", "outcome", "exit_code", "dry_run",
                                              "gates", "calls", "turns", "input_tokens", "cache_write_tokens",
                                              "cache_read_tokens", "output_tokens", "cost_usd")},
                         {"entry": "e", "base": base, "start_commit": base, "outcome": "published", "exit_code": 0,
                          "dry_run": False, "gates": ["passed"], "calls": 2, "turns": 4, "input_tokens": 6,
                          "cache_write_tokens": 10, "cache_read_tokens": 14, "output_tokens": 22, "cost_usd": 0.5})
        self.assertRegex(rec["end_commit"], "^[0-9a-f]{40}$")
        self.assertEqual(rec["diff_stat"], "1 file changed, 1 insertion(+)")
        self.assertLessEqual(rec["started"], rec["ended"])

    def test_run_record_without_usage_keeps_the_run(self):
        r = self.run_entry("report")
        self.assertEqual(r.returncode, 0, r.stderr)
        [rec] = self.records()
        base = self.git("-C", self.repo, "rev-parse", "main").strip()
        self.assertEqual((rec["outcome"], rec["calls"], rec["turns"], rec["cost_usd"], rec["start_commit"],
                          rec["end_commit"], rec["diff_stat"]), ("completed", 1, None, None, base, base, None))
        r = self.run_entry("draft-pr", dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.records()[1]["dry_run"])

    def test_max_turns_stop_writes_no_report_and_records_its_cost(self):
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write('#!/bin/sh\necho \'{"type": "result", "subtype": "error_max_turns", "num_turns": 5, '
                    '"total_cost_usd": 0.1, "usage": {}}\'\nexit 1\n')
        r = self.run_entry("report")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.report_written())
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["exit_code"], rec["turns"], rec["cost_usd"], rec["output_tokens"]),
                         ("failed", 1, 5, 0.1, None))
        self.assertEqual(rec["max_turns_hit"], 1)

    def test_usage_limit_stop_is_recorded_as_a_reason_with_unknown_cost(self):
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write('#!/bin/sh\necho \'{"type": "result", "subtype": "success", "is_error": true, "api_error_status": 429, '
                    '"result": "You have hit your limit - resets 5pm", "num_turns": 1}\'\nexit 1\n')
        r = self.run_entry("report")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.report_written())
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["reason"], rec["cost_usd"], rec["input_tokens"]), ("failed", "usage-limit", None, None))

    def test_non_json_stop_is_a_plain_failure_with_unknown_usage(self):
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write("#!/bin/sh\necho 'Overloaded'\nexit 1\n")
        self.run_entry("report")
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["reason"], rec["cost_usd"]), ("failed", None, None))

    def test_run_record_redacts_a_credential_from_the_summary(self):
        self.json_claude("test-change: sk-ant-1234567890abcdefXYZ: why\nedit: outcome=changed")
        r = self.run_entry("draft-pr")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: test-change line names no changed existing test", r.stderr)
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            line = f.read()
        self.assertNotIn("sk-ant-", line)
        rec = json.loads(line)
        self.assertEqual((rec["outcome"], rec["exit_code"], rec["cost_usd"]), ("blocked", 1, 0.5))
        self.assertEqual(rec["gates"], ["test-change line names no changed existing test: - [redacted]: why"])

    def edit_run(self, do, say="", allow="*", dep_files="0"):
        r = self.run_entry("pr", scen="do", extra={"DO": "echo 2 > src/w; " + do, "SAY": say}, allow=allow,
                           dep_files=dep_files)
        labels = [c.split("--add-label ")[1] for c in self.gh_writes() if c.startswith("gh pr edit")]
        creates = [c for c in self.gh_writes() if c.startswith("gh pr create")]
        return r, labels, creates

    def body(self):
        with open(self.log + ".body") as f:
            return f.read()

    def assert_disclosed(self, r, labels, creates, label):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(creates), 1)
        self.assertIn("--draft", creates[0])
        self.assertEqual(labels, [label])

    def assert_blocked(self, r, msg):
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: " + msg, r.stderr)
        self.assertEqual(self.remote_heads(), "")
        self.assertEqual(self.gh_writes(), [])

    def second_test(self, text="true\n"):
        self.write("tests/a_test.sh", 'for t in tests/*_test.sh; do [ "$t" = tests/a_test.sh ] || sh "$t" || exit 1; done\n'
                   'test "$(cat src/v)" = 1\n')
        self.write("tests/b_test.sh", text)
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "b")

    def test_deleted_test_with_reason_is_a_disclosed_change(self):
        self.second_test("test ! -f src/w\n")
        r, labels, creates = self.edit_run("rm tests/b_test.sh", "test-change: tests/b_test.sh: covered elsewhere")
        self.assert_disclosed(r, labels, creates, "factory:test-change")
        body = self.body()
        self.assertTrue(body.startswith("## Modifies existing tests"))
        self.assertIn("- tests/b_test.sh: covered elsewhere", body)
        self.assertIn("Deleted: tests/b_test.sh", body)
        self.assertIn("Old tests fail on the new code (exit 1): change needed.", body)

    def test_agent_instruction_change_is_always_a_labelled_draft(self):
        for path in ("AGENTS.md", "pkg/CLAUDE.md", ".claude/skills/s/notes.md", "skills/own/ref.md"):
            with self.subTest(path):
                self.skill_repo()
                r, labels, creates = self.edit_run(f"mkdir -p $(dirname {path}); echo x > {path}")
                self.assert_disclosed(r, labels, creates, "factory:instructions")
                self.assertTrue(self.body().startswith("## Changes agent instructions\n"))
                self.assertIn(f"- {path}\n", self.body())
                self.assertEqual(self.records()[-1]["instruction_change"], True)
                self.tearDown()
                self.setUp()
        r, labels, creates = self.edit_run("")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("--draft", creates[0])
        self.assertEqual((labels, self.records()[-1]["instruction_change"]), ([], False))

    def test_deleted_test_without_reason_blocks(self):
        self.second_test()
        r, _, _ = self.edit_run("rm tests/b_test.sh")
        self.assert_blocked(r, "no test-change reason for tests/b_test.sh")

    def test_tests_added_to_an_existing_file_need_no_reason_while_its_start_version_passes(self):
        self.second_test()
        r, _, _ = self.edit_run("echo 2 > src/v; { echo 'exit 0'; cat tests/a_test.sh; } > t; mv t tests/a_test.sh")
        self.assert_blocked(r, "no test-change reason for tests/a_test.sh: its start version does not pass on the new code")
        r, labels, creates = self.edit_run("echo 'test -f src/w' >> tests/b_test.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(creates), labels, self.records()[-1]["test_changes"]), (1, [], 0))
        self.assertNotIn("Modifies existing tests", self.body())

    def test_an_extended_import_line_needs_a_reason_but_a_new_import_line_does_not(self):
        self.second_test("import() { :; }\nimport a\n")
        r, _, _ = self.edit_run("{ echo 'import() { :; }'; echo 'import a b'; echo 'test -f src/w'; } > tests/b_test.sh")
        self.assert_blocked(r, "no test-change reason for tests/b_test.sh\n")
        r, labels, creates = self.edit_run("{ echo 'import b'; echo 'test -f src/w'; } >> tests/b_test.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((len(creates), labels, self.records()[-1]["test_changes"]), (1, [], 0))

    def test_an_appended_test_is_checked_apart_from_a_disclosed_test_change(self):
        self.second_test()
        r, labels, creates = self.edit_run("echo 2 > src/v; echo 'grep -qx 2 src/v' > tests/a_test.sh; "
                                           "echo 'test -f src/w' >> tests/b_test.sh",
                                           "test-change: tests/a_test.sh: src/v now holds 2")
        self.assert_disclosed(r, labels, creates, "factory:test-change")
        self.assertIn("Old tests fail on the new code (exit 1): change needed.", self.body())
        self.assertEqual(self.records()[-1]["test_changes"], 1)

    def test_renamed_test_needs_a_reason_for_its_old_path(self):
        self.second_test()
        r, _, _ = self.edit_run("mv tests/b_test.sh tests/c_test.sh")
        self.assert_blocked(r, "no test-change reason for tests/b_test.sh")
        r, labels, creates = self.edit_run("mv tests/b_test.sh tests/c_test.sh", "test-change: tests/b_test.sh: renamed")
        self.assert_disclosed(r, labels, creates, "factory:test-change")
        self.assertEqual(self.git("--git-dir", self.remote, "show", "factory/e:tests/c_test.sh"), "true\n")

    def test_skip_marker_still_blocks(self):
        r, _, _ = self.edit_run("echo 'it.skip(\"x\")' > tests/x.test.js")
        self.assert_blocked(r, "test skipped")

    def test_new_package_needs_a_dependency_line(self):
        manifests = {
            "package.json": '{"dependencies": {"left-pad": "1"}}',
            "pyproject.toml": '[project]\nname = "x"\ndependencies = ["Left_Pad>=1"]',
            "Cargo.toml": '[package]\nname = "x"\n[target.x.dev-dependencies]\nleft-pad = "1"',
            "go.mod": "module x\n\nrequire (\n\tleft-pad v1.0.0 // indirect\n)",
        }
        for name, text in manifests.items():
            with self.subTest(name):
                do = f"printf '%s\\n' '{text}' > {name}"
                r, _, _ = self.edit_run(do)
                self.assert_blocked(r, "new package without a dependency line: ")
                self.assertIn("left", r.stderr.lower())

    def test_new_package_with_a_dependency_line_is_disclosed_at_the_top(self):
        self.write("package.json", '{"dependencies": {"a": "1"}}\n')
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "pkg")
        r, labels, creates = self.edit_run(
            """printf '%s\\n' '{"dependencies": {"a": "1"}, "devDependencies": {"left-pad": "1"}}' > package.json""",
            "dependency: left-pad needs a full Unicode width table")
        self.assert_disclosed(r, labels, creates, "factory:dependency")
        body = self.body()
        self.assertTrue(body.startswith("## Adds dependencies"))
        self.assertIn("- left-pad: needs a full Unicode width table", body)
        self.assertIn("New packages: left-pad (package.json)", body)

    def test_unparsed_dependency_file_is_disclosed_not_blocked(self):
        r, labels, creates = self.edit_run("echo '{' > package.json; echo x > yarn.lock")
        self.assert_disclosed(r, labels, creates, "factory:dependency")
        self.assertIn("Dependency files changed: package.json, yarn.lock", self.body())


    def commit_file(self, path, text):
        self.write(path, text)
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", path)

    def test_manifest_outside_allow_takes_dependency_edits_only(self):
        self.commit_file("package.json", '{"scripts": {"test": "sh tests/a_test.sh"}, "dependencies": {}}\n')
        allow = 'src/*" "tests/*'
        add = """printf '%s\\n' '{"scripts": {"test": "sh tests/a_test.sh"}, "dependencies": {"left-pad": "1"}}' > package.json; """
        r, _, _ = self.edit_run(add.replace('"sh tests', '"true; sh tests'), "dependency: left-pad width table", allow, "1")
        self.assert_blocked(r, "package.json outside the allowlist: changes more than dependencies")
        r, labels, creates = self.edit_run(add + "seq 500 > yarn.lock", "dependency: left-pad width table", allow, "1")
        self.assert_disclosed(r, labels, creates, "factory:dependency")
        body = self.body()
        self.assertIn("New packages: left-pad (package.json)", body)
        self.assertIn("Dependency files changed: yarn.lock", body)
        self.assertNotIn("Lockfile changed without", body)

    def test_binary_lockfile_is_disclosed_other_binaries_block(self):
        r, _, _ = self.edit_run(r"printf 'a\000b' > src/blob")
        self.assert_blocked(r, "binary change src/blob")
        r, labels, creates = self.edit_run(r"printf 'a\000b' > bun.lockb")
        self.assert_disclosed(r, labels, creates, "factory:dependency")
        self.assertIn("Dependency files changed: bun.lockb", self.body())

    def put(self, path, text):
        src = f"{self.tmp.name}/put-{path.replace('/', '-')}"
        with open(src, "w") as f:
            f.write(text)
        return f"mkdir -p $(dirname {path}); cp {src} {path}; "

    def test_first_nested_dependency_table_outside_allow_is_dependency_only(self):
        cases = {
            "pyproject.toml": ('[tool.poetry]\nname = "x"\n', '[tool.poetry.group.test.dependencies]\nleft-pad = "1"\n'),
            "Cargo.toml": ('[package]\nname = "x"\n', '[target.x.dev-dependencies]\nleft-pad = "1"\n'),
            "sub/Cargo.toml": ('[package]\nname = "y"\n', '[workspace.dependencies]\nleft-pad = "1"\n'),
        }
        for path, (start, added) in cases.items():
            self.commit_file(path, start)
        for path, (start, added) in cases.items():
            with self.subTest(path):
                r, labels, creates = self.edit_run(self.put(path, start + added), "dependency: left-pad width table",
                                                   'src/*" "tests/*', "1")
                self.assert_disclosed(r, labels, creates, "factory:dependency")
                self.git("--git-dir", self.remote, "branch", "-qD", "factory/e")
                open(self.log, "w").close()

    def test_narrow_entries_cannot_edit_manifests_or_lockfiles(self):
        self.commit_file("package.json", '{"dependencies": {}}\n')
        dep = self.put("package.json", '{"dependencies": {"left-pad": "1"}}\n')
        for allow, do in (("tests/*", dep), ("AGENTS.md", dep), ("tests/*", "seq 5 > yarn.lock; ")):
            with self.subTest(allow=allow, do=do):
                r, _, _ = self.edit_run("rm src/w; " + do, "dependency: left-pad width table", allow)
                self.assertNotEqual(r.returncode, 0)
                self.assertRegex(r.stderr, r"gate: (package\.json|yarn\.lock) outside the allowlist\n")
                self.assertEqual(self.gh_writes(), [])

    def test_exempt_lockfile_must_be_a_regular_text_file(self):
        for do, msg in (("mkdir -p foo; ln -s ../tests/a_test.sh foo/package-lock.json", "foo/package-lock.json is not a regular file"),
                        ("printf '#!/bin/sh\\n' > yarn.lock; chmod +x yarn.lock", "yarn.lock is not a regular file"),
                        (r"printf 'a\000b' > package-lock.json", "binary change package-lock.json")):
            with self.subTest(msg):
                r, _, _ = self.edit_run(do, allow='src/*" "tests/*', dep_files="1")
                self.assert_blocked(r, msg)

    def test_lockfile_without_manifest_dependency_change_gets_its_own_line(self):
        self.commit_file("package.json", '{"dependencies": {"a": "1"}}\n')
        r, labels, creates = self.edit_run("seq 3 > package-lock.json", dep_files="1", allow='src/*" "tests/*')
        self.assert_disclosed(r, labels, creates, "factory:dependency")
        self.assertIn("Lockfile changed without a detected manifest dependency change", self.body())


    def test_exempt_lockfile_replacing_a_symlink_or_executable_blocks(self):
        os.makedirs(f"{self.repo}/foo")
        os.symlink("../tests/a_test.sh", f"{self.repo}/foo/package-lock.json")
        self.write("yarn.lock", "#!/bin/sh\nexit 0\n")
        os.chmod(f"{self.repo}/yarn.lock", 0o755)
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "bad modes")
        for do, p in (("rm foo/package-lock.json", "foo/package-lock.json"),
                      ("rm foo/package-lock.json; echo entry > foo/package-lock.json", "foo/package-lock.json"),
                      ("rm yarn.lock", "yarn.lock"), ("chmod -x yarn.lock; echo entry > yarn.lock", "yarn.lock")):
            with self.subTest(do):
                r, _, _ = self.edit_run(do, allow='src/*" "tests/*', dep_files="1")
                self.assert_blocked(r, f"{p} is not a regular file")

    def test_edit_escalation_stops_without_a_push(self):
        self.json_claude("needs the staging API key\nescalated: credentials\n")
        r = self.run_entry("pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_heads() + "".join(self.gh_writes()), "")
        with open(f"{self.repo}/.factory/reports/e/{self.today()}.md") as f:
            self.assertIn("escalated: credentials: the edit stopped; needs a human.", f.read())
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["reason"]), ("escalated", "credentials"))

    def today(self):
        return datetime.date.today().isoformat()

    def factory_pushes(self, n):
        shas = []
        for i in range(n):
            self.write("src/v", f"{i}\n")
            self.git("-C", self.repo, "commit", "-qam", f"push {i}")
            shas.append(self.git("-C", self.repo, "rev-parse", "HEAD").strip())
        self.git("-C", self.repo, "push", "-q", self.remote, "HEAD:refs/heads/factory/e")
        self.git("-C", self.repo, "reset", "-q", "--hard", "HEAD~" + str(n))
        self.write(".factory/reports/e/pushed.tsv", "".join(f"7 {c}\n" for c in shas))
        return shas

    def capped_setup(self):
        self.write("tests/a_test.sh", "true\n")
        self.git("-C", self.repo, "commit", "-qam", "t")
        return self.factory_pushes(2)

    def assert_refused(self, r, reason, why, head):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"escalated: {reason}: PR 7, {why}; needs a human.", r.stdout)
        self.assertEqual([c for c in self.calls() if c.startswith("claude") and "--restricted" not in c], [])
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", "factory/e").strip(), head)
        self.assertEqual([c for c in self.gh_writes() if not c.startswith("gh api graphql")], [])
        self.assertEqual((self.records()[-1]["outcome"], self.records()[-1]["reason"]), ("escalated", reason))

    def human_commit(self, on):
        self.git("-C", self.repo, "checkout", "-q", "--detach", on)
        self.write("src/human", "h\n")
        self.git("-C", self.repo, "add", "src/human")
        self.git("-C", self.repo, "commit", "-qm", "human")
        sha = self.git("-C", self.repo, "rev-parse", "HEAD").strip()
        self.git("-C", self.repo, "push", "-q", self.remote, "HEAD:refs/heads/factory/e")
        self.git("-C", self.repo, "checkout", "-q", "main")
        return sha

    def test_third_push_after_two_red_ci_rounds_is_refused(self):
        shas = self.capped_setup()
        r = self.run_entry("pr", extra={"PRS": f"7 {shas[1]}", "CI": "FAILURE"})
        self.assert_refused(r, "ci-cap", "the last two factory pushes failed CI", shas[1])
        self.git("--git-dir", self.remote, "update-ref", "refs/heads/factory/e", shas[0])
        r = self.run_entry("pr", extra={"PRS": f"7 {shas[0]}", "CI": "FAILURE"})
        self.assert_refused(r, "ci-cap", "the last two factory pushes failed CI", shas[0])
        human = self.human_commit(shas[0])
        r = self.run_entry("pr", extra={"PRS": f"7 {human}", "CI": "FAILURE"})
        self.assert_refused(r, "ci-cap", "the last two factory pushes failed CI", human)
        r = self.run_entry("pr", extra={"PRS": f"7 {human}", "CI": "PENDING"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(c.startswith("gh pr comment 7") for c in self.gh_writes()))
        with open(f"{self.repo}/.factory/reports/e/pushed.tsv") as f:
            rows = f.read().splitlines()
        self.assertEqual(rows[:2], [f"7 {c}" for c in shas])
        self.assertEqual(rows[2], "7 " + self.git("--git-dir", self.remote, "rev-parse", "factory/e").strip())

    def test_run_records_disclosures_and_ci_cap_and_analytics_counts_them(self):
        self.second_test()
        r, labels, _ = self.edit_run("rm tests/b_test.sh; echo '{\"dependencies\": {\"left-pad\": \"1\"}}' > package.json",
                                     "test-change: tests/b_test.sh: covered elsewhere\\ndependency: left-pad width table")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(labels, ["factory:test-change", "factory:dependency"])
        rec = self.records()[-1]
        self.assertEqual((rec["outcome"], rec["test_changes"], rec["dependency_change"]), ("published", 1, True))
        self.git("--git-dir", self.remote, "update-ref", "-d", "refs/heads/factory/e")
        r = self.run_entry("pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.records()[-1]["test_changes"], self.records()[-1]["dependency_change"]), (0, False))
        self.git("--git-dir", self.remote, "update-ref", "-d", "refs/heads/factory/e")
        shas = self.factory_pushes(2)
        r = self.run_entry("pr", extra={"PRS": f"7 {shas[1]}", "CI": "FAILURE"})
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.records()[-1]
        self.assertEqual((rec["reason"], rec["test_changes"], rec["dependency_change"]), ("ci-cap", None, None))
        report = "\n".join(agent_analytics.render_runs(agent_analytics.factory_runs(self.repo, None)))
        self.assertIn("| e | 3 | escalated 1, published 2 |", report)
        self.assertIn("Escalation reasons: ci-cap 1. Disclosed: existing tests changed in 1 (1 files), dependencies in 1.",
                      report)
        self.assertNotIn("left-pad", report)

    def test_green_human_head_resets_the_ci_cap(self):
        shas = self.capped_setup()
        human = self.human_commit(shas[1])
        r = self.run_entry("pr", extra={"PRS": f"7 {human}", "CI": "FAILURE", "CI_GREEN": human})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(c.startswith("gh pr comment 7") for c in self.gh_writes()))

    def test_ci_lookup_error_refuses_the_push(self):
        shas = self.capped_setup()
        r = self.run_entry("pr", extra={"PRS": f"7 {shas[1]}", "CI": "error"})
        self.assert_refused(r, "ci-unknown", "CI status unknown", shas[1])

    def test_symlinked_push_ledger_is_refused(self):
        shas = self.capped_setup()
        ledger = f"{self.repo}/.factory/reports/e/pushed.tsv"
        os.rename(ledger, f"{self.tmp.name}/elsewhere")
        os.symlink(f"{self.tmp.name}/elsewhere", ledger)
        r = self.run_entry("pr", extra={"PRS": f"7 {shas[1]}", "CI": "PENDING"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: .factory/reports/e/pushed.tsv is a symlink or not a regular file", r.stderr)
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", "factory/e").strip(), shas[1])
        self.assertEqual([c for c in self.gh_writes() if not c.startswith("gh api graphql")], [])
        with open(f"{self.tmp.name}/elsewhere") as f:
            self.assertEqual(len(f.read().splitlines()), 2)


    def pushed_commits(self):
        main = self.git("-C", self.repo, "rev-parse", "main").strip()
        return self.git("--git-dir", self.remote, "rev-list", "--count", f"{main}..factory/e").strip()

    def scoped_run(self, do, say, scope=""):
        r = self.run_entry("pr", scen="do", extra={"DO": do, "SAY": say, "SCOPE": scope})
        labels = [c.split("--add-label ")[1] for c in self.gh_writes() if c.startswith("gh pr edit")]
        return r, labels, [c for c in self.gh_writes() if c.startswith("gh pr create")]

    def test_refactor_scope_over_the_old_cap_publishes_split_commits(self):
        r, labels, creates = self.scoped_run("seq 3000 > src/big; git add -A; git commit -qm refactor; echo 2 > src/w",
                                             "scope: refactor the parser has to move out first")
        self.assert_disclosed(r, labels, creates, "factory:refactor")
        body = self.body()
        self.assertTrue(body.startswith("## Refactor scope\n\nthe parser has to move out first\n"))
        self.assertIn("Scope refactor, 3001 weighted lines.", body)
        self.assertEqual(self.pushed_commits(), "2")
        rec = self.records()[-1]
        self.assertEqual((rec["outcome"], rec["scope"], rec["weighted_lines"]), ("published", "refactor", 3001))
        report = "\n".join(agent_analytics.render_runs(agent_analytics.factory_runs(self.repo, None)))
        self.assertIn("Scope: minimal 0, refactor 1; largest 3,001 weighted lines.", report)

    def test_minimal_scope_squashes_edit_commits_and_weighs_deletions_a_quarter(self):
        self.commit_file("src/big", "".join(f"{i}\n" for i in range(20000)))
        r, labels, creates = self.scoped_run("git rm -q src/big; git commit -qm gone; echo 2 > src/w", "", "scope: minimal")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((labels, "--draft" in creates[0]), ([], False))
        self.assertEqual(self.pushed_commits(), "1")
        self.assertEqual(self.records()[-1]["weighted_lines"], 5001)

    def test_over_the_ceiling_blocks(self):
        r, _, _ = self.scoped_run("seq 10001 > src/big", "", "scope: minimal")
        self.assert_blocked(r, "10001 weighted changed lines, ceiling 10000")

    def test_missing_or_malformed_scope_line_blocks(self):
        for say, scope in (("", ""), ("", "scope: refactor  "), ("", "scope: large"),
                           ("scope: minimal", "scope: minimal")):
            with self.subTest(scope=scope, say=say):
                r, _, _ = self.scoped_run("echo 2 > src/w", say, scope)
                self.assert_blocked(r, "more than one scope line" if say else "no scope line: scope: minimal or scope: refactor")

    def test_refactor_without_a_separate_commit_blocks(self):
        r, _, _ = self.scoped_run("echo 2 > src/w", "scope: refactor needs room")
        self.assert_blocked(r, "scope refactor needs refactor commits before the behaviour commit")

    def test_refactor_commit_that_changes_or_fails_tests_blocks(self):
        for do, say, msg in (
                ("echo true >> tests/a_test.sh; git commit -qam r; echo 2 > src/w",
                 "test-change: tests/a_test.sh: tidy\nscope: refactor split", "changes existing test tests/a_test.sh"),
                ("echo 9 > src/v; git commit -qam r; printf '1\\n\\n' > src/v; echo 2 > src/w",
                 "scope: refactor split", "tests failed at refactor commit "),
                ("echo x > src/tmp; git add -A; git commit -qm r; rm src/tmp; echo 2 > src/w",
                 "scope: refactor split", "a commit changes src/tmp, unchanged in the final diff")):
            with self.subTest(msg):
                r, _, _ = self.scoped_run(do, say)
                self.assert_blocked(r, "")
                self.assertIn(msg, r.stderr)

    def test_every_pushed_commit_passes_the_content_gates(self):
        for do, msg in (
                ("printf 'sk-ant-1234567890abcdef\\n' > src/w; git add -A; git commit -qm r; echo safe > src/w",
                 "credential-shaped text at commit "),
                ("printf '\\0' > src/w; git add -A; git commit -qm r; echo safe > src/w", "binary change src/w")):
            with self.subTest(msg):
                r, _, _ = self.scoped_run(do, "scope: refactor split")
                self.assert_blocked(r, msg)

    def test_intermediate_commit_keeps_guarded_manifests_dependency_only_and_regular(self):
        start = '{"scripts": {"test": "sh tests/a_test.sh"}, "dependencies": {}}'
        self.commit_file("package.json", start + "\n")
        dep = start.replace("{}", '{"left-pad": "1"}')
        final = f"printf '%s\\n' '{dep}' > package.json; echo 2 > src/w"
        for do, msg in (
                (f"printf '%s\\n' '{start.replace('sh tests', 'true; sh tests')}' > package.json; git commit -qam r; " + final,
                 "package.json outside the allowlist: changes more than dependencies at commit "),
                (f"printf '%s\\n' '{start}' > src/payload; rm package.json; ln -s src/payload package.json; git add -A; "
                 "git commit -qm r; rm package.json; " + final, "package.json is not a regular file")):
            with self.subTest(msg):
                r = self.run_entry("pr", scen="do", allow='src/*" "tests/*', dep_files="1", extra={
                    "DO": do, "SAY": "dependency: left-pad width table", "SCOPE": "scope: refactor split"})
                self.assert_blocked(r, msg)

    def test_refactor_commit_that_turns_a_test_into_a_symlink_blocks(self):
        do = ("echo true > src/pass; rm tests/a_test.sh; ln -s ../src/pass tests/a_test.sh; echo 9 > src/v; "
              "git add -A; git commit -qm r; rm tests/a_test.sh; git checkout -q HEAD~1 -- tests/a_test.sh; "
              "echo true >> tests/a_test.sh; printf '1\\n\\n' > src/v; echo 2 > src/w")
        r, _, _ = self.scoped_run(do, "test-change: tests/a_test.sh: tidy\nscope: refactor split")
        self.assert_blocked(r, "tests/a_test.sh is a symlink or submodule")

    def test_allowlisted_symlink_or_submodule_blocks_and_executable_passes(self):
        for do, msg in (("ln -s ../tests/a_test.sh src/link", "src/link is a symlink or submodule"),
                        ("git init -q src/sub; git -C src/sub commit -q --allow-empty -m x", "src/sub is a symlink or submodule")):
            with self.subTest(msg):
                r, _, _ = self.edit_run(do)
                self.assert_blocked(r, msg)
        r, _, creates = self.edit_run("printf '#!/bin/sh\\n' > src/run; chmod +x src/run")
        self.assertEqual((r.returncode, len(creates)), (0, 1), r.stderr)

    def test_path_git_would_quote_blocks_and_unicode_path_is_gated_by_its_real_name(self):
        tab = "$(printf 'ci\\t.yml')"
        for do, allow in ((f'mkdir -p .github/workflows; echo x > ".github/workflows/{tab}"', "*"),
                          (f'ln -s /nonexistent "src/{tab}"', "*"),
                          (f'mkdir -p .github/src; echo x > ".github/src/{tab}"', "*/src/*"),
                          ("echo x > 'src/a\"b'", "src/*")):
            with self.subTest(do):
                r, _, _ = self.edit_run(do, allow=allow)
                self.assert_blocked(r, "path ")
                self.assertIn("has a control character, quote or backslash", r.stderr)
        r, _, _ = self.edit_run("mkdir -p .github; echo x > .github/č.yml")
        self.assert_blocked(r, "CI, hook or policy path .github/č.yml")
        r, _, _ = self.edit_run("ln -s /nonexistent src/č")
        self.assert_blocked(r, "src/č is a symlink or submodule")
        r, _, creates = self.edit_run("echo x > src/č.txt", allow="src/*")
        self.assertEqual((r.returncode, len(creates)), (0, 1), r.stderr)
        self.assertIn("src/č.txt", self.git("--git-dir", self.remote, "ls-tree", "-r", "-z", "--name-only", "factory/e"))

    def runs(self, *recs):
        os.makedirs(f"{self.repo}/.factory/reports", exist_ok=True)
        with open(f"{self.repo}/.factory/reports/runs.jsonl", "w") as f:
            f.write("".join(json.dumps(x) + "\n" for x in recs))

    def last_record(self):
        with open(f"{self.repo}/.factory/reports/runs.jsonl") as f:
            return json.loads(f.read().splitlines()[-1])

    def test_weekly_budget_reached_stops_before_any_call(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        ago = lambda d: (now - datetime.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.runs({"entry": "e", "started": ago(8), "cost_usd": 50}, {"entry": "e", "started": ago(1), "cost_usd": 3},
                  {"entry": "x", "started": ago(2), "cost_usd": 2}, {"entry": "x", "started": ago(1), "cost_usd": None})
        r = self.run_entry("draft-pr", weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = "weekly budget reached: $5.00 of $5 in the last 7 days; 1 runs without a cost counted as 0\n"
        self.assertEqual(r.stdout, line)
        with open(f"{self.repo}/.factory/reports/e/{datetime.date.today()}.md") as f:
            self.assertEqual(f.read(), line)
        self.assertEqual(self.calls(), [])
        self.assertEqual((self.last_record()["outcome"], self.last_record()["reason"]), ("skipped", "weekly-budget"))
        r = self.run_entry("draft-pr", weekly="5.01")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weekly budget: $5.00 of $5.01 in the last 7 days; 1 runs without a cost counted as 0\n", r.stdout)
        self.assertEqual(len([c for c in self.calls() if c.startswith("claude ")]), 2)

    def test_weekly_budget_counts_only_finite_nonnegative_costs(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        recs = [{"started": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "cost_usd": 3},
                {"started": now.isoformat(), "cost_usd": 2}]
        with open(f"{self.tmp.name}/bad", "w") as f:
            f.write("".join(f'{{"started": "{recs[0]["started"]}", "cost_usd": {c}}}\n' for c in ("NaN", "-5", "Infinity")))
        self.runs(*recs)
        with open(f"{self.tmp.name}/bad") as src, open(f"{self.repo}/.factory/reports/runs.jsonl", "a") as f:
            f.write(src.read())
        r = self.run_entry("report", weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "weekly budget reached: $5.00 of $5 in the last 7 days; 3 runs without a cost counted as 0\n")
        self.assertEqual(self.calls(), [])

    def test_weekly_budget_fails_closed_on_an_unusable_ledger(self):
        for kind in ("symlink", "directory", "unreadable"):
            with self.subTest(kind):
                self.setUp()
                p = f"{self.repo}/.factory/reports/runs.jsonl"
                os.makedirs(p if kind == "directory" else os.path.dirname(p))
                if kind == "symlink":
                    open(f"{self.tmp.name}/empty", "w").close()
                    os.symlink(f"{self.tmp.name}/empty", p)
                elif kind == "unreadable":
                    open(p, "w").close()
                    os.chmod(p, 0)
                r = self.run_entry("report", weekly="5")
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: weekly budget: runs.jsonl ", r.stderr)
                self.assertEqual(self.calls(), [])
                self.tearDown()
        self.setUp()
        r = self.run_entry("report", weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weekly budget: $0.00 of $5", r.stdout)

    def test_weekly_budget_needs_an_appendable_ledger(self):
        self.runs({"started": "2000-01-01T00:00:00Z", "cost_usd": 1})
        p = f"{self.repo}/.factory/reports/runs.jsonl"
        os.chmod(p, 0o444)
        r = self.run_entry("report", weekly="5")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: weekly budget: runs.jsonl cannot be appended to", r.stderr)
        self.assertEqual(self.calls(), [])
        os.chmod(p, 0o644)
        r = self.run_entry("pr", scen="do", weekly="5", extra={"DO": f"echo 2 > src/w; chmod 444 {p}"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("record: ", r.stderr)

    def test_unfilled_or_invalid_budget_or_model_fails_before_any_call(self):
        bad = "is not <cli>:<model>[@effort]"
        for kw, msg in (({"weekly": "<weekly usd>"}, "weekly budget <weekly usd> is not empty or a number of USD"),
                        ({"weekly": "-1"}, "weekly budget -1 is not empty or a number of USD"),
                        ({"models": '[default]="<model default>"'}, f"model <model default> {bad}"),
                        ({"models": "[default]=sonnet"}, f"model sonnet {bad}"),
                        ({"models": '[default]="claude:opus claude:sonnet"'}, f"model claude:opus claude:sonnet {bad}"),
                        ({"models": "[default]=claude:a,b"}, f"model claude:a,b {bad}"),
                        ({"models": "[default]=claude:default [edit]=nope:gpt-5.6-sol-high"},
                         "model nope:gpt-5.6-sol-high: CLI nope is not claude, codex, agy or agent"),
                        ({"models": "[default]=claude:opus@huge"},
                         "model claude:opus@huge: effort huge is not low, medium, high, xhigh or max"),
                        ({"models": "[default]=claude:opus [verfy]=claude:opus"}, "models: verfy is not a stage"),
                        ({"models": "[edit]=claude:opus"}, "models has no default"),
                        ({"models": "models=(opus sonnet)"}, "models: 0 is not a stage")):
            with self.subTest(msg):
                r = self.run_entry("draft-pr", **kw)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual(self.calls(), [])

    def test_default_and_per_stage_models_reach_each_call(self):
        for models, analyze, edit in (("", [], []),
                                      ("[default]=claude:default@low", ["--effort low"], ["--effort low"]),
                                      ("[default]=claude:opus@high [edit]=claude:sonnet",
                                       ["--model opus", "--effort high"], ["--model sonnet"])):
            with self.subTest(models):
                if os.path.exists(self.log):
                    os.remove(self.log)
                self.git("--git-dir", self.remote, "update-ref", "-d", "refs/heads/factory/e")
                r = self.run_entry("draft-pr", models=models)
                self.assertEqual(r.returncode, 0, r.stderr)
                [a, e] = [c for c in self.calls() if c.startswith("claude ")]
                self.assertIn("--restricted", a)
                for call, want in ((a, analyze), (e, edit)):
                    self.assertEqual(re.findall(r"--(?:model|effort) \S+", call), want)

    def test_a_model_not_picked_for_its_stage_refuses(self):
        r = self.run_entry("draft-pr", models="[default]=claude:opus",
                           main='      run_model edit claude:sonnet Read "$view" "$view/x.json" p < /dev/null\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gate: model claude:sonnet is not picked for edit", r.stderr)
        self.assertEqual(len([c for c in self.calls() if c.startswith("claude ")]), 1)

    def test_analyze_stops_at_its_minutes(self):
        with open(f"{self.tmp.name}/bin/claude", "w") as f:
            f.write("#!/bin/sh\nexec sleep 30\n")
        t = datetime.datetime.now()
        r = self.run_entry("report", minutes="0.02")
        self.assertEqual(r.returncode, 124, r.stderr)
        self.assertLess((datetime.datetime.now() - t).total_seconds(), 20)
        self.assertEqual(self.last_record()["stages"][0]["exit"], 124)
        self.assertFalse(self.report_written())

    def test_extra_skills_reach_the_view_and_need_distinct_names(self):
        self.skill_repo()
        os.makedirs(f"{self.tmp.name}/x/own")
        with open(f"{self.tmp.name}/x/own/SKILL.md", "w") as f:
            f.write("x\n")
        main = '      ls "$view/skills" > "$LOG.skills"\n      edit\n      publish\n'
        r = self.run_entry("draft-pr", skills=f'"skills/own" "{self.tmp.name}/x"', main=main)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.log + ".skills") as f:
            self.assertEqual(f.read().split(), ["own", "x"])
        os.remove(self.log)
        r = self.run_entry("draft-pr", skills=f'"skills/own" "{self.tmp.name}/x/own"', main=main)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(f"gate: skill {self.tmp.name}/x/own: another skill is named own", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_run_record_lists_stages_and_sums_reported_cost(self):
        self.json_claude("did it\nscope: minimal\nedit: outcome=changed\n")
        r = self.run_entry("draft-pr", models="[default]=claude:opus@high [edit]=claude:default")
        self.assertEqual(r.returncode, 0, r.stderr)
        [rec] = self.records()
        usage = {"turns": 2, "input_tokens": 3, "cache_write_tokens": 5, "cache_read_tokens": 7, "output_tokens": 11,
                 "cost_usd": 0.25, "exit": 0}
        self.assertEqual(rec["stages"], [
            dict(stage="analyze", cli="claude", model="opus", family="anthropic", effort="high", isolation="restricted", **usage),
            dict(stage="edit", cli="claude", model="default", family="anthropic", effort=None, isolation="environment",
                 **usage)])
        self.assertEqual((rec["cost_usd"], rec["cost_complete"]), (0.5, True))
        stub = f"{self.tmp.name}/bin/claude"
        with open(stub) as f:
            body = f.read()
        with open(stub, "w") as f:
            f.write(body.replace('"total_cost_usd": 0.25,', '"total_cost_usd": 0.25 if "--restricted" in sys.argv else None,'))
        self.git("--git-dir", self.remote, "update-ref", "-d", "refs/heads/factory/e")
        r = self.run_entry("draft-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.records()[1]
        self.assertEqual([s["cost_usd"] for s in rec["stages"]], [0.25, None])
        self.assertEqual((rec["cost_usd"], rec["cost_complete"], rec["turns"]), (0.25, False, 4))
        r = self.run_entry("report", weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weekly budget: $0.75 of $5 in the last 7 days; 1 runs with a stage that reported no cost\n", r.stdout)

    def test_job_spec_takes_the_entry_schedule_and_minutes(self):
        with open(os.path.join(HERE, "..", "references", "runners.md")) as f:
            [tpl] = re.findall(r"```json\n(.*?)```", f.read(), re.S)
        schedule = '{"kind": "calendar", "at": [{"weekday": "tue", "hour": 9, "minute": 30}]}'
        fill = {"<schedule>": schedule, "<bash>": "/b/bash", "<repo-root>": "/w/r", "<repo>": "r", "<entry>": "e", "<minutes>": "45"}
        for k, v in fill.items():
            tpl = tpl.replace(k, v)
        self.assertNotRegex(tpl, r"<[a-z -]+>")
        spec = json.loads(tpl)
        self.assertEqual((spec["namespace"], spec["name"], spec["cwd"]), ("factory-r", "e", "/w/r"))
        self.assertEqual(spec["command"], ["/b/bash", "/w/r/.factory/automations/e.sh"])
        self.assertEqual(spec["log"], "/w/r/.factory/automations/e.log")
        self.assertEqual(spec["timeout"], 45)
        if shutil.which("node"):
            r = subprocess.run(["node", ONCUE, "render", "-", "--backend", "systemd"], input=tpl,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("TimeoutStartSec=45min\n", r.stdout)
            self.assertIn("OnCalendar=Tue *-*-* 09:30\n", r.stdout)
            smoke = json.dumps({**spec, "schedule": {"kind": "manual"}, "env": {"FACTORY_DRY_RUN": "1"}})
            r = subprocess.run(["node", ONCUE, "render", "-", "--backend", "systemd"], input=smoke,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("[Timer]", r.stdout)
            self.assertIn("Environment=\"FACTORY_DRY_RUN=1\"\n", r.stdout)

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_launchd_renders_the_spec_without_timeout_and_refuses_one_with_it(self):
        with open(os.path.join(HERE, "..", "references", "runners.md")) as f:
            [tpl] = re.findall(r"```json\n(.*?)```", f.read(), re.S)
        fill = {"<schedule>": '{"kind": "interval", "minutes": 30}', "<bash>": "/b/bash", "<repo-root>": "/w/r",
                "<repo>": "r", "<entry>": "e", "<minutes>": "45"}
        for k, v in fill.items():
            tpl = tpl.replace(k, v)
        spec = json.loads(tpl)
        mac = json.dumps({k: v for k, v in spec.items() if k != "timeout"})
        r = subprocess.run(["node", ONCUE, "render", "-", "--backend", "launchd"], input=mac,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<plist ", r.stdout)
        self.assertIn("<array><string>/b/bash</string><string>/w/r/.factory/automations/e.sh</string></array>", r.stdout)
        r = subprocess.run(["node", ONCUE, "render", "-", "--backend", "launchd"], input=tpl,
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("timeout is not supported", r.stderr)

    def test_vendored_oncue_names_its_version(self):
        with open(ONCUE) as f:
            self.assertEqual(f.readline(), "#!/usr/bin/env node\n")
            self.assertRegex(f.readline(), r"^// oncue 0\.3\.0 [0-9a-f]{40}, built with bun run build:node\n$")

if __name__ == "__main__":
    unittest.main()
