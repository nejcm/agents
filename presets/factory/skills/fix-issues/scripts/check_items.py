#!/usr/bin/env python3
"""Check a fetch agent's stream-json run and write one <prefix>-<id>.json per item; check a write agent's
run; project a report; check a written spec; select fix and verify candidates; or list deferred items."""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

# Error trackers are err-<source>, so two trackers' group IDs never share a key.
PREFIX = re.compile(r"err-[a-z][a-z0-9]{0,14}|(?!err$)[a-z][a-z0-9]{0,14}")
# Native IDs (ENG-12, 4815162342, Slack <channel>-<ts> like C0123-1712345678.123456), branch-safe.
ITEM_ID = re.compile(r"(?!.*\.\.)(?!.*\.lock$)[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?")
VERDICT = re.compile(
    r"fix-issues: id=[A-Za-z0-9._-]{1,96} verdict=(new-bug|fixed|duplicate|related|owned|not-a-bug|needs-info)"
    r" feature=[a-z0-9_-]{1,64} ref=(#[0-9]+|[0-9a-f]{7,40}|[a-z][a-z0-9-]{0,18}-[A-Za-z0-9._-]{1,64}|none)"
)
# A fixed line with any ref, so a malformed one is still rejected with a reason.
FIXED_ANY_REF = re.compile(r"fix-issues: id=[A-Za-z0-9._-]{1,96} verdict=fixed feature=[a-z0-9_-]{1,64} ref=.*")
PIPELINE = re.compile(
    r"pipeline: id=([A-Za-z0-9._-]{1,96}) outcome=(fixed|reproduced|not-reproduced|blocked|escalated|skipped|deferred)"
    r" reason=[a-z-]{1,32} pr=(https?://\S+|none)"
)
SPEC_HEADINGS = ["## Preconditions and data", "## Steps", "## Expected final state", "## Broken final state"]
MAX_SPEC = 4096
MAX_ITEMS = 500
MAX_LINE = 256 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_STREAM = 64 * 1024 * 1024


def parse_time(v):
    if not isinstance(v, str):
        return None
    try:
        t = datetime.datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def is_time(v):
    return parse_time(v) is not None


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
    result, calls, ok, uses, up = None, set(), 0, [], set()
    for n, line in enumerate(stream.splitlines(), 1):
        try:
            ev = json.loads(line)
        except ValueError:
            sys.exit(f"stream line {n}: not JSON")
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            up = {m.get("name") for m in ev.get("mcp_servers") or () if m.get("status") == "connected"}
        content = ev.get("message", {}).get("content") if ev.get("type") in ("user", "assistant") else None
        for c in content if isinstance(content, list) else ():
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                uses.append(c)
            if c.get("type") == "tool_use" and c.get("name") in tools:
                calls.add(c.get("id"))
            if c.get("type") == "tool_result" and c.get("is_error"):
                sys.exit(f"stream line {n}: tool error or denied call")
            if c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                ok += 1
        if ev.get("type") == "result":
            result = ev
    if servers - up:
        sys.exit(f"MCP server not connected: {', '.join(sorted(servers - up))}")
    if not result or result.get("subtype") != "success" or result.get("is_error"):
        sys.exit("run did not succeed")
    if tools and not ok:
        sys.exit("no successful call to an allowlisted tool")
    return result.get("result") or "", uses


def judged(reports, today):
    seen = set()
    for name in os.listdir(reports) if os.path.isdir(reports) else ():
        if name.endswith(".md") and name != today:
            with open(os.path.join(reports, name), errors="replace") as f:
                seen.update(line.split(" ")[1][3:] for line in f if line.startswith("fix-issues: id="))
    return seen - deferred(reports, today)


def is_item_name(i):
    m = re.fullmatch(r"(err-[^-]+|[^-]+)-(.+)", i)
    return i.isdigit() or bool(m and PREFIX.fullmatch(m[1]) and ITEM_ID.fullmatch(m[2]))


def deferred(reports, today):
    last = {}
    for name in sorted(os.listdir(reports)) if os.path.isdir(reports) else ():
        if name.endswith(".md") and name != today:
            # Only the model-free section appended after the Judge's text counts.
            section = None
            with open(os.path.join(reports, name), errors="replace") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line == "## Pipeline":
                        section = []
                    elif section is not None:
                        section.append(line)
            for m in filter(None, map(PIPELINE.fullmatch, section or ())):
                if is_item_name(m[1]):
                    last[m[1]] = m[2]
    return {i for i, outcome in last.items() if outcome == "deferred"}


def check_spec(features, feature, stdin):
    data = stdin.read(MAX_SPEC + 1)
    if len(data) > MAX_SPEC:
        sys.exit(f"spec over {MAX_SPEC} bytes")
    try:
        text = data.decode()
    except UnicodeDecodeError:
        sys.exit("spec not UTF-8")
    if any(c != "\n" and unicodedata.category(c) in ("Cc", "Cf") for c in text):
        sys.exit("spec has a control or format character")
    if re.search(r"https?://", text, re.I):
        sys.exit("spec has a URL")
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", feature) or not os.path.isfile(os.path.join(features, feature + ".md")):
        sys.exit(f"feature {feature} not in the feature map")
    lines = text.rstrip("\n").split("\n")
    if lines[0] != f"feature: {feature}":
        sys.exit(f"first line is not 'feature: {feature}'")
    heads = [n for n, line in enumerate(lines) if line.startswith("#")]
    if [lines[n] for n in heads] != SPEC_HEADINGS:
        sys.exit("headings are not exactly: " + ", ".join(SPEC_HEADINGS))
    if any(line.strip() for line in lines[1:heads[0]]):
        sys.exit("text between the feature line and the first heading")
    for a, b in zip(heads, heads[1:] + [len(lines)]):
        if not any(line.strip() for line in lines[a + 1:b]):
            sys.exit(f"{lines[a]} is blank")
    sys.stdout.write("\n".join(lines) + "\n")


def select(report, items, cap, trust, label, verify):
    if not all(p == "#" or PREFIX.fullmatch(p) for p in trust):
        sys.exit("bad --trust prefix")
    never = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
    run = {}
    with open(report, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if VERDICT.fullmatch(line) or FIXED_ANY_REF.fullmatch(line):
                i, verdict, feature, ref = (x.split("=", 1)[1] for x in line.split(" ", 4)[1:])
                path = os.path.join(items, i + ".json")
                if i not in run and os.path.isfile(path):
                    try:
                        with open(path) as g:
                            obj = json.load(g)
                        labels = {x["name"] for x in obj.get("labels") or ()
                                  if isinstance(x, dict) and isinstance(x.get("name"), str)}
                        created = parse_time(obj.get("createdAt", obj.get("created"))) or never
                    except (OSError, ValueError, AttributeError, TypeError):
                        obj, labels, created = None, set(), never
                    run[i] = created, verdict, feature, ref.lstrip("#"), obj, labels, ref
    taken, fixes = set(), 0
    for i in sorted(run, key=lambda i: (run[i][0], i)):
        _, verdict, feature, ref, obj, labels, raw = run[i]
        gh = i.isdigit()
        if obj is None:
            why = "bad-item"
        elif verdict == "duplicate" and ref != i and ref in run and run[ref][1] == "duplicate" and run[ref][3] == i:
            why = "mutual-duplicate"
        elif verdict not in (("new-bug", "fixed") if verify else ("new-bug",)):
            why = "verdict"
        elif feature == "none":
            why = "no-feature"
        elif not (any(i.startswith(p + "-") for p in trust) or gh and ("#" in trust or label in labels)):
            why = "untrusted"
        elif gh and obj.get("state") != "OPEN":
            why = "closed"
        elif gh and obj.get("assignees") != []:
            why = "assigned"
        elif verdict == "fixed" and not re.fullmatch(r"#[0-9]{1,9}|[0-9a-f]{7,40}", raw):
            why = "fixed-ref"
        elif feature in taken:
            why = "same-feature"
        elif fixes >= cap:
            why = "cap"
        else:
            why, fixes = "verify" if verdict == "fixed" else "fix", fixes + 1
            taken.add(feature)
        # A verify row also carries the triage ref, a PR #<n> or a SHA the coordinator qualifies.
        print(f"{i}\t{feature}\t{why}" + (f"\t{raw}" if why == "verify" else ""))


def project(report):
    with open(report, errors="replace") as f:
        for line in f:
            if VERDICT.fullmatch(line.rstrip("\n")):
                print(line, end="")


def check_write(tool, body_key, body_file, fixed, stream):
    try:
        want = json.loads(fixed, object_pairs_hook=strict_object, parse_constant=reject_constant)
    except ValueError:
        sys.exit("fixed arguments not JSON")
    if not re.fullmatch(r"mcp__[^_]\w*?__\w+", tool) or not isinstance(want, dict) or body_key in want:
        sys.exit("bad tool name, or fixed arguments not an object without the body key")
    data = stream.read(MAX_STREAM + 1)
    if len(data) > MAX_STREAM:
        sys.exit(f"stream over {MAX_STREAM} bytes")
    try:
        _, uses = final_text(data.decode("utf-8", "replace"), {tool})
    except SystemExit as e:
        sys.exit(f"{e.code}: check the destination by hand")
    if len(uses) != 1 or uses[0].get("name") != tool:
        sys.exit(f"expected one call to {tool}, got {len(uses)}: check the destination by hand")
    got = uses[0].get("input")
    got = dict(got) if isinstance(got, dict) else None
    if body_key and got is not None:
        with open(body_file, errors="replace") as f:
            body = f.read().strip()
        sent = got.pop(body_key, None)
        got = got if isinstance(sent, str) and sent.strip() == body else None
    # Canonical JSON, so 1, 1.0 and True differ.
    if got is None or json.dumps(got, sort_keys=True) != json.dumps(want, sort_keys=True):
        sys.exit(f"{tool} called with other arguments or body: check the destination by hand")


def main(argv, stdin=sys.stdin.buffer):
    if len(argv) == 2 and argv[0] == "--project":
        return project(argv[1])
    if len(argv) == 5 and argv[0] == "--write":
        return check_write(*argv[1:], stdin)
    if len(argv) == 3 and argv[0] == "--spec":
        return check_spec(*argv[1:], stdin)
    if len(argv) == 3 and argv[0] == "--deferred":
        return sys.stdout.write("".join(i + "\n" for i in sorted(deferred(*argv[1:]))))
    if argv[:1] == ["--select"]:
        sp = argparse.ArgumentParser(usage="check_items.py --select <report> <items dir> <cap> "
                                     "[--trust <prefix or '#' for GitHub>]... [--label <name>] [--no-verify]")
        sp.add_argument("report")
        sp.add_argument("items")
        sp.add_argument("cap", type=int)
        sp.add_argument("--trust", action="append", default=[])
        sp.add_argument("--label")
        sp.add_argument("--no-verify", dest="verify", action="store_false")
        return select(**vars(sp.parse_args(argv[1:])))
    ap = argparse.ArgumentParser(usage="check_items.py <prefix> <dir> [--mcp <tools>] "
                                 "[--skip-judged <reports dir> <today>.md] < stream.jsonl | --project <report> | "
                                 "--write <tool> <body key or ''> <body file> <fixed args JSON> < stream.jsonl | "
                                 "--spec <features dir> <feature> < spec.md | --select ... | "
                                 "--deferred <reports dir> <today>.md")
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
    text, _ = final_text(data.decode("utf-8", "replace"), tools)
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
            try:
                with open(os.path.join(out, name + ".json"), "x") as f:
                    json.dump(obj, f)
            except FileExistsError:
                pass  # an earlier fetch this run wrote it
    print(len(items))


if __name__ == "__main__":
    main(sys.argv[1:])
