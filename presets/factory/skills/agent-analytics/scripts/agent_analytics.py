#!/usr/bin/env python3
"""Count agent sessions, tokens, cost and tool outcomes for one repo from local transcripts."""
# Reads only counter and structural fields; never prints message text or paths outside the repo.
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

HARNESSES = ("Claude Code", "Codex", "Cursor")
UNAVAILABLE = {
    "Claude Code": set(),
    "Codex": {"cost", "failed", "retries"},
    "Cursor": {"tokens", "cost", "failed", "retries", "escalations", "links"},
}
ESCALATION_TOOLS = {
    "Claude Code": {"AskUserQuestion"},
    "Codex": {"request_user_input", "request_user_input_async"},
}
CODEX_CHILD_THREADS = {"subagent", "guardian_review"}
TOKEN_KEYS = ("input", "cache_write", "cache_read", "output")


def new_stats():
    return {
        "found": False, "sessions": 0, "subagents": 0, "unreadable": 0, "tokens_seen": False,
        "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "cost": 0.0,
        "cost_sessions": 0, "tool_calls": 0, "failed": 0, "retries": 0, "escalations": 0,
        "links": [],
    }


def is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def num(value):
    return value if is_num(value) else 0


def text(value):
    return value if isinstance(value, str) and value else None


def load(path, stats):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        stats["unreadable"] += 1
        return None
    out = []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def repo_roots(repo):
    return {os.path.normpath(os.path.abspath(repo)), os.path.realpath(repo)}


def in_repo(cwd, repo):
    if not text(cwd) or "\0" in cwd or not os.path.isabs(cwd):
        return False
    real, root = os.path.realpath(cwd), os.path.realpath(repo)
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def first_cwd(recs):
    return next((r["cwd"] for r in recs if text(r.get("cwd"))), None)


def files(pattern, since, stats, recursive=False):
    out = []
    for path in glob.glob(pattern, recursive=recursive):
        try:
            if os.path.isfile(path) and (since is None or os.path.getmtime(path) >= since):
                out.append(path)
        except OSError:
            stats["unreadable"] += 1
    return sorted(out)


def blocks(rec):
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def new_session():
    return {"usage": {}, "tools": {}, "failed": set(), "retries": set(), "cost": None,
            "urls": set(), "branches": set(), "child": False, "total": None}


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
                if b.get("type") == "tool_result" and b.get("is_error") is True and text(b.get("tool_use_id")):
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
    for root in roots:
        enc = re.sub(r"[^A-Za-z0-9]", "-", root)
        for d in glob.glob(os.path.join(home, ".claude", "projects", enc + "*")):
            name = os.path.basename(d)
            if (name != enc and not name.startswith(enc + "-")) or d in seen:
                continue
            seen.add(d)
            for path in files(os.path.join(d, "*.jsonl"), since, s):
                recs = load(path, s)
                if not recs or not in_repo(first_cwd(recs), repo):
                    continue
                sid = next((r["sessionId"] for r in recs if text(r.get("sessionId"))), path)
                acc = sessions.setdefault(sid, new_session())
                claude_records(recs, path, acc)
                for sub in files(os.path.join(path[:-len(".jsonl")], "subagents", "*.jsonl"), None, s):
                    sub_recs = load(sub, s)
                    cwd = first_cwd(sub_recs or [])
                    if sub_recs and (cwd is None or in_repo(cwd, repo)):
                        s["subagents"] += 1
                        claude_records(sub_recs, sub, acc)
    for acc in sessions.values():
        s["found"] = True
        s["sessions"] += 1
        for u in acc["usage"].values():
            s["tokens_seen"] = True
            for key, value in zip(TOKEN_KEYS, u):
                s[key] += value
        s["tool_calls"] += len(acc["tools"])
        s["failed"] += len(acc["failed"] & acc["tools"].keys())
        s["retries"] += len(acc["retries"])
        s["escalations"] += sum(n in ESCALATION_TOOLS["Claude Code"] for n in acc["tools"].values())
        if acc["cost"] is not None:
            s["cost"] += acc["cost"]
            s["cost_sessions"] += 1
        s["links"].append((acc["urls"], acc["branches"]))
    return s


def codex(home, repo, since):
    s = new_stats()
    sessions = collections.OrderedDict()
    for path in files(os.path.join(home, ".codex", "sessions", "**", "rollout-*.jsonl"), since, s, True):
        recs = load(path, s)
        if not recs or recs[0].get("type") != "session_meta" or not isinstance(recs[0].get("payload"), dict):
            continue
        meta = recs[0]["payload"]
        if not in_repo(meta.get("cwd"), repo):
            continue
        acc = sessions.setdefault(text(meta.get("id")) or text(meta.get("session_id")) or path, new_session())
        acc["child"] = text(meta.get("thread_source")) in CODEX_CHILD_THREADS
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
    seen = set()
    for root in repo_roots(repo):
        enc = re.sub(r"[^A-Za-z0-9]+", "-", root).strip("-")
        for path in files(os.path.join(home, ".cursor", "projects", enc, "agent-transcripts", "**", "*.jsonl"), since, s, True):
            if path in seen:
                continue
            seen.add(path)
            recs = [r for r in load(path, s) or [] if "message" in r or "role" in r]
            if not recs:
                continue
            s["found"] = True
            s["subagents" if os.path.basename(os.path.dirname(path)) == "subagents" else "sessions"] += 1
            s["tool_calls"] += sum(b.get("type") == "tool_use" for rec in recs for b in blocks(rec))
    return s


def unavailable(name, s):
    missing = set(UNAVAILABLE[name])
    if not s["tokens_seen"]:
        missing.add("tokens")
    if not s["cost_sessions"]:
        missing.add("cost")
    return missing


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


def render(repo, since_label, stats, merged):
    rows = [
        ("Sessions", None, "sessions"),
        ("Subagent transcripts", None, "subagents"),
        ("Input tokens (uncached)", "tokens", "input"),
        ("Cache write tokens", "tokens", "cache_write"),
        ("Cache read tokens", "tokens", "cache_read"),
        ("Output tokens", "tokens", "output"),
        ("Cost, USD (harness estimate)", "cost", "cost"),
        ("Tool calls", None, "tool_calls"),
        ("Failed tool calls", "failed", "failed"),
        ("API retries", "retries", "retries"),
        ("Escalations (questions to the user)", "escalations", "escalations"),
    ]
    missing = {name: unavailable(name, stats[name]) for name in HARNESSES}
    out = [
        f"# Agent analytics: {os.path.basename(repo.rstrip('/'))}",
        "",
        f"Generated {datetime.date.today().isoformat()} by agent-analytics. Period: {since_label}.",
        "Totals only, from transcript counter fields. Totals sum the harnesses where a metric is available.",
        "",
        "| Metric | " + " | ".join(HARNESSES) + " | Total |",
        "| --- |" + " ---: |" * (len(HARNESSES) + 1),
    ]
    for label, metric, key in rows:
        fmt = (lambda v: f"{v:.2f}") if metric == "cost" else (lambda v: f"{v:,}")
        cells, values = [], []
        for name in HARNESSES:
            if not stats[name]["found"]:
                cells.append("not found")
            elif metric in missing[name]:
                cells.append("unavailable")
            else:
                values.append(stats[name][key])
                cells.append(fmt(values[-1]))
        total = fmt(sum(values)) if values else "unavailable"
        out.append(f"| {label} | " + " | ".join(cells) + f" | {total} |")

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
    ap.add_argument("--home", default=os.path.expanduser("~"), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    since = None
    if args.since:
        since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    merged = read_merged(args.merged) if args.merged else None
    stats = {
        "Claude Code": claude(args.home, args.repo, since),
        "Codex": codex(args.home, args.repo, since),
        "Cursor": cursor(args.home, args.repo, since),
    }
    since_label = f"transcripts modified since {args.since}" if args.since else "all local transcripts"
    sys.stdout.write(render(os.path.realpath(args.repo), since_label, stats, merged))


if __name__ == "__main__":
    main()
