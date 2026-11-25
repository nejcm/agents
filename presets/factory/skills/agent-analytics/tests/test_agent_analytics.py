import contextlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import agent_analytics as aa  # noqa: E402

HOME = os.path.join(HERE, "fixtures", "home")
REPO = "/work/demo"
MERGED = [
    {"url": "https://github.com/o/demo/pull/7", "headRefName": "x", "isCrossRepository": False},
    {"url": "https://github.com/o/demo/pull/8", "headRefName": "feat/c", "isCrossRepository": False},
    {"url": "https://github.com/o/demo/pull/9", "headRefName": "zzz", "isCrossRepository": False},
]


def run(*args, home=HOME, repo=REPO):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        aa.main(["--home", home, "--repo", repo, *args])
    return out.getvalue()


def write(home, rel, recs, raw=""):
    path = os.path.join(home, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(raw + "".join(json.dumps(r) + "\n" for r in recs))
    return path


def claude_msg(mid, tokens, cwd=REPO, sid="s", content=()):
    msg = {"id": mid, "usage": {"input_tokens": tokens}, "content": list(content)}
    return {"type": "assistant", "cwd": cwd, "sessionId": sid, "message": msg}


def pb(num, value):
    def varint(n):
        out = b""
        while n > 0x7F:
            out, n = out + bytes([n & 0x7F | 0x80]), n >> 7
        return out + bytes([n])
    if isinstance(value, int):
        return varint(num << 3) + varint(value)
    return varint(num << 3 | 2) + varint(len(value)) + value


def agy_db(home, rel, workspace, gens):
    path = os.path.join(home, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE trajectory_metadata_blob (data BLOB)")
        db.execute("CREATE TABLE gen_metadata (idx INTEGER, data BLOB)")
        db.execute("INSERT INTO trajectory_metadata_blob VALUES (?)", (pb(1, pb(1, workspace.encode())),))
        for i, (inp, out, cached) in enumerate(gens):
            usage = pb(2, inp) + pb(3, out) + pb(5, cached)
            db.execute("INSERT INTO gen_metadata VALUES (?, ?)", (i, pb(1, pb(4, usage))))
    db.close()
    return path


def row(report, label):
    return next(line for line in report.splitlines() if line.startswith(f"| {label} |"))


class ClaudeTest(unittest.TestCase):
    def test_counts_repo_and_worktree_sessions_only(self):
        s = aa.claude(HOME, REPO, None)
        self.assertEqual((s["sessions"], s["subagents"]), (2, 1))
        self.assertEqual((s["input"], s["cache_write"], s["cache_read"], s["output"]), (13, 100, 1000, 10))
        self.assertEqual((s["cost"], s["cost_sessions"]), (1.25, 1))
        self.assertEqual((s["tool_calls"], s["failed"], s["retries"], s["escalations"]), (3, 1, 1, 1))


class CodexTest(unittest.TestCase):
    def test_filters_by_cwd_and_uses_last_cumulative_usage(self):
        s = aa.codex(HOME, REPO, None)
        self.assertEqual((s["sessions"], s["subagents"]), (1, 1))
        self.assertEqual((s["input"], s["cache_read"], s["output"]), (100, 60, 51))
        self.assertEqual((s["tool_calls"], s["escalations"]), (2, 1))


class CursorTest(unittest.TestCase):
    def test_counts_sessions_and_tool_calls(self):
        s = aa.cursor(HOME, REPO, None)
        self.assertEqual((s["sessions"], s["subagents"], s["tool_calls"]), (1, 1, 3))


class ReportTest(unittest.TestCase):
    def test_reports_totals_coverage_and_no_text(self):
        report = run()
        self.assertNotIn("SECRET", report)
        self.assertNotIn(HOME, report)
        self.assertIn("| Sessions | 2 | 1 | 1 | 4 |", report)
        self.assertIn("| Cost, USD (harness estimate) | 1.25 | unavailable | unavailable | 1.25 |", report)
        self.assertIn("Codex: 1 sessions, 1 subagent transcripts. Unavailable: cost, failed, retries.", report)
        self.assertIn("Sessions per merged PR: unavailable", report)

    def test_links_sessions_to_merged_prs_by_url_or_branch(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(MERGED, f)
        try:
            report = run("--merged", f.name)
        finally:
            os.unlink(f.name)
        self.assertIn("Merged PRs in list: 3; with an explicitly linked session: 2.", report)
        self.assertIn("Sessions linked to a merged PR (PR URL, else a unique same-repo head branch): 2.", report)
        self.assertIn("Sessions per merged PR: 1.0.", report)

    def test_since_after_all_transcripts_finds_nothing(self):
        report = run("--since", "2999-01-01")
        self.assertIn("| Sessions | not found | not found | not found | unavailable |", report)

    def test_missing_harness_is_reported(self):
        with tempfile.TemporaryDirectory() as empty:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                aa.main(["--home", empty, "--repo", REPO])
        self.assertIn("Cursor: no transcripts found for this repo.", out.getvalue())


    def test_reads_factory_run_records_before_transcripts(self):
        with tempfile.TemporaryDirectory() as repo:
            write(repo, ".factory/reports/runs.jsonl", [
                {"entry": "e", "started": "2026-11-02T07:00:00Z", "outcome": "published", "dry_run": False,
                 "gates": ["SECRET path"], "turns": 4, "input_tokens": 6, "cache_write_tokens": 10,
                 "cache_read_tokens": 14, "output_tokens": 22, "cost_usd": 0.5},
                {"entry": "e", "started": "2026-11-03T07:00:00Z", "outcome": "blocked", "dry_run": True,
                 "turns": None, "cost_usd": None},
                {"entry": "e", "started": "2026-10-01T07:00:00Z", "outcome": "failed", "turns": 9}], raw="not json\n")
            report = run("--since", "2026-11-01", repo=repo)
            self.assertNotIn("SECRET", report)
            self.assertLess(report.index("## Factory runs"), report.index("| Sessions |"))
            self.assertIn("| e | 2 | blocked 1, published 1 | 4 | 6 | 10 | 14 | 22 | 0.50 |", report)
            self.assertIn("- e: 1 of 2 runs dry. Turns reported by 1, tokens by 1, cost by 1.", report)
            write(repo, ".factory/reports/runs.jsonl", [{"entry": "e", "outcome": "failed", "turns": 5, "cost_usd": 0.1}])
            self.assertIn("| e | 1 | failed 1 | 5 | unavailable | unavailable | unavailable | unavailable | 0.10 |",
                          run(repo=repo))
        self.assertIn("No run records (`.factory/reports/runs.jsonl` not found).", run())

    def test_escalations_are_scored_for_runs_and_items(self):
        with tempfile.TemporaryDirectory() as repo:
            write(repo, ".factory/reports/runs.jsonl", [
                {"entry": "e", "outcome": "escalated", "reason": "ci-cap"},
                {"entry": "p", "outcome": "completed", "items": [{"outcome": "escalated"}, {"outcome": "fixed"},
                                                                {"outcome": "BAD"}]}])
            report = run(repo=repo)
        self.assertIn("| e | 1 | escalated 1 |", report)
        self.assertIn("cost by 0. Items: ? 1, escalated 1, fixed 1.", report)

    def test_escalation_reasons_and_disclosures_are_counted_without_paths(self):
        with tempfile.TemporaryDirectory() as repo:
            write(repo, ".factory/reports/runs.jsonl", [
                {"entry": "e", "outcome": "escalated", "reason": "ci-cap"},
                {"entry": "e", "outcome": "published", "reason": None, "test_changes": 2, "dependency_change": True},
                {"entry": "p", "outcome": "completed", "test_changes": None, "items": [
                    {"outcome": "escalated", "reason": "credentials"}, {"outcome": "escalated", "reason": "SECRET path"},
                    {"outcome": "fixed", "test_changes": 1, "dependency_change": False},
                    {"outcome": "blocked", "reason": "gates", "test_changes": "1", "dependency_change": "yes"}]}])
            report = run(repo=repo)
        self.assertNotIn("SECRET", report)
        self.assertIn("cost by 0. Escalation reasons: ci-cap 1. Disclosed: existing tests changed in 1 (2 files), "
                      "dependencies in 1.", report)
        self.assertIn("Escalation reasons: ? 1, credentials 1. Disclosed: existing tests changed in 1 (1 files), "
                      "dependencies in 0.", report)


    def runs(self, recs, fates=""):
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo)
        write(repo, ".factory/reports/runs.jsonl", recs)
        write(repo, ".factory/reports/fix-issues/fates.tsv", [], raw=fates)
        return run(home=tempfile.gettempdir() + "/none", repo=repo)

    def test_review_agreement_and_merge_rates_follow_the_newest_fate(self):
        def item(n, verdicts, scope):
            return {"outcome": "fixed", "pr": f"https://github.com/o/r/pull/{n}", "scope": scope,
                    "reviews": [{"verdict": v} for v in verdicts]}
        items = [item(1, ["approve", "approve"], "minimal"), item(2, ["approve", "changes"], "refactor"),
                 item(3, ["approve"], "minimal"), item(4, ["approve"], "refactor"), item(5, ["approve"], "minimal"),
                 item(6, [], "minimal"), item(1, ["approve", "approve"], "minimal")]
        u = "https://github.com/o/r/pull/"
        fates = (f"{u}1 open 0 - t\n{u}1 merged 0 {'a' * 40} t\n{u}2 closed 1 - t\n{u}3 factory-merged 0 {'b' * 40} t\n"
                 f"{u}4 reverted 0 {'c' * 40} t\n{u}6 merged 0 {'d' * 40} t\n{u}9 merged 0 - t\nbad row\n")
        report = self.runs([{"entry": "issue-pipeline", "outcome": "ok", "items": items}], fates)
        self.assertIn("Review: approved 4 of 5 reviewed PRs; human outcome known for 3, agreeing 2; misses 1 "
                      "(approved, then closed or reverted). Merged of resolved PRs: minimal 3 of 3, refactor 0 of 2.", report)

    def test_corrupt_counters_and_scope_do_not_abort_or_reach_the_totals(self):
        bad = {"entry": "e", "outcome": "ok", "cost_usd": float("nan"), "turns": -4, "weighted_lines": float("inf"),
               "test_changes": float("nan"), "items": [{"pr": "https://github.com/o/r/pull/1", "scope": ["minimal"],
                                                        "reviews": [{"verdict": "approve"}]}]}
        report = self.runs([bad, {"entry": "e", "outcome": "ok", "cost_usd": 0.5, "turns": 3}])
        self.assertIn("| e | 2 | ok 2 | 3 |", report)
        self.assertIn("| 0.50 |", report)
        self.assertIn("Turns reported by 1, tokens by 0, cost by 1.", report)
        self.assertNotIn("nan", report)

    def test_runs_missing_a_calls_cost_are_noted(self):
        report = self.runs([{"entry": "e", "outcome": "ok", "cost_usd": 0.5, "cost_complete": False},
                            {"entry": "e", "outcome": "ok", "cost_usd": 0.25, "cost_complete": True}])
        self.assertIn("| 0.75 |", report)
        self.assertIn("cost by 2 (1 missing a call's cost).", report)

    def test_a_run_with_no_reported_cost_is_not_called_partial(self):
        report = self.runs([{"entry": "e", "outcome": "ok", "cost_usd": None, "cost_complete": False}])
        self.assertIn("cost by 0.", report)
        self.assertNotIn("missing a call's cost", report)


class RobustnessTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)

    def test_unreadable_transcript_is_skipped_without_path(self):
        os.makedirs(os.path.join(self.home, ".claude/projects/-work-demo/dir.jsonl"))
        locked = write(self.home, ".claude/projects/-work-demo/locked.jsonl", [claude_msg("m", 1)])
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o600)
        report = run(home=self.home)
        self.assertNotIn(self.home, report)
        if not os.access(locked, os.R_OK):
            self.assertIn("1 unreadable transcript files skipped", report)

    def test_scope_normalizes_cwd_and_checks_children(self):
        write(self.home, ".codex/sessions/a/rollout-1.jsonl",
              [{"type": "session_meta", "payload": {"id": "c", "cwd": REPO + "/../demo-other"}}])
        write(self.home, ".claude/projects/-work-demo/p.jsonl", [claude_msg("m1", 1)])
        write(self.home, ".claude/projects/-work-demo/p/subagents/a.jsonl", [claude_msg("m2", 42, cwd="/elsewhere")])
        report = run(home=self.home)
        self.assertIn("| Sessions | 1 | not found |", report)
        self.assertIn("| Input tokens (uncached) | 1 |", report)

    def test_symlinked_repo_alias_is_in_scope(self):
        real = os.path.join(self.home, "real")
        alias = os.path.join(self.home, "alias")
        os.makedirs(real)
        os.symlink(real, alias)
        for i, path in enumerate((alias, real)):
            enc = re.sub(r"[^A-Za-z0-9]", "-", path)
            write(self.home, f".claude/projects/{enc}/s.jsonl", [claude_msg("m", 1, cwd=path, sid=str(i))])
        write(self.home, ".codex/sessions/a/rollout-1.jsonl", [{"type": "session_meta", "payload": {"id": "c", "cwd": real}}])
        self.assertIn("| Sessions | 2 | 1 |", run(home=self.home, repo=alias))

    def test_empty_invalid_and_mistyped_records(self):
        write(self.home, ".claude/projects/-work-demo/empty.jsonl", [])
        write(self.home, ".claude/projects/-work-demo/bad.jsonl", [], raw="{bad\n")
        write(self.home, ".cursor/projects/work-demo/agent-transcripts/e/e.jsonl", [], raw="{bad\n")
        self.assertIn("| Sessions | not found | not found | not found |", run(home=self.home))
        write(self.home, ".claude/projects/-work-demo/t.jsonl",
              [claude_msg("m", 1, content=[{"type": "tool_use", "id": "t", "name": {"x": 1}}])])
        self.assertIn("| Tool calls | 1 |", run(home=self.home))

    def test_session_split_across_files_counts_once(self):
        for name, cost in (("a", 2.0), ("b", 3.0)):
            write(self.home, f".claude/projects/-work-demo/{name}.jsonl",
                  [claude_msg("m", 1, sid="S"), {"type": "cost-state", "sessionId": "S", "totalCostUSD": cost}])
            write(self.home, f".codex/sessions/{name}/rollout-1.jsonl",
                  [{"type": "session_meta", "payload": {"id": "C", "cwd": REPO}}])
        report = run(home=self.home)
        self.assertIn("| Sessions | 1 | 1 |", report)
        self.assertIn("| Cost, USD (harness estimate) | 3.00 |", report)

    def test_missing_counters_are_unavailable_not_zero(self):
        write(self.home, ".claude/projects/-work-demo/s.jsonl", [{"type": "user", "cwd": REPO, "sessionId": "s"}])
        report = run(home=self.home)
        self.assertIn("| Input tokens (uncached) | unavailable |", report)
        self.assertIn("| Cost, USD (harness estimate) | unavailable |", report)
        self.assertIn("Unavailable: cost, tokens.", report)

    def test_url_link_wins_and_ambiguous_or_fork_branch_does_not_link(self):
        write(self.home, ".claude/projects/-work-demo/a.jsonl",
              [{"type": "user", "cwd": REPO, "sessionId": "a", "gitBranch": "solo"}, {"type": "pr-link", "prUrl": "u/1"}])
        write(self.home, ".claude/projects/-work-demo/b.jsonl",
              [{"type": "user", "cwd": REPO, "sessionId": "b", "gitBranch": "dup"}])
        write(self.home, ".claude/projects/-work-demo/c.jsonl",
              [{"type": "user", "cwd": REPO, "sessionId": "c", "gitBranch": "fork"}])
        merged = [{"url": "u/1", "headRefName": "x", "isCrossRepository": False},
                  {"url": "u/2", "headRefName": "dup", "isCrossRepository": False},
                  {"url": "u/3", "headRefName": "dup", "isCrossRepository": False},
                  {"url": "u/4", "headRefName": "fork", "isCrossRepository": True},
                  {"url": "u/5", "headRefName": "solo", "isCrossRepository": False}]
        path = write(self.home, "merged.json", [], raw=json.dumps(merged))
        report = run("--merged", path, home=self.home)
        self.assertIn("with an explicitly linked session: 1.", report)
        self.assertIn("(PR URL, else a unique same-repo head branch): 1.", report)

    def test_vanishing_file_during_period_scan_does_not_leak_path(self):
        write(self.home, ".claude/projects/-work-demo/s.jsonl", [claude_msg("m", 1)])

        def gone(path):
            raise FileNotFoundError(2, "No such file", path)

        with unittest.mock.patch.object(aa.os.path, "getmtime", gone):
            report = run("--since", "2000-01-01", home=self.home)
        self.assertNotIn(self.home, report)
        self.assertIn("1 unreadable transcript files skipped", report)

    def test_symlink_inside_repo_to_outside_is_out_of_scope(self):
        repo, outside = os.path.join(self.home, "repo"), os.path.join(self.home, "outside")
        os.makedirs(repo)
        os.makedirs(outside)
        os.symlink(outside, os.path.join(repo, "link"))
        write(self.home, ".codex/sessions/a/rollout-1.jsonl",
              [{"type": "session_meta", "payload": {"id": "c", "cwd": os.path.join(repo, "link")}}])
        self.assertIn("| Sessions | not found | not found |", run(home=self.home, repo=repo))

    def test_default_repo_uses_logical_pwd_of_symlinked_checkout(self):
        real, alias = os.path.join(self.home, "real"), os.path.join(self.home, "alias")
        os.makedirs(real)
        os.symlink(real, alias)
        enc = re.sub(r"[^A-Za-z0-9]", "-", alias)
        write(self.home, f".claude/projects/{enc}/s.jsonl", [claude_msg("m", 1, cwd=alias)])
        old = os.getcwd()
        os.chdir(alias)
        self.addCleanup(os.chdir, old)
        with unittest.mock.patch.dict(os.environ, {"PWD": alias}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                aa.main(["--home", self.home])
        self.assertIn("| Sessions | 1 |", out.getvalue())

    def test_malformed_codex_meta_and_nul_cwd_do_not_abort(self):
        write(self.home, ".codex/sessions/a/rollout-1.jsonl",
              [{"type": "session_meta", "payload": {"id": "c", "cwd": REPO, "thread_source": {}}}])
        write(self.home, ".codex/sessions/b/rollout-1.jsonl",
              [{"type": "session_meta", "payload": {"id": "d", "cwd": REPO + "/\u0000x"}}])
        self.assertIn("| Sessions | not found | 1 |", run(home=self.home))

    def test_empty_or_missing_usage_is_unavailable(self):
        msg = claude_msg("m", 1)
        msg["message"]["usage"] = {}
        write(self.home, ".claude/projects/-work-demo/s.jsonl", [msg])
        write(self.home, ".codex/sessions/a/rollout-1.jsonl",
              [{"type": "session_meta", "payload": {"id": "c", "cwd": REPO}},
               {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {}}}}])
        write(self.home, ".codex/sessions/b/rollout-1.jsonl", [{"type": "session_meta", "payload": {"id": "d", "cwd": REPO}}])
        self.assertIn("| Input tokens (uncached) | unavailable | unavailable |", run(home=self.home))


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)

    def test_codex_reads_archived_sessions_and_codex_home_once_per_session(self):
        meta = {"type": "session_meta", "payload": {"id": "c", "cwd": REPO}}
        usage = {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
            "input_tokens": 5, "output_tokens": 2, "total_tokens": 7}}}}
        write(self.home, ".codex/sessions/a/rollout-1.jsonl", [meta, usage])
        write(self.home, ".codex/archived_sessions/rollout-1.jsonl", [meta, usage])
        write(self.home, "alt/archived_sessions/rollout-2.jsonl",
              [{"type": "session_meta", "payload": {"id": "d", "cwd": REPO}}, usage])
        with unittest.mock.patch.dict(os.environ, {"CODEX_HOME": os.path.join(self.home, "alt")}):
            s = aa.codex(self.home, REPO, None)
        self.assertEqual((s["sessions"], s["input"], s["output"]), (2, 10, 4))

    def test_claude_config_dir_is_read_and_deduped_with_default(self):
        for config in (".claude", "alt"):
            write(self.home, f"{config}/projects/-work-demo/s.jsonl", [claude_msg("m", 3, sid="S")])
            write(self.home, f"{config}/projects/-work-demo/s/subagents/a.jsonl", [claude_msg("n", 4, sid="S")])
        write(self.home, "alt/projects/-work-demo/t.jsonl", [claude_msg("o", 5, sid="T")])
        with unittest.mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": os.path.join(self.home, "alt")}):
            s = aa.claude(self.home, REPO, None)
        self.assertEqual((s["sessions"], s["subagents"], s["input"]), (2, 1, 12))

    def test_claude_session_moved_into_repo_counts_only_in_its_exact_dir(self):
        moved = [claude_msg("m", 1, cwd="/scratch/x", sid="a"), claude_msg("n", 2, sid="a")]
        write(self.home, ".claude/projects/-work-demo/a.jsonl", moved)
        write(self.home, ".claude/projects/-work-demo-x/b.jsonl",
              [claude_msg("o", 4, cwd="/work/demo-x", sid="b"), claude_msg("p", 8, sid="b")])
        s = aa.claude(self.home, REPO, None)
        self.assertEqual((s["sessions"], s["input"]), (1, 3))

    def test_antigravity_counts_repo_conversations_once_across_roots(self):
        t3 = ".t3/userdata/providers/antigravity/h/antigravity-acp/conversations"
        agy_db(self.home, f"{t3}/a.db", "file:///work/demo", [(10, 3, 20), (1, 1, 0)])
        agy_db(self.home, ".gemini/antigravity-cli/conversations/a.db", "file:///work/demo", [(10, 3, 20), (1, 1, 0)])
        agy_db(self.home, f"{t3}/b.db", "file:///work/demo/sub%20dir", [(5, 1, 0)])
        agy_db(self.home, f"{t3}/c.db", "file:///work/demo-other", [(99, 99, 99)])
        write(self.home, f"{t3}/d.db", [], raw="not sqlite")
        s = aa.antigravity(self.home, REPO, None)
        self.assertEqual((s["sessions"], s["input"], s["cache_read"], s["output"]), (2, 16, 20, 5))
        self.assertEqual(s["unreadable"], 1)
        report = run(home=self.home)
        self.assertNotIn(self.home, report)
        self.assertIn("| Metric | Claude Code | Codex | Cursor | Antigravity | Total |", report)
        self.assertIn("| Sessions | not found | not found | not found | 2 | 2 |", report)
        self.assertIn("| Tool calls | not found | not found | not found | unavailable | unavailable |", report)
        self.assertNotIn("Antigravity |", run())


    def test_antigravity_reads_commits_still_in_the_wal_and_writes_nothing_beside_the_database(self):
        d = ".gemini/antigravity-cli/conversations"
        path = agy_db(self.home, f"{d}/a.db", "file:///work/demo", [(10, 3, 0)])
        idle = agy_db(self.home, f"{d}/b.db", "file:///work/demo", [(1, 1, 0)])
        writer = sqlite3.connect(path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO gen_metadata VALUES (?, ?)", (1, pb(1, pb(4, pb(2, 5) + pb(3, 2)))))
        writer.commit()
        os.utime(path, (1, 1))
        os.utime(idle, (1, 1))
        # A WAL emptied by a checkpoint holds nothing new, whatever its mtime.
        open(idle + "-wal", "w").close()

        def beside():
            names = sorted(os.listdir(os.path.dirname(path)))
            return [(n, os.stat(os.path.join(os.path.dirname(path), n)).st_mtime_ns) for n in names]

        before = beside()
        s = aa.antigravity(self.home, REPO, 1000)
        self.assertEqual((s["sessions"], s["input"], s["output"], s["unreadable"]), (1, 15, 5, 0))
        self.assertEqual(aa.antigravity(self.home, REPO, None)["sessions"], 2)
        self.assertEqual(beside(), before)
        self.assertIn("| Subagent transcripts | not found | not found | not found | unavailable |", run(home=self.home))

    def test_codex_child_marked_only_by_native_source_is_a_subagent(self):
        write(self.home, ".codex/sessions/a/rollout-1.jsonl", [{"type": "session_meta", "payload": {
            "id": "c", "cwd": REPO, "source": {"subagent": {"thread_spawn": {"depth": 1}}}}}])
        write(self.home, ".codex/sessions/a/rollout-2.jsonl",
              [{"type": "session_meta", "payload": {"id": "p", "cwd": REPO, "source": "vscode"}}])
        s = aa.codex(self.home, REPO, None)
        self.assertEqual((s["sessions"], s["subagents"]), (1, 1))

    def test_claude_session_is_in_the_period_when_any_of_its_transcripts_is(self):
        for sid, old in (("a", "a/subagents/x.jsonl"), ("b", "b.jsonl"), ("c", None)):
            write(self.home, f".claude/projects/-work-demo/{sid}.jsonl", [claude_msg(f"m{sid}", 1, sid=sid)])
            write(self.home, f".claude/projects/-work-demo/{sid}/subagents/x.jsonl", [claude_msg(f"n{sid}", 10, sid=sid)])
            for rel in (old,) if old else (f"{sid}.jsonl", f"{sid}/subagents/x.jsonl"):
                os.utime(os.path.join(self.home, ".claude/projects/-work-demo", rel), (1, 1))
        s = aa.claude(self.home, REPO, 1000)
        self.assertEqual((s["sessions"], s["subagents"], s["input"]), (2, 2, 22))

    def test_cursor_transcript_under_both_checkout_aliases_counts_once(self):
        real = os.path.join(self.home, "real")
        os.makedirs(real)
        alias = os.path.join(self.home, "alias")
        os.symlink(real, alias)
        use = {"role": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}}
        for root, recs in ((real, [use]), (alias, [use, use])):
            enc = re.sub(r"[^A-Za-z0-9]+", "-", root).strip("-")
            write(self.home, f".cursor/projects/{enc}/agent-transcripts/s/s.jsonl", recs)
        s = aa.cursor(self.home, alias, None)
        self.assertEqual((s["sessions"], s["tool_calls"]), (1, 2))


class DriftTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)

    def main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = aa.main(["--home", self.home, "--repo", REPO])
        return code, out.getvalue()

    def sessions(self, result):
        for i in range(aa.DRIFT_MIN_SESSIONS):
            use = {"type": "tool_use", "id": f"t{i}", "name": "Bash"}
            user = {"type": "user", "cwd": REPO, "sessionId": str(i), "message": {"content": [result(f"t{i}")]}}
            write(self.home, f".claude/projects/-work-demo/{i}.jsonl", [claude_msg(f"m{i}", 1, sid=str(i), content=[use]), user])

    def test_renamed_field_is_drift_and_unverified(self):
        self.sessions(lambda tid: {"type": "tool_result", "tool_use_id": tid, "isError": True})
        code, report = self.main()
        self.assertEqual(code, aa.DRIFT_EXIT)
        self.assertIn("## Format drift", report)
        self.assertIn("- Claude Code: no tool_result.is_error flags in 5 sessions; format may have changed. Unverified: failed.", report)
        self.assertIn("| Failed tool calls | unverified |", report)
        self.assertIn("| Tool calls | 5 |", report)

    def test_expected_shapes_are_not_drift(self):
        self.sessions(lambda tid: {"type": "tool_result", "tool_use_id": tid, "is_error": False})
        code, report = self.main()
        self.assertEqual(code, 0)
        self.assertNotIn("Format drift", report)
        self.assertIn("| Failed tool calls | 0 |", report)
        self.home = HOME
        self.assertEqual(self.main()[0], 0)

    def test_shape_prints_structure_without_values(self):
        path = write(self.home, "t.jsonl", [
            {"type": "privateword", "SECRET key": 1, "message": {"content": [
                {"type": "tool_use", "input": {"secretkey": "SECRET"}},
                {"type": "tool_result", "content": "SECRET", "is_error": False}]}},
            {"type": "assistant", "toolUseResult": {"secretkey": 1}, "x": {"/SECRET/path": 2}},
            {"type": "event_msg", "payload": {"item": {"result": {"structuredContent": {"SECRETFILE": 1}}}}}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(aa.main(["--shape", path]), 0)
        self.assertNotIn("SECRET", out.getvalue())
        token = write(self.home, "k.jsonl", [{"type": "assistant", "message": {"usage": {
            "ghp_" + "a" * 30: 1, "AKIAABCDEFGHIJKLMNOP": 2, "cache_creation_input_tokens": 3, "totalCostUSD": 4}}}])
        keys = io.StringIO()
        with contextlib.redirect_stdout(keys):
            aa.main(["--shape", token])
        self.assertEqual(json.loads(keys.getvalue())["message"]["usage"],
                         {"?": "int", "cache_creation_input_tokens": "int", "totalCostUSD": "int"})
        self.assertNotIn("SECRET", out.getvalue())
        self.assertNotIn("privateword", out.getvalue())
        self.assertNotIn("secretkey", out.getvalue())
        self.assertIn('"is_error": "bool"', out.getvalue())
        self.assertIn('"type": "?"', out.getvalue())


if __name__ == "__main__":
    unittest.main()
