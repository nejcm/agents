#!/usr/bin/env python3
"""Count agent sessions, tokens, cost and tool outcomes for one repo from local transcripts."""
# Reads only counter and structural fields; never prints message text or paths outside the repo.
import argparse
import collections
import contextlib
import datetime
import glob
import json
import math
import os
import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.parse

HARNESSES = ("Claude Code", "Codex", "Cursor", "Antigravity")
# Shown as a table column only when found.
OPTIONAL_HARNESSES = {"Antigravity"}
UNAVAILABLE = {
    "Claude Code": set(),
    "Codex": {"cost", "failed", "retries"},
    "Cursor": {"tokens", "cost", "failed", "retries", "escalations", "links"},
    "Antigravity": {"subagents", "cost", "tool_calls", "failed", "retries", "escalations", "links"},
}
ESCALATION_TOOLS = {
    "Claude Code": {"AskUserQuestion"},
    "Codex": {"request_user_input", "request_user_input_async"},
}
CODEX_CHILD_THREADS = {"subagent", "guardian_review"}
TOKEN_KEYS = ("input", "cache_write", "cache_read", "output")
# (shape, stats key that counts it, metrics it feeds); zero across this many sessions means drift.
EXPECTED = {
    "Claude Code": (("assistant usage records", "tokens_seen", {"tokens"}),
                    ("tool_use blocks", "tool_calls", {"tool_calls", "failed", "escalations"}),
                    ("tool_result.is_error flags", "error_flags", {"failed"})),
    "Codex": (("token_count records", "tokens_seen", {"tokens"}),
              ("tool call records", "tool_calls", {"tool_calls", "escalations"})),
    "Cursor": (("tool_use blocks", "tool_calls", {"tool_calls"}),),
    "Antigravity": (("gen_metadata usage records", "tokens_seen", {"tokens"}),),
}
FATES = ("open", "merged", "factory-merged", "closed", "reverted")
RUN_METRICS = ("turns", "input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens", "cost_usd")
DRIFT_MIN_SESSIONS = 5
DRIFT_EXIT = 3
KNOWN_TYPES = {"assistant", "user", "system", "cost-state", "pr-link", "tool_use", "tool_result", "text",
               "session_meta", "event_msg", "response_item", "token_count", "function_call",
               "custom_tool_call", "local_shell_call"}
# --shape descends only into containers the parsers read; message.content holds the Claude blocks.
# Field names are short words; a longer letter run or a second digit is taken for an ID or a credential.
SHAPE_KEY = re.compile(r"(?!.*([a-z]{15}|[A-Z]{6}))[A-Za-z_]{1,40}([0-9][A-Za-z_]*)?")
SHAPE_CONTAINERS = {"message", "usage", "payload", "info", "total_token_usage", "git"}


def new_stats():
    return {
        "found": False, "sessions": 0, "subagents": 0, "unreadable": 0, "tokens_seen": False,
        "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "cost": 0.0,
        "cost_sessions": 0, "tool_calls": 0, "failed": 0, "retries": 0, "escalations": 0,
        "error_flags": 0, "links": [],
    }


def is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def num(value):
    return value if is_num(value) else 0


def text(value):
    return value if isinstance(value, str) and value else None


def load(path, stats):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except OSError:
        stats["unreadable"] += 1
        return None
    return out


def repo_roots(repo):
    path = os.path.normpath(os.path.abspath(repo))
    roots = {path, os.path.realpath(repo)}
    # The link's own target keeps a symlinked parent unresolved, as tools record it (macOS /var, /tmp).
    if os.path.islink(path):
        roots.add(os.path.normpath(os.path.join(os.path.dirname(path), os.readlink(path))))
    return roots


def in_repo(cwd, repo):
    if not text(cwd) or "\0" in cwd or not os.path.isabs(cwd):
        return False
    real, root = os.path.realpath(cwd), os.path.realpath(repo)
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def first_cwd(recs):
    return next((r["cwd"] for r in recs if text(r.get("cwd"))), None)


def config_dirs(home, var, name):
    dirs = [os.path.expanduser(os.environ[var])] if text(os.environ.get(var)) else []
    return list(collections.OrderedDict((os.path.realpath(d), d) for d in dirs + [os.path.join(home, name)]).values())


def fresh(paths, since, stats):
    if since is None:
        return True
    for path in paths:
        try:
            if os.path.getmtime(path) >= since:
                return True
        except OSError:
            stats["unreadable"] += 1
    return False


def files(pattern, since, stats, recursive=False):
    return sorted(p for p in glob.glob(pattern, recursive=recursive) if os.path.isfile(p) and fresh([p], since, stats))


def blocks(rec):
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def new_session():
    return {"usage": {}, "tools": {}, "failed": set(), "retries": set(), "cost": None,
            "urls": set(), "branches": set(), "child": False, "total": None, "error_flags": 0, "subagents": set()}


def claude_records(recs, path, acc):
    for i, rec in enumerate(recs):
        kind = rec.get("type")
        branch = text(rec.get("gitBranch"))
        if branch and branch != "HEAD":
            acc["branches"].add(branch)
        if kind == "assistant":
            msg = rec["message"] if isinstance(rec.get("message"), dict) else {}
            u = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
            readings = [u.get(k) for k in ("input_tokens", "cache_creation_input_tokens",
                                           "cache_read_input_tokens", "output_tokens")]
            if text(msg.get("id")) and any(is_num(r) for r in readings):
                acc["usage"][msg["id"]] = tuple(num(r) for r in readings)
            for b in blocks(rec):
                if b.get("type") == "tool_use" and text(b.get("id")):
                    acc["tools"][b["id"]] = text(b.get("name"))
        elif kind == "user":
            for b in blocks(rec):
                if b.get("type") != "tool_result":
                    continue
                acc["error_flags"] += isinstance(b.get("is_error"), bool)
                if b.get("is_error") is True and text(b.get("tool_use_id")):
                    acc["failed"].add(b["tool_use_id"])
        elif kind == "system" and rec.get("subtype") == "api_error":
            acc["retries"].add(text(rec.get("uuid")) or (path, i))
        elif kind == "cost-state" and is_num(rec.get("totalCostUSD")):
            acc["cost"] = max(acc["cost"] or 0.0, float(rec["totalCostUSD"]))
        elif kind == "pr-link" and text(rec.get("prUrl")):
            acc["urls"].add(rec["prUrl"].rstrip("/"))


def claude(home, repo, since):
    s = new_stats()
    roots = repo_roots(repo)
    sessions = collections.OrderedDict()
    seen = set()
    for root, config in ((r, c) for r in roots for c in config_dirs(home, "CLAUDE_CONFIG_DIR", ".claude")):
        enc = re.sub(r"[^A-Za-z0-9]", "-", root)
        for d in glob.glob(os.path.join(config, "projects", enc + "*")):
            name = os.path.basename(d)
            if (name != enc and not name.startswith(enc + "-")) or d in seen:
                continue
            seen.add(d)
            for path in files(os.path.join(d, "*.jsonl"), None, s):
                subs = files(os.path.join(path[:-len(".jsonl")], "subagents", "*.jsonl"), None, s)
                if not fresh([path] + subs, since, s):
                    continue
                recs = load(path, s)
                # A session started elsewhere (e.g. a scratch dir) and moved into the repo is filed under its exact dir.
                cwds = [r.get("cwd") for r in recs or []] if name == enc else [first_cwd(recs or [])]
                if not any(in_repo(c, repo) for c in cwds):
                    continue
                sid = next((r["sessionId"] for r in recs if text(r.get("sessionId"))), path)
                acc = sessions.setdefault(sid, new_session())
                claude_records(recs, path, acc)
                for sub in subs:
                    sub_recs = load(sub, s)
                    cwd = first_cwd(sub_recs or [])
                    if sub_recs and (cwd is None or in_repo(cwd, repo)):
                        acc["subagents"].add(os.path.basename(sub))
                        claude_records(sub_recs, sub, acc)
    for acc in sessions.values():
        s["found"] = True
        s["sessions"] += 1
        s["subagents"] += len(acc["subagents"])
        for u in acc["usage"].values():
            s["tokens_seen"] = True
            for key, value in zip(TOKEN_KEYS, u):
                s[key] += value
        s["tool_calls"] += len(acc["tools"])
        s["failed"] += len(acc["failed"] & acc["tools"].keys())
        s["retries"] += len(acc["retries"])
        s["error_flags"] += acc["error_flags"]
        s["escalations"] += sum(n in ESCALATION_TOOLS["Claude Code"] for n in acc["tools"].values())
        if acc["cost"] is not None:
            s["cost"] += acc["cost"]
            s["cost_sessions"] += 1
        s["links"].append((acc["urls"], acc["branches"]))
    return s


def codex(home, repo, since):
    s = new_stats()
    sessions = collections.OrderedDict()
    paths = [p for d in config_dirs(home, "CODEX_HOME", ".codex") for sub in ("sessions", "archived_sessions")
             for p in files(os.path.join(d, sub, "**", "rollout-*.jsonl"), since, s, True)]
    for path in paths:
        recs = load(path, s)
        if not recs or recs[0].get("type") != "session_meta" or not isinstance(recs[0].get("payload"), dict):
            continue
        meta = recs[0]["payload"]
        if not in_repo(meta.get("cwd"), repo):
            continue
        acc = sessions.setdefault(text(meta.get("id")) or text(meta.get("session_id")) or path, new_session())
        native = isinstance(meta.get("source"), dict) and "subagent" in meta["source"]
        acc["child"] = native or text(meta.get("thread_source")) in CODEX_CHILD_THREADS
        git = meta.get("git") if isinstance(meta.get("git"), dict) else {}
        if text(git.get("branch")):
            acc["branches"].add(git["branch"])
        for i, rec in enumerate(recs[1:]):
            p = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
            if p.get("type") == "token_count" and isinstance(p.get("info"), dict):
                t = p["info"].get("total_token_usage")
                measured = isinstance(t, dict) and any(is_num(t.get(k)) for k in ("input_tokens", "output_tokens"))
                if measured and num(t.get("total_tokens")) >= num((acc["total"] or {}).get("total_tokens")):
                    acc["total"] = t
            elif p.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
                acc["tools"][text(p.get("call_id")) or (path, i)] = text(p.get("name"))
    for acc in sessions.values():
        s["found"] = True
        if acc["child"]:
            s["subagents"] += 1
        else:
            s["sessions"] += 1
            s["links"].append((set(), acc["branches"]))
        t = acc["total"]
        if t is not None:
            s["tokens_seen"] = True
            cached = num(t.get("cached_input_tokens"))
            s["input"] += num(t.get("input_tokens")) - cached
            s["cache_read"] += cached
            s["cache_write"] += num(t.get("cache_write_input_tokens"))
            s["output"] += num(t.get("output_tokens"))
        s["tool_calls"] += len(acc["tools"])
        s["escalations"] += sum(n in ESCALATION_TOOLS["Codex"] for n in acc["tools"].values())
    return s


def cursor(home, repo, since):
    s = new_stats()
    tools = {}
    for root in repo_roots(repo):
        enc = re.sub(r"[^A-Za-z0-9]+", "-", root).strip("-")
        base = os.path.join(home, ".cursor", "projects", enc, "agent-transcripts")
        for path in files(os.path.join(base, "**", "*.jsonl"), since, s, True):
            recs = [r for r in load(path, s) or [] if "message" in r or "role" in r]
            if not recs:
                continue
            # The same transcript can sit under the checkout's real and symlinked project dirs.
            key = os.path.relpath(path, base)
            tools[key] = max(tools.get(key, 0), sum(b.get("type") == "tool_use" for rec in recs for b in blocks(rec)))
    for key, n in tools.items():
        s["found"] = True
        s["subagents" if os.path.basename(os.path.dirname(key)) == "subagents" else "sessions"] += 1
        s["tool_calls"] += n
    return s


def varint(data, i):
    value = shift = 0
    while True:
        value |= (data[i] & 0x7F) << shift
        i += 1
        if data[i - 1] < 0x80:
            return value, i
        shift += 7
        if shift > 63:
            raise ValueError("varint")


def pb(data):
    fields, i = {}, 0
    while i < len(data):
        key, i = varint(data, i)
        if key & 7 == 0:
            value, i = varint(data, i)
        elif key & 7 == 2:
            size, i = varint(data, i)
            value, i = bytes(data[i:i + size]), i + size
            if i > len(data):
                raise ValueError("truncated")
        elif key & 7 in (1, 5):
            i += 8 if key & 7 == 1 else 4
            continue
        else:
            raise ValueError("wire type")
        fields.setdefault(key >> 3, []).append(value)
    return fields


def workspace(meta):
    uri = (pb(meta).get(1) or [b""])[0]
    return urllib.parse.unquote(uri[len(b"file://"):].decode()) if uri.startswith(b"file://") else None


def antigravity(home, repo, since):
    s = new_stats()
    sessions = collections.OrderedDict()
    # T3 Code runs agy over ACP with a per-install data dir instead of ~/.gemini; no env var points there.
    for pattern in (os.path.join(home, ".gemini", "antigravity-cli", "conversations", "*.db"),
                    os.path.join(home, ".t3", "userdata", "providers", "antigravity", "*", "antigravity-acp",
                                 "conversations", "*.db")):
        for path in files(pattern, None, s):
            try:
                wal = [path + "-wal"] if os.path.getsize(path + "-wal") else []
            except OSError:
                wal = []
            if not fresh([path] + wal, since, s):
                continue
            try:
                # Even mode=ro writes the -shm beside a WAL database, so read a private copy; -wal first,
                # so a checkpoint in between only replays frames the database copy already holds.
                with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
                    for part in wal + [path]:
                        shutil.copyfile(part, os.path.join(tmp, "c.db" + part[len(path):]))
                    db = stack.enter_context(contextlib.closing(sqlite3.connect(os.path.join(tmp, "c.db"))))
                    meta = db.execute("SELECT data FROM trajectory_metadata_blob").fetchone()
                    # Factory runs are counted from their run records; their agy calls work under .factory/.
                    if not any(in_repo(w, repo) and not in_repo(w, os.path.join(repo, ".factory"))
                               for w in map(workspace, pb(meta[0]).get(1, []))):
                        continue
                    gens = db.execute("SELECT idx, data FROM gen_metadata").fetchall()
            except (sqlite3.Error, OSError, ValueError, IndexError, TypeError):
                s["unreadable"] += 1
                continue
            acc = sessions.setdefault(os.path.basename(path)[:-len(".db")], {})
            for idx, data in gens:
                try:
                    usage = pb(pb(pb(data)[1][0])[4][0])
                except (ValueError, IndexError, KeyError, TypeError):
                    continue
                readings = [(usage.get(f) or [None])[0] for f in (2, 4, 5, 3)]
                if any(is_num(r) for r in readings):
                    acc[idx] = tuple(num(r) for r in readings)
    for acc in sessions.values():
        s["found"] = True
        s["sessions"] += 1
        for u in acc.values():
            s["tokens_seen"] = True
            for key, value in zip(TOKEN_KEYS, u):
                s[key] += value
    return s


def pr_fates(repo):
    fates = {}
    path = os.path.join(repo, ".factory", "reports", "fix-issues", "fates.tsv")
    if os.path.isfile(path) and not os.path.islink(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                t = line.split(" ", 4)
                if len(t) >= 3 and t[1] in FATES:
                    fates[t[0]] = (t[1], t[2].isdigit() and int(t[2]) > 0)
    return fates


def agreement(prs, fates):
    reviewed = [(ok, scope, fates.get(pr)) for pr, (ok, has, scope, _) in prs.items() if has]
    by = collections.defaultdict(lambda: [0, 0])
    approved = sum(ok for ok, _, _ in reviewed)
    known = agree = misses = 0
    for ok, _, fate in reviewed:
        f, asked = fate or (None, False)
        bad = asked or f in ("closed", "reverted")
        if bad or f == "merged":
            known += 1
            agree += ok != bad
        misses += ok and f in ("closed", "reverted")
    merged = {s: [0, 0] for s in ("minimal", "refactor")}
    for pr, (_, _, scope, families) in prs.items():
        f, asked = fates.get(pr) or (None, False)
        for name, ok in families if asked or f in ("merged", "closed", "reverted") else []:
            by[name][0] += ok != (asked or f in ("closed", "reverted"))
            by[name][1] += 1
        if scope in merged and f in ("merged", "factory-merged", "closed", "reverted"):
            merged[scope][0] += f in ("merged", "factory-merged")
            merged[scope][1] += 1
    return (f"Review: approved {approved} of {len(reviewed)} reviewed PRs; human outcome known for {known}, "
            f"agreeing {agree}; misses {misses} (approved, then closed or reverted). Merged of resolved PRs: "
            f"minimal {merged['minimal'][0]} of {merged['minimal'][1]}, refactor {merged['refactor'][0]} of {merged['refactor'][1]}."
            + (" Reviewer agreement by family: " + ", ".join(f"{n} {a} of {k}" for n, (a, k) in sorted(by.items())) + "." if by else ""))


def factory_runs(repo, since):
    path = os.path.join(repo, ".factory", "reports", "runs.jsonl")
    if not os.path.isfile(path):
        return None
    fates = pr_fates(repo)
    runs = collections.OrderedDict()
    for rec in load(path, new_stats()) or []:
        started = text(rec.get("started")) or ""
        if since and started[:10] < since:
            continue
        entry = rec.get("entry") if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", str(rec.get("entry"))) else "?"
        outcome = rec.get("outcome") if re.fullmatch(r"[a-z-]{1,20}", str(rec.get("outcome"))) else "?"
        r = runs.setdefault(entry, {"runs": 0, "dry": 0, "outcomes": collections.Counter(), "seen": collections.Counter(),
                                    "items": collections.Counter(), "escalations": collections.Counter(),
                                    "tests": 0, "test_files": 0, "deps": 0, "capped": 0, "partial": 0,
                                    "scopes": collections.Counter(), "weighted": None, "prs": {}, **{k: 0 for k in RUN_METRICS}})
        dry = rec.get("dry_run") is True
        r["runs"] += 1
        r["dry"] += dry
        r["capped"] += is_num(rec.get("max_turns_hit")) and rec["max_turns_hit"] > 0
        r["partial"] += rec.get("cost_complete") is False and is_num(rec.get("cost_usd"))
        r["outcomes"][outcome] += 1
        # A dry run pushes nothing, so its items, escalations and disclosures are not counted.
        items = rec.get("items") if isinstance(rec.get("items"), list) and not dry else []
        for i in items:
            o = i.get("outcome") if isinstance(i, dict) else None
            r["items"][o if re.fullmatch(r"[a-z-]{1,20}", str(o)) else "?"] += 1
            pr, rv = (i.get("pr"), i.get("reviews")) if isinstance(i, dict) else (None, None)
            if isinstance(pr, str) and re.search(r"/pull/[0-9]+$", pr):
                rv = [x for x in rv if isinstance(x, dict)] if isinstance(rv, list) else []
                r["prs"][pr] = (bool(rv) and all(x.get("verdict") == "approve" for x in rv), bool(rv), text(i.get("scope")),
                                [(x["family"] if re.fullmatch(r"[a-z]{1,20}", str(x.get("family"))) else "unknown",
                                  x.get("verdict") == "approve") for x in rv])
        for u in ([] if dry else [rec]) + [i for i in items if isinstance(i, dict)]:
            if u.get("outcome") == "escalated":
                why = u.get("reason")
                r["escalations"][why if re.fullmatch(r"[a-z-]{1,20}", str(why)) else "?"] += 1
            n = u.get("test_changes")
            if is_num(n) and n > 0:
                r["tests"] += 1
                r["test_files"] += int(n)
            r["deps"] += u.get("dependency_change") is True
            if u.get("scope") in ("minimal", "refactor"):
                r["scopes"][u["scope"]] += 1
            if is_num(u.get("weighted_lines")):
                r["weighted"] = max(r["weighted"] or 0, int(u["weighted_lines"]))
        for k in RUN_METRICS:
            r["seen"][k] += is_num(rec.get(k))
            r[k] += num(rec.get(k))
    for r in runs.values():
        r["agreement"] = agreement(r.pop("prs"), fates) if r["prs"] else ""
    return runs


def render_runs(runs):
    out = ["## Factory runs", ""]
    if runs is None:
        return out + ["- No run records (`.factory/reports/runs.jsonl` not found).", ""]
    if not runs:
        return out + ["- No run records in the period.", ""]
    out += ["| Entry | Runs | Outcomes | Turns | Input tokens | Cache write tokens | Cache read tokens | "
            "Output tokens | Cost, USD |", "| --- | ---: | --- |" + " ---: |" * 6]
    for entry, r in runs.items():
        outcomes = ", ".join(f"{o} {n}" for o, n in sorted(r["outcomes"].items()))
        cells = [f"{r[k]:,}" if r["seen"][k] else "unavailable" for k in RUN_METRICS[:-1]]
        cells.append(f"{r['cost_usd']:.2f}" if r["seen"]["cost_usd"] else "unavailable")
        out.append(f"| {entry} | {r['runs']} | {outcomes} | " + " | ".join(cells) + " |")
    out.append("")
    for entry, r in runs.items():
        items = ", ".join(f"{o} {n}" for o, n in sorted(r["items"].items()))
        escalations = ", ".join(f"{o} {n}" for o, n in sorted(r["escalations"].items()))
        out.append(f"- {entry}: {r['dry']} of {r['runs']} runs dry. Turns reported by {r['seen']['turns']}, "
                   f"tokens by {r['seen']['output_tokens']}, cost by {r['seen']['cost_usd']}"
                   + (f" ({r['partial']} missing a call's cost)" if r["partial"] else "") + "."
                   + (f" Items: {items}." if items else "")
                   + (f" Runs that hit the turn cap: {r['capped']}." if r["capped"] else "")
                   + (f" Escalation reasons: {escalations}." if escalations else "")
                   + (f" Disclosed: existing tests changed in {r['tests']} ({r['test_files']} files), "
                      f"dependencies in {r['deps']}." if r["tests"] or r["deps"] else "")
                   + (f" Scope: minimal {r['scopes']['minimal']}, refactor {r['scopes']['refactor']}; "
                      f"largest {r['weighted'] or 0:,} weighted lines." if r["scopes"] else "")
                   + (" " + r["agreement"] if r["agreement"] else ""))
    return out + [""]


def shape(value, key=None, parent=None):
    if key == "type" and isinstance(value, str):
        return value if value in KNOWN_TYPES else "?"
    opened = key is None or key in SHAPE_CONTAINERS or (key, parent) == ("content", "message")
    if isinstance(value, (dict, list)) and not opened:
        return type(value).__name__
    if isinstance(value, dict):
        return {(k if SHAPE_KEY.fullmatch(k) else "?"): shape(v, k, key) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v) for v in value[:3]]
    return type(value).__name__


def print_shapes(path, limit=40):
    seen = []
    for rec in load(path, new_stats()) or []:
        line = json.dumps(shape(rec), sort_keys=True)
        if line not in seen and len(seen) < limit:
            seen.append(line)
            print(line)


def unavailable(name, s):
    missing = set(UNAVAILABLE[name])
    if not s["tokens_seen"]:
        missing.add("tokens")
    if not s["cost_sessions"]:
        missing.add("cost")
    return missing


def drift(name, s):
    if s["sessions"] < DRIFT_MIN_SESSIONS:
        return {}
    return {shape: metrics for shape, key, metrics in EXPECTED[name] if not s[key]}


def merged_links(stats, merged):
    by_url = {text(pr.get("url")).rstrip("/"): pr["url"] for pr in merged if text(pr.get("url"))}
    heads = collections.Counter(text(pr.get("headRefName")) for pr in merged)
    by_branch = {pr["headRefName"]: pr["url"] for pr in merged
                 if text(pr.get("url")) and text(pr.get("headRefName")) and heads[pr["headRefName"]] == 1
                 and pr.get("isCrossRepository") is False}
    linked_sessions, linked_prs = 0, set()
    for s in stats.values():
        for urls, branches in s["links"]:
            if urls:
                prs = {by_url[u] for u in urls if u in by_url}
            else:
                prs = {by_branch[b] for b in branches if b in by_branch}
            linked_sessions += bool(prs)
            linked_prs |= prs
    return linked_sessions, len(linked_prs)


def render(repo, since_label, stats, merged, runs=None):
    rows = [
        ("Sessions", None, "sessions"),
        ("Subagent transcripts", "subagents", "subagents"),
        ("Input tokens (uncached)", "tokens", "input"),
        ("Cache write tokens", "tokens", "cache_write"),
        ("Cache read tokens", "tokens", "cache_read"),
        ("Output tokens", "tokens", "output"),
        ("Cost, USD (harness estimate)", "cost", "cost"),
        ("Tool calls", "tool_calls", "tool_calls"),
        ("Failed tool calls", "failed", "failed"),
        ("API retries", "retries", "retries"),
        ("Escalations (questions to the user)", "escalations", "escalations"),
    ]
    drifted = {name: drift(name, stats[name]) for name in HARNESSES}
    unverified = {name: set().union(*drifted[name].values()) for name in HARNESSES}
    missing = {name: unavailable(name, stats[name]) - unverified[name] for name in HARNESSES}
    shown = [name for name in HARNESSES if name not in OPTIONAL_HARNESSES or stats[name]["found"]]
    out = [
        f"# Agent analytics: {os.path.basename(repo.rstrip('/'))}",
        "",
        f"Generated {datetime.date.today().isoformat()} by agent-analytics. Period: {since_label}.",
        "Totals only. Factory runs come from their run records; they keep no transcript.",
        "",
        *render_runs(runs),
        "## Sessions",
        "",
        "From transcript counter fields. Totals sum the harnesses where a metric is available.",
        "",
        "| Metric | " + " | ".join(shown) + " | Total |",
        "| --- |" + " ---: |" * (len(shown) + 1),
    ]
    for label, metric, key in rows:
        fmt = (lambda v: f"{v:.2f}") if metric == "cost" else (lambda v: f"{v:,}")
        cells, values = [], []
        for name in shown:
            if not stats[name]["found"]:
                cells.append("not found")
            elif metric in unverified[name]:
                cells.append("unverified")
            elif metric in missing[name]:
                cells.append("unavailable")
            else:
                values.append(stats[name][key])
                cells.append(fmt(values[-1]))
        total = fmt(sum(values)) if values else "unavailable"
        out.append(f"| {label} | " + " | ".join(cells) + f" | {total} |")

    if any(drifted.values()):
        out += ["", "## Format drift", ""]
        for name in HARNESSES:
            for shape in sorted(drifted[name]):
                out.append(f"- {name}: no {shape} in {stats[name]['sessions']} sessions; format may have changed. "
                           f"Unverified: {', '.join(sorted(drifted[name][shape]))}.")

    out += ["", "## Coverage", ""]
    for name in HARNESSES:
        s = stats[name]
        skipped = f" {s['unreadable']} unreadable transcript files skipped." if s["unreadable"] else ""
        if not s["found"]:
            out.append(f"- {name}: no transcripts found for this repo.{skipped}")
            continue
        listed = ", ".join(sorted(missing[name])) or "none"
        line = f"- {name}: {s['sessions']} sessions, {s['subagents']} subagent transcripts. Unavailable: {listed}."
        if name == "Claude Code":
            line += f" Cost reported by {s['cost_sessions']} of {s['sessions']} sessions."
        out.append(line + skipped)

    out += ["", "## PR linking", ""]
    if merged is None:
        out.append("- Sessions per merged PR: unavailable (no merged PR list given).")
    else:
        linked_sessions, linked_prs = merged_links(stats, merged)
        out.append(f"- Merged PRs in list: {len(merged)}; with an explicitly linked session: {linked_prs}.")
        out.append(f"- Sessions linked to a merged PR (PR URL, else a unique same-repo head branch): {linked_sessions}.")
        per_pr = f"{linked_sessions / linked_prs:.1f}" if linked_prs else "unavailable (no session is linked to a merged PR)"
        out.append(f"- Sessions per merged PR: {per_pr}.")
    return "\n".join(out) + "\n"


def read_merged(source):
    try:
        if source == "-":
            data = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as f:
                data = json.load(f)
    except (OSError, ValueError):
        sys.exit("agent_analytics: merged PR list is unreadable or not JSON")
    if not isinstance(data, list) or not all(isinstance(pr, dict) for pr in data):
        sys.exit("agent_analytics: merged PR list must be a JSON array of objects")
    return data


def default_repo():
    # $PWD keeps a symlinked checkout's logical path, which harnesses may record instead of getcwd().
    pwd = os.environ.get("PWD")
    return pwd if pwd and os.path.isabs(pwd) and os.path.realpath(pwd) == os.getcwd() else os.getcwd()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=default_repo(), help="repo root (default: cwd)")
    ap.add_argument("--since", help="YYYY-MM-DD; only transcripts modified on or after it")
    ap.add_argument("--merged", help="file or - with JSON from `gh pr list --state merged --json url,headRefName,isCrossRepository`")
    ap.add_argument("--shape", metavar="FILE", help="print one transcript's record structure (keys, known types, value types) and exit")
    ap.add_argument("--home", default=os.path.expanduser("~"), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.shape:
        print_shapes(args.shape)
        return 0
    since = None
    if args.since:
        since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    merged = read_merged(args.merged) if args.merged else None
    stats = {
        "Claude Code": claude(args.home, args.repo, since),
        "Codex": codex(args.home, args.repo, since),
        "Cursor": cursor(args.home, args.repo, since),
        "Antigravity": antigravity(args.home, args.repo, since),
    }
    since_label = f"transcripts modified since {args.since}" if args.since else "all local transcripts"
    runs = factory_runs(args.repo, args.since)
    sys.stdout.write(render(os.path.realpath(args.repo), since_label, stats, merged, runs))
    if any(drift(name, stats[name]) for name in HARNESSES):
        sys.stderr.write("agent_analytics: format drift detected; see the report's Format drift section\n")
        return DRIFT_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main())
