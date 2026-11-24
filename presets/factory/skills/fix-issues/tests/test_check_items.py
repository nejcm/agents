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


if __name__ == "__main__":
    unittest.main()
