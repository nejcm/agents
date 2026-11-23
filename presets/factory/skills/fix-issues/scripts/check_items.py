#!/usr/bin/env python3
"""Check a fetch agent's stream-json run and write one <prefix>-<id>.json per item; or project a report."""
import argparse
import datetime
import json
import os
import re
import sys

# Error trackers are err-<source>, so two trackers' group IDs never share a key.
PREFIX = re.compile(r"err-[a-z][a-z0-9]{0,14}|(?!err$)[a-z][a-z0-9]{0,14}")
# Native IDs (ENG-12, 4815162342, Slack <channel>-<ts> like C0123-1712345678.123456), branch-safe.
ITEM_ID = re.compile(r"(?!.*\.\.)(?!.*\.lock$)[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?")
VERDICT = re.compile(
    r"fix-issues: id=[A-Za-z0-9._-]{1,96} verdict=(new-bug|fixed|duplicate|related|owned|not-a-bug|needs-info)"
    r" feature=[a-z0-9_-]{1,64} ref=(#[0-9]+|[0-9a-f]{7,40}|[a-z][a-z0-9-]{0,18}-[A-Za-z0-9._-]{1,64}|none)"
)
MAX_ITEMS = 500
MAX_LINE = 256 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_STREAM = 64 * 1024 * 1024


def is_time(v):
    if not isinstance(v, str):
        return False
    try:
        datetime.datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
    except ValueError:
        return False
    return True


def check(obj):
    if not isinstance(obj, dict):
        return "not an object"
    if not isinstance(obj.get("id"), (str, int)) or isinstance(obj["id"], bool):
        return "id missing"
    if not ITEM_ID.fullmatch(str(obj["id"])):
        return "id not 1-64 of [A-Za-z0-9._-], alphanumeric at both ends, no '..'"
    for k in ("title", "body"):
        if not isinstance(obj.get(k), str):
            return k + " not a string"
    if not isinstance(obj.get("url"), str) or not re.fullmatch(r"https?://\S+", obj["url"]):
        return "url not http(s)"
    for k in ("created", "updated"):
        if not is_time(obj.get(k)):
            return k + " not ISO 8601"
    labels = obj.get("labels")
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        return "labels not a list of strings"
    try:
        json.dumps(obj, allow_nan=False)
    except ValueError:
        return "non-finite number"
    return None


def strict_object(pairs):
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate key")
    return dict(pairs)


def reject_constant(name):
    raise ValueError(name)


def final_text(stream, tools):
    servers = {t.split("__")[1] for t in tools}
    result, calls, ok = None, set(), 0
    for n, line in enumerate(stream.splitlines(), 1):
        try:
            ev = json.loads(line)
        except ValueError:
            sys.exit(f"stream line {n}: not JSON")
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            up = {m.get("name") for m in ev.get("mcp_servers") or () if m.get("status") == "connected"}
            if servers - up:
                sys.exit(f"MCP server not connected: {', '.join(sorted(servers - up))}")
        content = ev.get("message", {}).get("content") if ev.get("type") in ("user", "assistant") else None
        for c in content if isinstance(content, list) else ():
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("name") in tools:
                calls.add(c.get("id"))
            if c.get("type") == "tool_result" and c.get("is_error"):
                sys.exit(f"stream line {n}: tool error or denied call")
            if c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                ok += 1
        if ev.get("type") == "result":
            result = ev
    if not result or result.get("subtype") != "success" or result.get("is_error"):
        sys.exit("run did not succeed")
    if tools and not ok:
        sys.exit("no successful call to an allowlisted tool")
    return result.get("result") or ""


def judged(reports, today):
    seen = set()
    for name in os.listdir(reports) if os.path.isdir(reports) else ():
        if name.endswith(".md") and name != today:
            with open(os.path.join(reports, name), errors="replace") as f:
                seen.update(line.split(" ")[1][3:] for line in f if line.startswith("fix-issues: id="))
    return seen


def project(report):
    with open(report, errors="replace") as f:
        for line in f:
            if VERDICT.fullmatch(line.rstrip("\n")):
                print(line, end="")


def main(argv, stdin=sys.stdin.buffer):
    if len(argv) == 2 and argv[0] == "--project":
        return project(argv[1])
    ap = argparse.ArgumentParser(usage="check_items.py <prefix> <dir> [--mcp <tools>] "
                                 "[--skip-judged <reports dir> <today>.md] < stream.jsonl | --project <report>")
    ap.add_argument("prefix")
    ap.add_argument("out")
    ap.add_argument("--mcp", default="")
    ap.add_argument("--skip-judged", nargs=2)
    a = ap.parse_args(argv)
    tools = {t for t in re.split(r"[ ,]+", a.mcp) if t}
    if not PREFIX.fullmatch(a.prefix) or not all(re.fullmatch(r"mcp__[^_]\w*?__\w+", t) for t in tools):
        sys.exit("bad prefix or --mcp tool name")
    prefix, out = a.prefix, a.out
    data = stdin.read(MAX_STREAM + 1)
    if len(data) > MAX_STREAM:
        sys.exit(f"stream over {MAX_STREAM} bytes")
    text = final_text(data.decode("utf-8", "replace"), tools)
    if len(text.encode()) > MAX_TOTAL:
        sys.exit(f"output over {MAX_TOTAL} bytes")
    lines = text.split("\n") if text.strip() else []
    if lines and lines[-1] == "":
        lines.pop()
    skip = judged(*a.skip_judged) if a.skip_judged else set()
    items = {}
    for n, line in enumerate(lines, 1):
        if len(line.encode()) > MAX_LINE:
            sys.exit(f"line {n}: over {MAX_LINE} bytes")
        if not line.strip():
            sys.exit(f"line {n}: blank")
        try:
            obj = json.loads(line, object_pairs_hook=strict_object, parse_constant=reject_constant)
        except ValueError:
            sys.exit(f"line {n}: not JSON")
        err = check(obj)
        if err:
            sys.exit(f"line {n}: {err}")
        name = f"{prefix}-{obj['id']}"
        if name in items:
            sys.exit(f"line {n}: duplicate id {obj['id']}")
        items[name] = obj
        if len(items) > MAX_ITEMS:
            sys.exit(f"over {MAX_ITEMS} items")
    os.makedirs(out, exist_ok=True)
    for name, obj in items.items():
        if name not in skip:
            with open(os.path.join(out, name + ".json"), "x") as f:
                json.dump(obj, f)
    print(len(items))


if __name__ == "__main__":
    main(sys.argv[1:])
