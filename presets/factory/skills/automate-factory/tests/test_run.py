import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, "..", "assets", "run.sh")
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

    def run_entry(self, level, scen="plain", dry=False, skills="", post="", main="", extra=None, allow="*", dep_files="0"):
        with open(RUN_SH) as f:
            script = f.read()
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1",
                     "<level>": level, "<remote url>": self.remote, "<test command>": "sh tests/a_test.sh",
                     "<path glob>": allow}.items():
            script = script.replace(k, v)
        for old, new in (("skills=()", f"skills=({skills})"), ("post() { :; }", post),
                         ("      edit\n      publish\n", main),
                         ("dep_files=0", "dep_files=1" if dep_files == "1" else "")):
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

    def test_deleted_test_without_reason_blocks(self):
        self.second_test()
        r, _, _ = self.edit_run("rm tests/b_test.sh")
        self.assert_blocked(r, "no test-change reason for tests/b_test.sh")

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


if __name__ == "__main__":
    unittest.main()
