import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import check_items as ci  # noqa: E402

ITEM = {
    "id": "ENG-12",
    "title": "Crash on save",
    "body": "Steps...",
    "url": "https://linear.app/x/issue/ENG-12",
    "created": "2026-11-01T08:00:00Z",
    "updated": "2026-11-02T08:00:00+01:00",
    "labels": ["bug"],
    "priority": 2,
}


def stream(text, events=(), result="success", servers=()):
    init = {"type": "system", "subtype": "init", "mcp_servers": [{"name": n, "status": st} for n, st in servers]}
    evs = [init, *events, {"type": "result", "subtype": result,
                                                            "is_error": result != "success", "result": text}]
    return io.BytesIO("".join(json.dumps(e) + "\n" for e in evs).encode())


def tool_result(is_error, use_id="t"):
    content = [{"type": "tool_result", "tool_use_id": use_id, "is_error": is_error, "content": "x"}]
    return {"type": "user", "message": {"role": "user", "content": content}}


def tool_use(name, use_id="t", args=None):
    content = [{"type": "tool_use", "id": use_id, "name": name, "input": args or {}}]
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


LIST = "mcp__trk__list_issues"


def setUpModule():
    global scratch
    scratch = tempfile.TemporaryDirectory()
    tempfile.tempdir = scratch.name


def tearDownModule():
    tempfile.tempdir = None
    scratch.cleanup()


def run(lines, prefix="lin", extra=(), **kw):
    out = tempfile.mkdtemp()
    text = "".join(json.dumps(x) + "\n" if not isinstance(x, str) else x + "\n" for x in lines)
    with contextlib.redirect_stdout(io.StringIO()):
        ci.main([prefix, out, *extra], stream(text, **kw))
    return out


class CheckItems(unittest.TestCase):
    def test_valid_writes_one_file_per_item(self):
        out = run([ITEM, dict(ITEM, id=7, labels=[]), dict(ITEM, id="C0123-1712345678.123456")])
        names = ["lin-7.json", "lin-C0123-1712345678.123456.json", "lin-ENG-12.json"]
        self.assertEqual(sorted(os.listdir(out)), names)
        with open(os.path.join(out, "lin-ENG-12.json")) as f:
            self.assertEqual(json.load(f), ITEM)

    def test_empty_output_is_zero_items(self):
        self.assertEqual(os.listdir(run([])), [])
        self.assertEqual(os.listdir(run([""])), [])

    def test_tool_error_or_failed_run_fails(self):
        for kw in ({"events": [tool_result(False), tool_result(True)]}, {"result": "error_max_turns"}):
            with self.subTest(kw=kw), self.assertRaises(SystemExit):
                run([ITEM], **kw)
        self.assertEqual(len(os.listdir(run([ITEM], events=[tool_result(False)]))), 1)
        with self.assertRaises(SystemExit):
            ci.main(["lin", tempfile.mkdtemp()], io.BytesIO(json.dumps(ITEM).encode()))

    def test_mcp_needs_connected_server_and_a_successful_allowlisted_call(self):
        mcp = ["--mcp", LIST]
        good = [tool_use(LIST), tool_result(False)]
        self.assertEqual(os.listdir(run([], extra=mcp, servers=[("trk", "connected")], events=good)), [])
        bad = [
            {"servers": [("trk", "failed")], "events": good},
            {"servers": [], "events": good},
            {"servers": [("trk", "connected")]},
            {"servers": [("trk", "connected")], "events": [tool_use("mcp__trk__other"), tool_result(False)]},
        ]
        for kw in bad:
            with self.subTest(kw=kw), self.assertRaises(SystemExit):
                run([], extra=mcp, **kw)
        with self.assertRaises(SystemExit):
            run([], extra=["--mcp", "Bash"])

    def test_skips_items_judged_in_earlier_reports(self):
        reports = tempfile.mkdtemp()
        with open(os.path.join(reports, "2026-11-20.md"), "w") as f:
            f.write("fix-issues: id=lin-C0123-1712345678X123456 verdict=new-bug feature=none ref=none\n"
                    "fix-issues: id=lin-ENG-12 verdict=fixed feature=none ref=none\n")
        with open(os.path.join(reports, "2026-11-24.md"), "w") as f:
            f.write("fix-issues: id=lin-7 verdict=fixed feature=none ref=none\n")
        out = run([ITEM, dict(ITEM, id="C0123-1712345678.123456"), dict(ITEM, id=7)],
                  extra=["--skip-judged", reports, "2026-11-24.md"])
        self.assertEqual(sorted(os.listdir(out)), ["lin-7.json", "lin-C0123-1712345678.123456.json"])

    def test_project_keeps_only_valid_lines(self):
        lines = [
            "fix-issues: id=err-sentry-C0123-1712345678.123456 verdict=duplicate feature=none ref=lin-ENG-3",
            "fix-issues: id=7 verdict=fixed feature=x ref=abc1234",
            "fix-issues: id=7 verdict=fixed feature=x ref=$(x)",
            "  fix-issues: id=7 verdict=fixed feature=x ref=none",
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("\n".join(lines) + "\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ci.main(["--project", f.name])
        self.assertEqual(buf.getvalue().splitlines(), lines[:2])

    def test_invalid_fails_and_writes_nothing(self):
        cases = [
            "here are the items:",
            "```json",
            [1],
            "\t",
            "   ",
            '{"id": "1", "id": "2"}',
            json.dumps(ITEM)[:-1] + ', "score": NaN}',
            json.dumps(ITEM)[:-1] + ', "score": -Infinity}',
            json.dumps(ITEM)[:-1] + ', "score": 1e999}',
            dict(ITEM, id="../etc"),
            dict(ITEM, id="a..b"),
            dict(ITEM, id=".x"),
            dict(ITEM, id="x.lock"),
            dict(ITEM, id="x" * 65),
            dict(ITEM, url="https://x/a\n"),
            dict(ITEM, id=True),
            {k: v for k, v in ITEM.items() if k != "body"},
            dict(ITEM, url="javascript:alert(1)"),
            dict(ITEM, created="yesterday"),
            dict(ITEM, labels="bug"),
        ]
        for bad in cases:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as out:
                text = json.dumps(ITEM) + "\n" + (bad if isinstance(bad, str) else json.dumps(bad))
                with self.assertRaises(SystemExit) as e:
                    ci.main(["lin", out], stream(text))
                self.assertIn("line 2", str(e.exception.code))
                self.assertEqual(os.listdir(out), [])

    def test_interior_empty_line_fails(self):
        with self.assertRaises(SystemExit) as e:
            run([ITEM, "", dict(ITEM, id=7)])
        self.assertIn("line 2: blank", str(e.exception.code))

    def test_duplicate_id_fails(self):
        with self.assertRaises(SystemExit):
            run([ITEM, ITEM])

    def test_prefixes(self):
        self.assertEqual(os.listdir(run([ITEM], prefix="err-sentry")), ["err-sentry-ENG-12.json"])
        for bad in ("../x", "err", "err-", "Lin", "lin-x"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                run([ITEM], prefix=bad)

    def test_oversized_fails(self):
        with self.assertRaises(SystemExit) as e:
            run([dict(ITEM, body="x" * ci.MAX_LINE)])
        self.assertIn("over", str(e.exception.code))
        with self.assertRaises(SystemExit) as e:
            run([ITEM, " " * (ci.MAX_LINE + 1)])
        self.assertIn("over", str(e.exception.code))
        with self.assertRaises(SystemExit) as e:
            run([dict(ITEM, id=n) for n in range(ci.MAX_ITEMS + 1)])
        self.assertIn("items", str(e.exception.code))
        with self.assertRaises(SystemExit) as e:
            ci.main(["lin", tempfile.mkdtemp()], stream("x" * (ci.MAX_TOTAL + 1)))
        self.assertIn("bytes", str(e.exception.code))

    def test_write_needs_exactly_the_fixed_call(self):
        tool, fixed = "mcp__trk__save_comment", '{"issueId": "ENG-12"}'
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("Fixed in #4.\n")

        def write(*uses):
            events = [e for i, u in enumerate(uses) for e in (tool_use(u[0], str(i), u[1]), tool_result(False, str(i)))]
            ci.main(["--write", tool, "body", f.name, fixed], stream("", events, servers=[("trk", "connected")]))

        write((tool, {"issueId": "ENG-12", "body": "Fixed in #4."}))
        bad = [
            [(tool, {"issueId": "ENG-13", "body": "Fixed in #4."})],
            [(tool, {"issueId": "ENG-12", "body": "Fixed."})],
            [(tool, {"issueId": "ENG-12", "body": "Fixed in #4.", "parentId": "x"})],
            [(tool, {"issueId": "ENG-12", "body": "Fixed in #4."})] * 2,
            [],
            [("mcp__trk__other", {"issueId": "ENG-12", "body": "Fixed in #4."})],
            [(tool, {"issueId": "ENG-12", "body": 4})],
            [(tool, [["issueId", "ENG-12"], ["body", "Fixed in #4."]])],
        ]
        for uses in bad:
            with self.subTest(uses=uses), self.assertRaises(SystemExit):
                write(*uses)
        call = [tool_use(tool, "1", {"issueId": "ENG-12", "body": "Fixed in #4."})]
        for kw in ({"events": call + [tool_result(True, "1")], "servers": [("trk", "connected")]},
                   {"events": call + [tool_result(False, "1")], "servers": [("trk", "failed")]}):
            with self.subTest(kw=kw), self.assertRaises(SystemExit) as e:
                ci.main(["--write", tool, "body", f.name, fixed], stream("", **kw))
            self.assertIn("by hand", str(e.exception.code))
        with self.assertRaises(SystemExit) as e:
            ci.main(["--write", tool, "body", f.name, "{"], stream(""))
        self.assertIn("not JSON", str(e.exception.code))

    def test_write_body_may_differ_only_by_trailing_newlines(self):
        tool, fixed = "mcp__trk__save_comment", '{"issueId": "ENG-12"}'
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("    code block\n")

        def write(body):
            events = [tool_use(tool, "1", {"issueId": "ENG-12", "body": body}), tool_result(False, "1")]
            ci.main(["--write", tool, "body", f.name, fixed], stream("", events, servers=[("trk", "connected")]))

        write("    code block")
        write("    code block\n")
        for body in ("code block", "    code block ", "\n    code block"):
            with self.subTest(body=body), self.assertRaises(SystemExit):
                write(body)

    def test_write_without_body_checks_fixed_args_only(self):
        tool, fixed = "mcp__trk__update_issue", '{"id": "ENG-12", "state": "In Review", "notify": false}'

        def write(args):
            events = [tool_use(tool, "1", args), tool_result(False, "1")]
            ci.main(["--write", tool, "", "/dev/null", fixed], stream("", events, servers=[("trk", "connected")]))

        write({"id": "ENG-12", "state": "In Review", "notify": False})
        for args in ({"id": "ENG-12", "state": "Done", "notify": False},
                     {"id": "ENG-12", "state": "In Review", "notify": 0}):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                write(args)

    def test_deferred_item_is_fetched_again_and_a_final_one_is_not(self):
        reports = tempfile.mkdtemp()
        with open(os.path.join(reports, "2026-11-20.md"), "w") as f:
            f.write("fix-issues: id=lin-ENG-12 verdict=new-bug feature=save ref=none\n"
                    "fix-issues: id=lin-7 verdict=new-bug feature=save ref=none\n## Pipeline\n"
                    "pipeline: id=lin-ENG-12 outcome=deferred reason=cap pr=none\n"
                    "pipeline: id=lin-7 outcome=deferred reason=cap pr=none\n")
        with open(os.path.join(reports, "2026-11-21.md"), "w") as f:
            f.write("## Pipeline\npipeline: id=lin-7 outcome=fixed reason=none pr=https://github.com/o/r/pull/3\n")
        with open(os.path.join(reports, "2026-11-22.md"), "w") as f:
            f.write("## lin-9\npipeline: id=lin-7 outcome=deferred reason=cap pr=none\n"
                    "## Pipeline\npipeline: id=--x outcome=deferred reason=cap pr=none\n"
                    "pipeline: id=.. outcome=deferred reason=cap pr=none\n"
                    "pipeline: id=lin-a..b outcome=deferred reason=cap pr=none\n")
        with open(os.path.join(reports, "2026-11-23.md"), "w") as f:
            f.write("pipeline: id=lin-7 outcome=deferred reason=cap pr=none\n")
        with open(os.path.join(reports, "2026-11-24.md"), "w") as f:
            f.write("## Pipeline\npipeline: id=lin-7 outcome=deferred reason=cap pr=none\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ci.main(["--deferred", reports, "2026-11-24.md"])
        self.assertEqual(buf.getvalue(), "lin-ENG-12\n")
        out = run([ITEM, dict(ITEM, id=7)], extra=["--skip-judged", reports, "2026-11-24.md"])
        self.assertEqual(os.listdir(out), ["lin-ENG-12.json"])

    def test_escalated_after_deferred_is_final(self):
        reports = tempfile.mkdtemp()
        with open(os.path.join(reports, "2026-11-20.md"), "w") as f:
            f.write("## Pipeline\npipeline: id=lin-7 outcome=deferred reason=cap pr=none\n")
        with open(os.path.join(reports, "2026-11-21.md"), "w") as f:
            f.write("## Pipeline\npipeline: id=lin-7 outcome=escalated reason=prod-access pr=none\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ci.main(["--deferred", reports, "2026-11-24.md"])
        self.assertEqual(buf.getvalue(), "")

    def test_item_already_fetched_this_run_is_kept(self):
        out = run([ITEM])
        with contextlib.redirect_stdout(io.StringIO()):
            ci.main(["lin", out], stream(json.dumps(dict(ITEM, title="Other")) + "\n"))
        with open(os.path.join(out, "lin-ENG-12.json")) as f:
            self.assertEqual(json.load(f), ITEM)


SPEC = ("feature: save\n\n## Preconditions and data\nA saved draft.\n\n## Steps\n1. Click Save.\n\n"
        "## Expected final state\nSaved.\n\n## Broken final state\nThe app crashes.\n")


class Spec(unittest.TestCase):
    def setUp(self):
        self.features = tempfile.mkdtemp()
        open(os.path.join(self.features, "save.md"), "w").close()

    def spec(self, text, feature="save"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ci.main(["--spec", self.features, feature], io.BytesIO(text.encode()))
        return buf.getvalue()

    def test_valid_spec_is_printed(self):
        self.assertEqual(self.spec(SPEC), SPEC)

    def test_rejects_and_prints_nothing(self):
        cases = {
            "missing heading": SPEC.replace("## Steps\n1. Click Save.\n\n", ""),
            "reordered": SPEC.replace("## Expected final state", "## X").replace("## Broken final state",
                                      "## Expected final state").replace("## X", "## Broken final state"),
            "extra heading": SPEC + "### Notes\nx\n",
            "blank section": SPEC.replace("1. Click Save.", "  "),
            "text before first heading": SPEC.replace("feature: save\n\n", "feature: save\nhi\n"),
            "feature mismatch": SPEC.replace("feature: save", "feature: load"),
            "no feature line": SPEC.replace("feature: save\n", ""),
            "oversize": SPEC + "x" * ci.MAX_SPEC,
            "control character": SPEC.replace("Saved.", "Saved.\x1b[2J"),
            "carriage return": SPEC.replace("\n", "\r\n"),
            "bidi override": SPEC.replace("Saved.", "Saved\u202e."),
            "url": SPEC.replace("A saved draft.", "See HTTPS://x.y/z."),
            "empty": "",
        }
        runs = [("save", text.encode(), name) for name, text in cases.items()]
        runs += [(f, SPEC.replace("save", f, 1).encode(), f) for f in ("load", "../save", "none")]
        runs.append(("save", SPEC.encode() + b"\xff", "invalid UTF-8"))
        for feature, data, name in runs:
            with self.subTest(name), contextlib.redirect_stdout(io.StringIO()) as buf, \
                    self.assertRaises(SystemExit) as e:
                ci.main(["--spec", self.features, feature], io.BytesIO(data))
            self.assertTrue(e.exception.code)
            self.assertEqual(buf.getvalue(), "")


def gh_item(n, created, **kw):
    return dict({"number": n, "title": "t", "body": "b", "createdAt": created, "url": "https://x",
                 "labels": [], "state": "OPEN", "assignees": []}, **kw)


class Select(unittest.TestCase):
    def select(self, verdicts, items, cap=3, extra=()):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "items"))
        for name, obj in items.items():
            with open(os.path.join(d, "items", name + ".json"), "w") as f:
                f.write(obj if isinstance(obj, str) else json.dumps(obj))
        with open(os.path.join(d, "projected"), "w") as f:
            f.write("".join(f"fix-issues: id={v[0]} verdict={v[1]} feature={v[2]} ref={v[3]}\n" for v in verdicts))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ci.main(["--select", os.path.join(d, "projected"), os.path.join(d, "items"), str(cap), *extra])
        return [line.split("\t") for line in buf.getvalue().splitlines()]

    def test_reasons_order_and_cap(self):
        day = "2026-11-%02dT08:00:00Z"
        items = {
            "1": gh_item(1, day % 1),
            "2": gh_item(2, day % 2, labels=[{"name": "factory"}]),
            "3": gh_item(3, day % 3),
            "4": gh_item(4, day % 4, labels=[{"name": "factory"}], state="CLOSED"),
            "5": gh_item(5, day % 5, labels=[{"name": "factory"}], assignees=[{"login": "x"}]),
            "lin-A": dict(ITEM, id="A", created="2026-11-06T08:00:00"),
            "lin-B": dict(ITEM, id="B", created=day % 7),
            "lin-C": dict(ITEM, id="C", created=day % 8),
            "lin-D": dict(ITEM, id="D", created=day % 9),
            "lin-E": dict(ITEM, id="E", created=day % 10),
            "lin-F": dict(ITEM, id="F", created=day % 11),
            "lin-G": dict(ITEM, id="G", created=day % 12),
            "err-s-H": dict(ITEM, id="H", created=day % 13),
            "err-s-I": dict(ITEM, id="I", created=day % 14),
            "err-s-J": dict(ITEM, id="J", created=day % 15),
            "lin-K": dict(ITEM, id="K", created=day % 16),
        }
        verdicts = [
            ("lin-K", "new-bug", "k", "none"),
            ("err-s-J", "duplicate", "j", "lin-F"),
            ("1", "new-bug", "one", "none"),
            ("2", "new-bug", "two", "none"),
            ("3", "fixed", "three", "abc1234"),
            ("4", "new-bug", "four", "none"),
            ("5", "new-bug", "five", "none"),
            ("lin-A", "new-bug", "none", "none"),
            ("lin-B", "new-bug", "two", "none"),
            ("lin-C", "new-bug", "c", "none"),
            ("lin-D", "new-bug", "d", "none"),
            ("lin-E", "duplicate", "e", "#2"),
            ("lin-F", "duplicate", "f", "err-s-I"),
            ("lin-G", "new-bug", "g", "none"),
            ("err-s-H", "new-bug", "h", "none"),
            ("err-s-I", "duplicate", "i", "lin-F"),
            ("lin-Z", "new-bug", "z", "none"),
            ("lin-K", "new-bug", "other", "none"),
        ]
        got = self.select(verdicts, items, 3, ["--trust", "lin", "--label", "factory"])
        self.assertEqual(got, [
            ["1", "one", "untrusted"],
            ["2", "two", "fix"],
            ["3", "three", "untrusted"],
            ["4", "four", "closed"],
            ["5", "five", "assigned"],
            ["lin-A", "none", "no-feature"],
            ["lin-B", "two", "same-feature"],
            ["lin-C", "c", "fix"],
            ["lin-D", "d", "fix"],
            ["lin-E", "e", "verdict"],
            ["lin-F", "f", "mutual-duplicate"],
            ["lin-G", "g", "cap"],
            ["err-s-H", "h", "untrusted"],
            ["err-s-I", "i", "mutual-duplicate"],
            ["err-s-J", "j", "verdict"],
            ["lin-K", "k", "cap"],
        ])

    def test_github_trust(self):
        items = {"1": gh_item(1, "2026-11-01T08:00:00Z", labels=[{"name": "other"}])}
        verdicts = [("1", "new-bug", "one", "none")]
        self.assertEqual(self.select(verdicts, items, extra=["--trust", "#"])[0][2], "fix")
        self.assertEqual(self.select(verdicts, items, extra=["--label", "factory"])[0][2], "untrusted")
        self.assertEqual(self.select(verdicts, items, cap=0, extra=["--trust", "#"])[0][2], "cap")
        with self.assertRaises(SystemExit):
            self.select(verdicts, items, extra=["--trust", "../x"])

    def test_fixed_needs_a_pr_or_sha_ref_and_counts_toward_the_cap(self):
        day = "2026-11-0%dT08:00:00Z"
        items = {str(n): gh_item(n, day % n) for n in range(1, 8)}
        refs = ["#12", "abc1234", "none", "lin-A", "1234567", "#3", "a" * 40]
        verdicts = [(str(n), "fixed", f"f{n}", r) for n, r in zip(range(1, 8), refs)]
        got = self.select(verdicts, items, extra=["--trust", "#"])
        self.assertEqual(got, [["1", "f1", "verify", "#12"], ["2", "f2", "verify", "abc1234"],
                               ["3", "f3", "fixed-ref"], ["4", "f4", "fixed-ref"], ["5", "f5", "verify", "1234567"],
                               ["6", "f6", "cap"], ["7", "f7", "cap"]])
        bad = [("1", "fixed", "f1", "$(touch x)"), ("2", "fixed", "f2", "#1 abc"), ("3", "new-bug", "f3", "$(x)")]
        self.assertEqual(self.select(bad, items, extra=["--trust", "#"]),
                         [["1", "f1", "fixed-ref"], ["2", "f2", "fixed-ref"]])
        mixed = [("1", "new-bug", "f1", "none"), ("2", "fixed", "f1", "#9"), ("3", "fixed", "f3", "#9")]
        self.assertEqual(self.select(mixed, items, extra=["--trust", "#"]),
                         [["1", "f1", "fix"], ["2", "f1", "same-feature"], ["3", "f3", "verify", "#9"]])

    def test_no_verify_leaves_fixed_to_the_report_without_using_cap_or_feature(self):
        day = "2026-11-0%dT08:00:00Z"
        items = {str(n): gh_item(n, day % n) for n in range(1, 4)}
        verdicts = [("1", "fixed", "f1", "#12"), ("2", "new-bug", "f1", "none"), ("3", "new-bug", "f3", "none")]
        self.assertEqual(self.select(verdicts, items, cap=2, extra=["--trust", "#", "--no-verify"]),
                         [["1", "f1", "verdict"], ["2", "f1", "fix"], ["3", "f3", "fix"]])

    def test_self_duplicate_and_bad_items(self):
        day = "2026-11-0%dT08:00:00Z"
        items = {"1": gh_item(1, day % 1), "2": [], "3": gh_item(3, day % 3, labels=123),
                 "4": gh_item(4, day % 4, labels=[{"name": ["factory"]}]), "5": gh_item(5, day % 5), "6": "{"}
        verdicts = [("1", "duplicate", "one", "#1")] + [(str(n), "new-bug", f"f{n}", "none") for n in range(2, 7)]
        got = self.select(verdicts, items, extra=["--label", "factory"])
        self.assertEqual(got, [["1", "one", "verdict"], ["4", "f4", "untrusted"], ["5", "f5", "untrusted"],
                               ["2", "f2", "bad-item"], ["3", "f3", "bad-item"], ["6", "f6", "bad-item"]])


if __name__ == "__main__":
    unittest.main()
