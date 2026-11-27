import datetime
import json
import os
import re
import subprocess
import unittest

import test_run

CATALOG = os.path.join(test_run.HERE, "..", "references", "catalog", "pr-babysitting.md")
SETTINGS = 'trigger="" daily_cap=6 window="" notify=()\n'
GH = r"""#!/usr/bin/env bash
echo "gh $*" >> "$LOG"
case "$1 $2" in
  "api graphql") case "$*" in *rateLimit*) cat "$PAGES" ;; *) echo '{}' ;; esac ;;
  "pr view") case " ${SAME-5} " in *" $3 "*) fork=false ;; *) fork=true ;; esac
    echo "{\"headRefOid\": \"0000000000000000000000000000000000000000\", \"isCrossRepository\": $fork}" ;;
  "pr diff") echo "diff of $3" ;;
  "pr list") printf '%s\n' ${PRLIST:-} ;;
  "pr checks"|"api repos/"*) echo '[]' ;;
esac
"""
CLAUDE = r"""#!/usr/bin/env bash
echo claude >> "$LOG"
find input skills ! -type d | sort > "$LOG.ls"
cat skills/babysit-pr/SKILL.md > "$LOG.skill"
echo report
"""


def blocks():
    with open(CATALOG) as f:
        return [("  " + b).replace("\n  ", "\n").strip() + "\n" for b in re.findall(r"```bash\n(.*?)```", f.read(), re.S)]


def ago(**kw):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(**kw)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def pr(n, sha, rollup="FAILURE", merge="BLOCKED", mergeable="MERGEABLE", draft=False, author="ann", fork=False,
       threads=(), minutes=10):
    return dict(number=n, updatedAt=ago(minutes=minutes), author={"login": author}, isCrossRepository=fork, isDraft=draft,
                headRefOid=sha, headRefName=f"b{n}", mergeable=mergeable, mergeStateStatus=merge,
                statusCheckRollup=rollup and {"state": rollup},
                reviewThreads={"nodes": [{"isResolved": r, "comments": {"nodes": [{"author": {"__typename": t}}]}}
                                         for t, r in threads]})


def page(prs, remaining=5000):
    return {"data": {"rateLimit": {"limit": 5000, "remaining": remaining, "cost": 11},
                     "repository": {"pullRequests": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": prs}}}}


class PrBabysittingTest(unittest.TestCase):
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
        self.write("skills/babysit-pr/SKILL.md", "base skill\n")
        self.git("-C", self.repo, "add", "-A")
        self.git("-C", self.repo, "commit", "-qm", "skill")
        self.write(".factory/automations/pr-babysitting.md", "p\n")
        self.git("-C", self.repo, "push", "-q", self.remote, "main")
        other = f"{self.tmp.name}/other"
        self.git("clone", "-q", "-b", "main", self.remote, other)
        self.git("-C", other, "checkout", "-qb", "b5")
        for path, text in (("skills/babysit-pr/SKILL.md", "head skill\n"), ("pushed.txt", "from the head\n")):
            with open(f"{other}/{path}", "w") as f:
                f.write(text)
        os.symlink("/etc/passwd", f"{other}/link")
        self.git("-C", other, "add", "-A")
        self.git("-C", other, "commit", "-qm", "head")
        self.git("-C", other, "push", "-q", "origin", "b5")
        self.sha = self.git("-C", other, "rev-parse", "HEAD").strip()
        self.other_sha = "b" * 40
        self.out = f"{self.repo}/.factory/reports/pr-babysitting"
        self.pages = f"{self.tmp.name}/pages.json"

    def tick(self, prs, trigger="watch", dry=False, level="report", drafts="skip", author="", target="", pages=None,
             env=None):
        with open(self.pages, "w") as f:
            f.write("\n".join(json.dumps(p) for p in (pages or [page(prs)])))
        watch, fetch, posting = blocks()
        for k, v in {"<trigger>": trigger, "<daily cap>": "6", "<window>": "", "<notify command>": "",
                     "<drafts>": drafts, "<author>": author, '"<n>"': f'"{target}"'}.items():
            watch = watch.replace(k, v)
        with open(test_run.RUN_SH) as f:
            script = f.read()
        self.assertIn(SETTINGS, script)
        script = script.replace(SETTINGS, watch).replace("fetch() { :; }", fetch).replace(
            "skills=() consumed=()", "skills=(skills/babysit-pr) consumed=()")
        if level == "comment":
            script = script.replace("post_check() { :; }\n\npost() { :; }", posting)
        for k, v in {"<base>": "main", "<owner/repo>": "o/r", "<turns>": "5", "<minutes>": "1", "<level>": level,
                     "<weekly usd>": "", "<remote url>": self.remote}.items():
            script = script.replace(k, v)
        path = f"{self.repo}/.factory/automations/pr-babysitting.sh"
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
        e = dict(self.env, PAGES=self.pages, **(env or {}), **({"FACTORY_DRY_RUN": "1"} if dry else {}))
        return subprocess.run([path], env=e, capture_output=True, text=True, timeout=120)

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

    def listing(self):
        with open(self.log + ".ls") as f:
            return f.read().split()

    def quiet(self, prs, **kw):
        before = (len(self.records()), self.model_calls())
        r = self.tick(prs, **kw)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual((len(self.records()), self.model_calls()), before)

    def fired(self, prs, **kw):
        r = self.tick(prs, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.records()[-1]["events"]

    def test_only_a_settled_actionable_pr_fires(self):
        s = self.other_sha
        self.quiet([pr(1, s, rollup="PENDING", mergeable="CONFLICTING"), pr(2, s, rollup="EXPECTED", threads=[("Bot", False)]),
                    pr(3, s, merge="UNKNOWN"),
                    pr(4, s, rollup="SUCCESS", merge="CLEAN"), pr(6, s, rollup=None, merge="CLEAN"),
                    pr(7, s, rollup="SUCCESS", threads=[("Bot", True), ("User", False)])])
        self.assertEqual((self.model_calls(), self.records(), self.seen()), (0, [], []))
        for p, fp in ((pr(8, s, rollup="ERROR"), "ERROR.BLOCKED.0"),
                      (pr(9, s, rollup="SUCCESS", mergeable="CONFLICTING", merge="DIRTY"), "SUCCESS.DIRTY.0"),
                      (pr(10, s, rollup=None, merge="CLEAN", threads=[("Bot", False), ("Bot", False)]), "NONE.CLEAN.2")):
            self.assertEqual(self.fired([p]), [f"pr-{p['number']}"])
            self.assertEqual(self.seen()[-1], [f"pr-{p['number']}", "done", f"{s}.{fp}"])

    def test_a_green_new_commit_does_not_fire_and_a_changed_fingerprint_does(self):
        s = self.other_sha
        self.assertEqual(self.fired([pr(1, s)]), ["pr-1"])
        self.quiet([pr(1, s)])
        self.quiet([pr(1, "c" * 40, rollup="SUCCESS", merge="CLEAN")])
        self.assertEqual(self.fired([pr(1, "c" * 40)]), ["pr-1"])
        self.assertEqual(self.model_calls(), 2)
        self.assertTrue(os.path.exists(f"{self.out}/{datetime.date.today()}-pr-1-cccccccccccc.md"))

    def test_only_the_changed_pr_is_fetched_one_fire_per_pr(self):
        s = self.other_sha
        prs = [pr(1, s, minutes=5), pr(2, s, minutes=30), pr(3, s, rollup="SUCCESS", merge="CLEAN")]
        self.assertEqual(self.fired(prs), ["pr-2"])
        self.assertEqual(self.fired(prs), ["pr-1"])
        self.quiet(prs)
        views = [c for c in self.calls() if c.startswith("gh pr view") and "--json number" in c]
        self.assertEqual(views, [f"gh pr view {n} --json number,title,headRefOid,isCrossRepository,isDraft,mergeable,mergeStateStatus,"
                                 "statusCheckRollup" for n in (2, 1)])
        self.assertNotIn("gh pr list", "\n".join(self.calls()))
        self.assertIn("input/1/diff.patch", self.listing())
        self.assertFalse([p for p in self.listing() if p.startswith("input/2/")])

    def test_a_fork_pr_gets_the_diff_only(self):
        refs = self.git("-C", self.repo, "for-each-ref")
        self.assertEqual(self.fired([pr(5, self.sha, fork=True)], env={"SAME": ""}), ["pr-5"])
        self.assertIn("input/5/diff.patch", self.listing())
        self.assertFalse([p for p in self.listing() if p.startswith("input/5/head")])
        self.assertEqual(self.git("-C", self.repo, "for-each-ref"), refs)
        r = subprocess.run(["git", "-C", self.repo, "cat-file", "-e", self.sha], env=self.env, capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    def test_a_refused_diff_still_fires_without_it(self):
        with open(f"{self.tmp.name}/bin/gh", "w") as f:
            f.write(GH.replace('"pr diff") echo "diff of $3" ;;', '"pr diff") exit 1 ;;'))
        self.assertEqual(self.fired([pr(5, self.sha)]), ["pr-5"])
        self.assertEqual(self.records()[-1]["outcome"], "completed")
        self.assertNotIn("input/5/diff.patch", self.listing())
        self.assertIn("input/5/head/pushed.txt", self.listing())
        self.assertEqual(self.seen()[-1][:2], ["pr-5", "done"])

    def test_fetch_calls_target_the_configured_repo(self):
        with open(f"{self.tmp.name}/bin/gh", "w") as f:
            f.write(GH.replace('echo "gh $*" >> "$LOG"', 'echo "gh $*" >> "$LOG"; echo "${GH_REPO-unset}" >> "$LOG.repo"'))
        self.assertEqual(self.fired([pr(5, self.sha)]), ["pr-5"])
        with open(self.log + ".repo") as f:
            repos = f.read().split()
        self.assertEqual(repos[0], "unset")
        self.assertEqual(set(repos[1:]), {"o/r"})

    def test_a_same_repo_head_is_data_never_skills(self):
        refs = self.git("-C", self.repo, "for-each-ref")
        self.assertEqual(self.fired([pr(5, self.sha)]), ["pr-5"])
        ls = self.listing()
        self.assertIn("input/5/head/pushed.txt", ls)
        self.assertIn("input/5/head/skills/babysit-pr/SKILL.md", ls)
        self.assertNotIn("input/5/head/link", ls)
        self.assertEqual([p for p in ls if p.startswith("skills/")], ["skills/babysit-pr/SKILL.md"])
        with open(self.log + ".skill") as f:
            self.assertEqual(f.read(), "base skill\n")
        self.assertEqual(self.git("-C", self.repo, "for-each-ref"), refs)
        self.assertFalse(os.path.exists(f"{self.repo}/.git/FETCH_HEAD"))
        self.assertEqual(sum(c.startswith("gh pr view 5 ") for c in self.calls()), 1)

    def test_drafts_are_skipped_unless_included(self):
        prs = [pr(1, self.other_sha, draft=True)]
        self.quiet(prs)
        self.assertEqual(self.fired(prs, drafts="include"), ["pr-1"])
        r = self.tick(prs, drafts="maybe")
        self.assertIn("gate: drafts maybe is not skip or include", r.stderr)

    def test_one_author_scope(self):
        prs = [pr(1, self.other_sha, author="bob"), pr(2, self.other_sha, author="ann", minutes=5)]
        self.assertEqual(self.fired(prs, author="ann"), ["pr-2"])
        self.quiet(prs, author="ann")

    def test_the_author_match_ignores_case(self):
        self.assertEqual(self.fired([pr(1, self.other_sha, author="Ann")], author="ann"), ["pr-1"])

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_an_unreadable_comment_ledger_blocks_before_posting(self):
        self.write(".factory/reports/pr-babysitting/commented.tsv", "")
        os.chmod(f"{self.out}/commented.tsv", 0)
        r = self.tick([pr(3, self.other_sha)], level="comment", target="3")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commented.tsv unreadable", r.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith("gh pr comment")])

    def test_comment_level_posts_once_per_pr_per_head_sha(self):
        s = self.other_sha
        kw = dict(level="comment", target="3")
        self.assertEqual(self.fired([pr(3, s)], **kw), ["pr-3"])
        self.assertEqual(self.fired([pr(3, s, threads=[("Bot", False)])], **kw), ["pr-3"])
        self.assertEqual(self.fired([pr(4, "d" * 40)], **kw), ["pr-4"])
        self.assertEqual(self.fired([pr(3, "c" * 40)], **kw), ["pr-3"])
        posts = [c for c in self.calls() if c.startswith("gh pr comment")]
        self.assertEqual(posts, [f"gh pr comment 3 --repo o/r --body-file .factory/reports/pr-babysitting/"
                                 f"{datetime.date.today()}-pr-3-{x[:12]}.md" for x in (s, "c" * 40)])
        with open(f"{self.out}/commented.tsv") as f:
            self.assertEqual(f.read(), f"3 {s}\n3 {'c' * 40}\n")
        self.assertEqual(self.model_calls(), 4)

    def test_pr_level_needs_and_watches_only_the_target(self):
        r = self.tick([pr(1, self.other_sha)], level="pr")
        self.assertIn("gate: level pr needs the target PR number", r.stderr)
        self.assertEqual(self.model_calls(), 0)
        self.tick([pr(1, self.other_sha, minutes=50), pr(2, self.other_sha)], level="pr", target="2")
        self.assertEqual(self.records()[-1]["events"], ["pr-2"])

    def test_the_rate_limit_floor_is_a_detect_error(self):
        r = self.tick([], pages=[page([pr(1, self.other_sha)]), page([], remaining=499)])
        self.assertEqual(r.returncode, 1)
        self.assertIn("rate limit: 499 of 5000 left", r.stderr)
        [rec] = self.records()
        self.assertEqual((rec["outcome"], rec["reason"]), ("failed", "detect-error"))
        self.assertEqual(self.model_calls(), 0)
        self.assertEqual(self.fired([], pages=[page([pr(1, self.other_sha)]), page([], remaining=500)]), ["pr-1"])

    def test_a_dry_run_takes_the_latest_actionable_pr_and_writes_no_ledger(self):
        s = self.other_sha
        self.write(".factory/reports/pr-babysitting/seen.tsv", f"pr-2\tdone\t{s}.FAILURE.BLOCKED.0\t{ago(days=1)}\n")
        prs = [pr(1, s, minutes=60), pr(2, s, minutes=5), pr(3, s, rollup="SUCCESS", merge="CLEAN", minutes=1)]
        r = self.tick(prs, dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.records()[-1]
        self.assertEqual((rec["dry_run"], rec["events"]), (True, ["pr-2"]))
        self.assertEqual(len(self.seen()), 1)
        r = self.tick([pr(1, s, minutes=31 * 24 * 60)], dry=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no event to analyze", r.stdout)
        self.assertEqual(self.model_calls(), 1)

    def test_schedule_mode_reads_every_pr_in_scope(self):
        r = self.tick([], trigger="schedule", author="ann", env={"PRLIST": "4 6"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gh pr list --state open --limit 200 --author ann --json number --jq .[].number", self.calls())
        self.assertEqual(self.model_calls(), 1)
        self.assertTrue({"input/4/pr.json", "input/6/pr.json"} <= set(self.listing()))
        self.assertFalse([p for p in self.listing() if "diff.patch" in p])
        self.assertFalse([c for c in self.calls() if "rateLimit" in c])
        self.assertEqual((self.records()[-1]["trigger"], self.records()[-1]["events"], self.seen()), ("schedule", None, []))
        self.assertTrue(os.path.exists(f"{self.out}/{datetime.date.today()}.md"))


if __name__ == "__main__":
    unittest.main()
