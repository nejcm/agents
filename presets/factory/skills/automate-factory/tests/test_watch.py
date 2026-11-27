import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import time
import unittest

import test_run

SETTINGS = 'trigger="" daily_cap=6 window="" notify=()\n'
DETECT = r"""detect() {
  echo detect >> "$LOG"
  [ -z "${DETECT_FAIL:-}" ] || false
  [ -z "${SEEN:-}" ] || seen "$SEEN" done
  [ ! -f "$EVENTS" ] || cat "$EVENTS"
}
"""
CLAUDE = r"""#!/usr/bin/env bash
echo claude >> "$LOG"
[ -z "${RESIST:-}" ] || trap '' TERM
[ -z "${HOLD:-}" ] || for _ in $(seq 600); do [ ! -e "$HOLD" ] || break; sleep 0.1; done
[ -z "${SLOW:-}" ] || sleep 1
[ -z "${BREAK:-}" ] || { rm -f "$BREAK"; mkdir "$BREAK"; }
[ -z "${FAIL:-}" ] || exit 1
echo report
"""
GIT = """#!/bin/sh
[ "$1" != archive ] || echo "git archive" >> "$LOG"
exec {git} "$@"
"""
NOTIFY = """#!/bin/sh
printf '%s|' "$@" >> "$LOG.notify"
echo >> "$LOG.notify"
[ -z "${NOTIFY_HOLD:-}" ] || for _ in $(seq 600); do [ ! -e "$NOTIFY_HOLD" ] || break; sleep 0.1; done
exit 3
"""


def utc(t):
    return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tz_near_noon():
    now = datetime.datetime.now(datetime.timezone.utc)
    o = 12 * 60 - (now.hour * 60 + now.minute)
    return f"FAK{'-' if o >= 0 else '+'}{abs(o) // 60:02d}:{abs(o) % 60:02d}", now + datetime.timedelta(minutes=o)


class WatchTest(unittest.TestCase):
    setUp_repo = test_run.RunShTest.setUp
    tearDown = test_run.RunShTest.tearDown
    git = test_run.RunShTest.git
    write = test_run.RunShTest.write
    calls = test_run.RunShTest.calls

    def setUp(self):
        real_git = shutil.which("git")
        self.setUp_repo()
        for name, body in (("claude", CLAUDE), ("git", GIT.format(git=real_git)), ("notify", NOTIFY)):
            with open(f"{self.tmp.name}/bin/{name}", "w") as f:
                f.write(body)
            os.chmod(f"{self.tmp.name}/bin/{name}", 0o755)
        self.out = f"{self.repo}/.factory/reports/e"
        self.path = f"{self.repo}/.factory/automations/e.sh"
        self.events_file = f"{self.tmp.name}/events"

    def tick(self, events=None, cap="6", window="", dry=False, check=False, weekly="", extra=None,
             settings=None, tz=None, level="report", post=None, popen=False):
        if events is not None:
            with open(self.events_file, "w") as f:
                f.write(events)
        with open(test_run.RUN_SH) as f:
            script = f.read()
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1", "<level>": level,
                     "<weekly usd>": weekly}.items():
            script = script.replace(k, v)
        self.assertIn(SETTINGS, script)
        if settings is None:
            settings = f'trigger=watch daily_cap={cap} window="{window}" notify=(notify)\n' + DETECT
        script = script.replace(SETTINGS, settings)
        if post:
            script = script.replace("post() { :; }", post)
        with open(self.path, "w") as f:
            f.write(script)
        os.chmod(self.path, 0o755)
        env = dict(self.env, EVENTS=self.events_file, **(extra or {}))
        if dry:
            env["FACTORY_DRY_RUN"] = "1"
        if check:
            env["FACTORY_CHECK_MODELS"] = "1"
        if tz:
            env["TZ"] = tz
        if popen:
            return subprocess.Popen([self.path], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    start_new_session=True)
        return subprocess.run([self.path], env=env, capture_output=True, text=True, timeout=120, start_new_session=True)

    def records(self):
        p = f"{self.repo}/.factory/reports/runs.jsonl"
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [json.loads(x) for x in f]

    def count(self, what):
        return self.calls().count(what)

    def seen(self):
        p = f"{self.out}/seen.tsv"
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [x.split("\t")[:3] for x in f.read().splitlines()]

    def day_report(self):
        p = f"{self.out}/{datetime.date.today()}.md"
        if not os.path.exists(p):
            return ""
        with open(p) as f:
            return f.read()

    def lock(self):
        return f"{self.repo}/.factory/tmp/e.lock"

    def lock_pid(self):
        with open(self.lock()) as f:
            return f.read().strip()

    def hold_lock(self, pid):
        os.makedirs(os.path.dirname(self.lock()), exist_ok=True)
        with open(self.lock(), "w") as f:
            f.write(f"{pid}\n")

    def dead_pid(self):
        p = subprocess.Popen(["true"])
        p.wait()
        return p.pid

    def test_quiet_tick_writes_nothing_and_skips_budget_and_snapshot(self):
        now = utc(datetime.datetime.now(datetime.timezone.utc))
        self.write(".factory/reports/runs.jsonl", json.dumps({"entry": "x", "started": now, "cost_usd": 9}) + "\n")
        r = self.tick("", weekly="5")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.calls(), ["detect"])
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(os.listdir(self.out), [])
        self.assertEqual(sorted(os.listdir(f"{self.repo}/.factory/tmp")), [".gitignore", "e.lock"])
        self.assertEqual(self.lock_pid(), "")

    def test_a_fire_records_once_settles_its_events_and_notifies(self):
        r = self.tick("abc123 101\nabc123 102\nother 9\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.count("claude"), self.count("git archive")), (1, 1))
        [rec] = self.records()
        self.assertEqual((rec["trigger"], rec["events"], rec["outcome"]), ("watch", ["101", "102"], "completed"))
        with open(f"{self.out}/{datetime.date.today()}-abc123.md") as f:
            self.assertEqual(f.read(), "report\n")
        self.assertEqual(self.seen(), [["101", "failed", "-"], ["102", "failed", "-"], ["101", "done", "-"],
                                       ["102", "done", "-"]])
        with open(self.log + ".notify") as f:
            self.assertEqual(f.read(), "e: abc123 completed|\n")
        self.assertIn("notify: exit 3", r.stderr)
        self.assertEqual(self.lock_pid(), "")
        r = self.tick()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.records()[-1]["events"], ["9"])
        r = self.tick()
        self.assertEqual((r.returncode, r.stdout, self.count("claude"), len(self.records())), (0, "", 2, 2))

    def test_a_changed_value_fires_again(self):
        self.tick("pr-1-aaa pr-1 h1\n")
        r = self.tick("pr-1-bbb pr-1 h2\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x["events"] for x in self.records()], [["pr-1"], ["pr-1"]])
        self.assertEqual(self.seen()[-1], ["pr-1", "done", "h2"])

    def test_a_second_fire_with_the_same_name_keeps_the_first_report(self):
        self.tick("pr-1-aaa pr-1 h1\n")
        r = self.tick("pr-1-aaa pr-1 h2\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        day = datetime.date.today()
        self.assertEqual(sorted(f for f in os.listdir(self.out) if f.startswith(f"{day}-")),
                         [f"{day}-pr-1-aaa-2.md", f"{day}-pr-1-aaa.md"])

    def test_a_live_lock_is_silent_and_fails_a_dry_run_loudly(self):
        self.hold_lock(os.getpid())
        r = self.tick("a 1\n")
        self.assertEqual((r.returncode, r.stdout, r.stderr, self.calls(), self.records()), (0, "", "", [], []))
        r = self.tick(dry=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"gate: lock .factory/tmp/e.lock is held by PID {os.getpid()}", r.stderr)
        self.assertEqual(self.records()[-1]["outcome"], "blocked")
        r = self.tick(check=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"gate: lock .factory/tmp/e.lock is held by PID {os.getpid()}", r.stderr)
        self.assertEqual((self.lock_pid(), self.count("claude")), (str(os.getpid()), 0))

    def test_a_stale_lock_is_taken_over(self):
        pid = self.dead_pid()
        self.hold_lock(pid)
        r = self.tick("a 1\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], f"lock: took over from gone PID {pid}")
        self.assertEqual((self.count("claude"), self.lock_pid()), (1, ""))

    def test_concurrent_ticks_fire_once(self):
        ps = [self.tick("a 1\n", extra={"SLOW": "1"}, popen=True) for _ in range(6)]
        outs = [p.communicate(timeout=120) + (p.returncode,) for p in ps]
        self.assertEqual([o[2] for o in outs], [0] * 6, outs)
        self.assertEqual((self.count("claude"), len(self.records())), (1, 1))
        self.assertEqual(self.seen(), [["1", "failed", "-"], ["1", "done", "-"]])

    def test_the_lock_owner_is_read_and_written_only_under_flock(self):
        import fcntl
        self.hold_lock(self.dead_pid())
        with open(self.lock(), "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            p = self.tick("a 1\n", popen=True)
            subprocess.run(["sleep", "2"])
            f.truncate(0)
            f.write(f"{os.getpid()}\n")
            f.flush()
        out, err = p.communicate(timeout=120)
        self.assertEqual((p.returncode, out, err, self.calls()), (0, "", "", []))
        self.assertEqual(self.lock_pid(), str(os.getpid()))

    def test_ticks_while_a_fire_runs_are_silent(self):
        hold = f"{self.tmp.name}/release"
        holder = self.tick("a 1\n", extra={"HOLD": hold}, popen=True)
        for _ in range(600):
            if self.count("claude"):
                break
            subprocess.run(["sleep", "0.1"])
        ps = [self.tick("b 2\n", popen=True) for _ in range(4)]
        outs = [p.communicate(timeout=120) + (p.returncode,) for p in ps]
        self.assertEqual(outs, [("", "", 0)] * 4)
        open(hold, "w").close()
        out, err = holder.communicate(timeout=120)
        self.assertEqual(holder.returncode, 0, err)
        self.assertEqual((self.count("claude"), self.count("detect"), self.lock_pid()), (1, 1, ""))

    def held_fire(self, hold, **extra):
        p = self.tick("a 1\n", extra={"HOLD": hold, **extra}, popen=True)
        for _ in range(600):
            if self.count("claude"):
                break
            subprocess.run(["sleep", "0.1"])
        return p

    def test_a_sigterm_mid_fire_records_a_failure_and_settles_nothing(self):
        # systemd signals the whole cgroup, launchd (kill or bootout) only the script, mid-call.
        for name, send, extra in (("group", os.killpg, {}), ("script", os.kill, {}),
                                  ("script, call ignores TERM", os.kill, {"RESIST": "1"})):
            with self.subTest(name):
                shutil.rmtree(f"{self.repo}/.factory/reports", ignore_errors=True)
                for f in (self.log, self.log + ".notify"):
                    open(f, "w").close()
                p = self.held_fire(f"{self.tmp.name}/never", **extra)
                sent = time.monotonic()
                send(p.pid, signal.SIGTERM)
                p.communicate(timeout=10)
                self.assertEqual(p.returncode, 143)
                self.assertLess(time.monotonic() - sent, 5, "launchd kills the script 5 seconds after its TERM")
                [rec] = self.records()
                self.assertEqual((rec["outcome"], rec["exit_code"]), ("failed", 143))
                self.assertEqual(self.seen(), [["1", "failed", "-"]])
                with open(self.log + ".notify") as f:
                    self.assertEqual(f.read(), "e: a failed|\n")
                self.assertEqual(self.lock_pid(), "")
                for _ in range(50):
                    if subprocess.run(["pgrep", "-f", f"{self.tmp.name}/bin/claude"]).returncode:
                        break
                    subprocess.run(["sleep", "0.1"])
                else:
                    self.fail("the model call outlived the script")

    def test_a_second_sigterm_during_cleanup_still_releases_the_lock(self):
        release = f"{self.tmp.name}/release"
        p = self.tick("a 1\n", extra={"HOLD": f"{self.tmp.name}/never", "NOTIFY_HOLD": release}, popen=True)
        def wait_for(ready):
            for _ in range(600):
                if ready():
                    return
                subprocess.run(["sleep", "0.1"])
            self.fail("timed out waiting for the run")
        wait_for(lambda: self.count("claude"))
        os.killpg(p.pid, signal.SIGTERM)
        wait_for(lambda: os.path.exists(self.log + ".notify"))
        subprocess.run(["kill", "-TERM", str(p.pid)])
        open(release, "w").close()
        p.communicate(timeout=120)
        self.assertEqual(p.returncode, 143)
        self.assertEqual(self.lock_pid(), "")

    def test_a_kill_mid_fire_counts_an_attempt_and_three_failures_give_up(self):
        hold = f"{self.tmp.name}/release"
        p = self.held_fire(hold)
        os.kill(p.pid, signal.SIGKILL)
        open(hold, "w").close()
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, -9)
        self.assertEqual(self.seen(), [["1", "failed", "-"]])
        self.assertTrue(self.lock_pid())
        for n in range(2):
            r = self.tick(extra={"FAIL": "1"})
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual("lock: took over from gone PID" in r.stdout, n == 0)
        self.assertEqual(self.seen(), [["1", "failed", "-"]] * 3)
        self.assertEqual([x["outcome"] for x in self.records()], ["failed", "failed"])
        r = self.tick()
        self.assertEqual((r.returncode, r.stdout), (0, "given-up: 1 after 3 failed attempts\n"))
        self.assertEqual((self.count("claude"), len(self.records())), (3, 2))
        self.assertEqual(self.seen()[-1], ["1", "given-up", "-"])
        self.assertEqual(self.day_report(), "given-up: 1 after 3 failed attempts\n")
        r = self.tick()
        self.assertEqual((r.returncode, r.stdout, self.count("claude")), (0, "", 3))

    def test_window_opens_by_local_day_and_time_with_the_end_excluded(self):
        tz, local = tz_near_noon()
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        today, prev, nxt = (days[(local.weekday() + i) % 7] for i in (0, -1, 1))

        def hm(minutes):
            return (local + datetime.timedelta(minutes=minutes)).strftime("%H:%M")
        for window, opens in ((f"daily {hm(-60)}-{hm(60)}", True), (f"daily {hm(0)}-{hm(60)}", True),
                              (f"daily {hm(-60)}-{hm(0)}", False), (f"daily {hm(30)}-{hm(60)}", False),
                              (f"{prev}-{nxt} {hm(-60)}-{hm(60)}", True), (f"{nxt}-{prev} {hm(-60)}-{hm(60)}", False),
                              (f"{nxt},{today} {hm(-60)}-{hm(60)}", True), (f"{nxt},{prev} {hm(-60)}-{hm(60)}", False)):
            with self.subTest(window):
                before = self.count("detect")
                r = self.tick("", window=window, tz=tz)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
                self.assertEqual(self.count("detect") - before, int(opens))
        for window, msg in (("mon-fri 9:00-18:00", "is not <days> HH:MM-HH:MM"), ("daily 18:00-09:00", "ends before it starts"),
                            ("mon-funday 09:00-18:00", "is not <days> HH:MM-HH:MM"), ("mon-xyz 09:00-18:00", "day mon-xyz")):
            with self.subTest(window):
                r = self.tick("", window=window)
                self.assertEqual(r.returncode, 1)
                self.assertIn(msg, r.stderr)

    def test_the_daily_cap_counts_local_days_and_reports_once(self):
        tz = "FAK-14"
        local = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=14)))
        if (local.hour, local.minute) in ((0, 0), (23, 59)):
            self.skipTest("too close to local midnight")
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        rec = dict(entry="e", trigger="watch", dry_run=False, events=["x"])
        rows = [dict(rec, started=utc(midnight + datetime.timedelta(minutes=1))),
                dict(rec, started=utc(midnight - datetime.timedelta(minutes=1))),
                dict(rec, started=utc(midnight - datetime.timedelta(minutes=2))),
                dict(rec, started=utc(local), dry_run=True),
                dict(rec, started=utc(local), events=None, reason="detect-error"),
                dict(rec, started=utc(local), entry="other")]
        self.write(".factory/reports/runs.jsonl", "".join(json.dumps(x) + "\n" for x in rows))
        r = self.tick("a 1\n", cap="2", tz=tz)
        self.assertEqual((r.returncode, self.count("claude")), (0, 1), r.stderr)
        report = f"{self.out}/{local.date()}.md"
        for n in (1, 2):
            r = self.tick("b 2\n", cap="2", tz=tz)
            self.assertEqual((r.returncode, r.stdout, self.count("claude")), (0, "" if n == 2 else "daily fire cap reached: 2\n", 1))
        with open(report) as f:
            self.assertEqual(f.read(), "daily fire cap reached: 2\n")
        self.assertEqual(len(self.records()), len(rows) + 1)

    def test_a_detect_error_is_recorded_at_most_hourly(self):
        r = self.tick(extra={"DETECT_FAIL": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("detect: failed, exit 1", r.stderr)
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["reason"], rec["trigger"], rec["calls"]), ("failed", "detect-error", "watch", 0))
        r = self.tick(extra={"DETECT_FAIL": "1"})
        self.assertEqual((r.returncode, r.stdout, r.stderr, len(self.records())), (0, "", "", 1))
        r = self.tick(dry=True, extra={"DETECT_FAIL": "1"})
        self.assertEqual((r.returncode, len(self.records())), (1, 2))
        rec["started"] = utc(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=61))
        self.write(".factory/reports/runs.jsonl", json.dumps(rec) + "\n")
        r = self.tick(extra={"DETECT_FAIL": "1"})
        self.assertEqual((r.returncode, len(self.records())), (1, 2))
        self.assertEqual(self.count("claude"), 0)

    def test_pause_wins(self):
        self.write(".factory/pause", "")
        r = self.tick("a 1\n")
        self.assertEqual((r.returncode, r.stdout, self.calls(), self.records()), (0, "paused\n", [], []))
        self.assertFalse(os.path.exists(self.lock()))

    def test_check_models_and_dry_run_ignore_window_cap_and_ledger(self):
        now = utc(datetime.datetime.now(datetime.timezone.utc))
        self.write(".factory/reports/runs.jsonl",
                   json.dumps(dict(entry="e", trigger="watch", dry_run=False, events=["x"], started=now)) + "\n")
        self.write(".factory/reports/e/seen.tsv", f"1\tdone\t-\t{now}\n")
        closed = "daily 00:00-00:01" if datetime.datetime.now().hour else "daily 23:58-23:59"
        r = self.tick("a 1\n", cap="1", window=closed, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.count("detect"), self.count("claude")), (1, 1))
        self.assertEqual(self.records()[-1]["events"], ["1"])
        self.assertTrue(self.records()[-1]["dry_run"])
        self.assertTrue(os.path.exists(f"{self.out}/{datetime.date.today()}-a.md"))
        self.assertEqual(self.seen(), [["1", "done", "-"]])
        self.assertFalse(os.path.exists(self.log + ".notify"))
        r = self.tick(window=closed, check=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.count("detect"), self.count("claude")), (1, 2))
        r = self.tick("", window=closed, dry=True)
        self.assertEqual((r.returncode, r.stdout), (0, "no event to analyze\n"), r.stderr)
        self.assertTrue(self.records()[-1]["dry_run"])

    def test_watch_without_detect_and_bad_settings_block(self):
        for settings, msg in (('trigger=watch daily_cap=6 window="" notify=()\n', "trigger watch needs an entry with a detect step"),
                              ('trigger=watch daily_cap=0 window="" notify=()\n' + DETECT, "daily_cap 0 is not a positive whole number")):
            with self.subTest(msg):
                r = self.tick("a 1\n", settings=settings)
                self.assertEqual(r.returncode, 1)
                self.assertIn("gate: " + msg, r.stderr)
                self.assertEqual(self.count("claude"), 0)
        r = self.tick("a 1 x y\n")
        self.assertIn("gate: detect printed a line other than <fire> <key> [<value>]", r.stderr)

    def test_security_review_on_watch_blocks_before_any_call(self):
        import test_triggers
        t = test_triggers.TriggerTest("test_schedule_mode_reviews_every_run")
        t.setUp()
        try:
            r = t.run_entry("security-review", "watch", {'"<risk glob>"': '"auth/*"'})
            self.assertEqual(r.returncode, 1)
            self.assertIn("gate: trigger watch needs an entry with a detect step", r.stderr)
            self.assertEqual(t.model_calls(), 0)
        finally:
            t.tearDown()

    def test_watch_job_spec_runs_on_an_interval(self):
        with open(os.path.join(test_run.HERE, "..", "references", "runners.md")) as f:
            text = f.read()
        self.assertIn('`{"kind": "interval", "minutes": <interval>}`', text)
        if not shutil.which("node"):
            return
        [tpl] = re.findall(r"```json\n(.*?)```", text, re.S)
        for k, v in {"<schedule>": '{"kind": "interval", "minutes": 2}', "<repo-root>": "/w/r", "<repo>": "r",
                     "<entry>": "e", "<minutes>": "45"}.items():
            tpl = tpl.replace(k, v)
        r = subprocess.run(["node", test_run.ONCUE, "render", "-", "--backend", "systemd"], input=tpl,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OnCalendar=*:0/2\n", r.stdout)


    def test_an_early_exit_still_records_and_cleans_up(self):
        r = self.tick("a 1\n", weekly="-1")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("command not found", r.stderr)
        self.assertEqual(self.records()[-1]["outcome"], "blocked")
        self.assertEqual(os.listdir(f"{self.repo}/.factory/tmp"), [".gitignore"])

    def test_a_watch_budget_skip_is_recorded_hourly_but_a_dry_run_never_skips_silently(self):
        now = utc(datetime.datetime.now(datetime.timezone.utc))
        self.write(".factory/reports/runs.jsonl", json.dumps({"entry": "x", "started": now, "cost_usd": 9}) + "\n")
        r = self.tick("a 1\n", weekly="5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("weekly budget reached", r.stdout)
        self.assertEqual(self.records()[-1]["reason"], "weekly-budget")
        self.assertEqual(self.seen(), [])
        r = self.tick(weekly="5")
        self.assertEqual((r.returncode, r.stdout, len(self.records())), (0, "", 2))
        r = self.tick(weekly="5", dry=True)
        self.assertIn("weekly budget reached", r.stdout)
        self.assertEqual((r.returncode, len(self.records()), self.records()[-1]["dry_run"]), (0, 3, True))
        self.assertEqual(self.count("claude"), 0)

    def test_a_trigger_typo_blocks(self):
        r = self.tick("a 1\n", settings='trigger=watc daily_cap=6 window="" notify=()\n' + DETECT)
        self.assertEqual(r.returncode, 1)
        self.assertIn("gate: trigger watc is not schedule or changes", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_detect_can_settle_an_event_and_an_unusable_ledger_blocks(self):
        r = self.tick("", extra={"SEEN": "7"})
        self.assertEqual((r.returncode, self.seen()), (0, [["7", "done", "-"]]))
        r = self.tick("a 7\n")
        self.assertEqual((r.returncode, r.stdout, self.count("claude")), (0, "", 0))
        seen = f"{self.out}/seen.tsv"
        os.rename(seen, seen + ".real")
        os.symlink(seen + ".real", seen)
        r = self.tick("a 8\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("seen.tsv is a symlink or not a regular file", r.stderr)
        os.remove(seen)
        os.rename(seen + ".real", seen)
        if os.geteuid() != 0:
            os.chmod(seen, 0)
            r = self.tick("a 8\n")
            os.chmod(seen, 0o644)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(self.count("claude"), 0)

    def test_a_ledger_broken_mid_fire_still_releases_and_cleans_up(self):
        r = self.tick("a 1\n", extra={"BREAK": f"{self.out}/seen.tsv"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("seen: done not written", r.stderr)
        self.assertEqual(self.lock_pid(), "")
        self.assertEqual(sorted(os.listdir(f"{self.repo}/.factory/tmp")), [".gitignore", "e.lock"])

    def test_the_comment_level_posts_the_fire_report(self):
        r = self.tick("a 1\n", level="comment", post='post() { cp "$report_md" "$LOG.posted"; }')
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.log + ".posted") as f:
            self.assertEqual(f.read(), "report\n")
        self.assertFalse(os.path.exists(f"{self.out}/{datetime.date.today()}.md"))


if __name__ == "__main__":
    unittest.main()
