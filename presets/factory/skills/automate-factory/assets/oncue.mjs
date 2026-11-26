#!/usr/bin/env node
// oncue 0.2.0 1b67f6a4530cd1bf4abbf4e7387ecbdae0b4ff59, built with bun run build:node
// MIT License
//
// Copyright (c) 2026 nejcm
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// src/cli.ts
import { readFileSync as readFileSync2 } from "node:fs";
import { parseArgs } from "node:util";

// src/errors.ts
class OnCueError extends Error {
  name = "OnCueError";
  code;
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

// src/index.ts
import { homedir } from "node:os";
import { isAbsolute as isAbsolute2, posix as posix5, win32 as win323 } from "node:path";

// src/path.ts
import { accessSync, constants, statSync } from "node:fs";
import { dirname, extname, isAbsolute, join } from "node:path";
var DEFAULTS = {
  darwin: ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"],
  win32: []
};
var POSIX_DEFAULTS = ["/usr/local/bin", "/usr/bin", "/bin"];
var WIN_PATHEXT = ".COM;.EXE;.BAT;.CMD";
function runnable(p, windows) {
  try {
    if (!statSync(p).isFile())
      return false;
    if (!windows)
      accessSync(p, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}
function which(cmd, PATH = process.env.PATH ?? "", PATHEXT = process.platform === "win32" ? process.env.PATHEXT ?? WIN_PATHEXT : "") {
  if (!cmd)
    return;
  const windows = PATHEXT !== "";
  const exts = windows ? PATHEXT.split(";").filter(Boolean) : [];
  const names = !windows || exts.some((e) => e.toLowerCase() === extname(cmd).toLowerCase()) ? [cmd] : exts.map((e) => cmd + e);
  const dirs = isAbsolute(cmd) ? [""] : PATH.split(windows ? ";" : ":").filter(Boolean);
  for (const d of dirs)
    for (const n of names) {
      const p = d ? join(d, n) : n;
      if (runnable(p, windows))
        return p;
    }
  return;
}
function capturePath(tools, defaults, {
  PATH = process.env.PATH ?? "",
  PATHEXT,
  platform = process.platform
} = {}) {
  const windows = platform === "win32";
  const ext = windows ? PATHEXT ?? process.env.PATHEXT ?? WIN_PATHEXT : "";
  const found = tools.flatMap((t) => {
    const p = which(t, PATH, ext);
    return p ? [dirname(p)] : [];
  });
  return [...new Set([...found, ...defaults ?? DEFAULTS[platform] ?? POSIX_DEFAULTS])].join(windows ? ";" : ":");
}

// src/backends/launchd.ts
import { posix as posix2 } from "node:path";

// src/quote.ts
var FORBIDDEN = /[\u0000-\u001f\u007f\ufffe\uffff]|[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;
function clean(s) {
  if (FORBIDDEN.test(s))
    throw new OnCueError("INVALID_SPEC", `control or non-XML character in ${JSON.stringify(s)}`);
  return s;
}
var XML = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" };
var xml = (s) => clean(s).replace(/[&<>"']/g, (c) => XML[c]);
var systemdArg = (s, program = false) => {
  const q = clean(s).replace(/[\\"]/g, "\\$&").replace(/%/g, "%%");
  return `"${program ? q : q.replace(/\$/g, "$$$$")}"`;
};
var systemdEnv = (key, value) => `"${`${clean(key)}=${clean(value)}`.replace(/[\\"]/g, "\\$&").replace(/%/g, "%%")}"`;
var systemdText = (s) => {
  if (s.endsWith("\\"))
    throw new OnCueError("INVALID_SPEC", `trailing backslash in ${JSON.stringify(s)}`);
  return clean(s).replace(/%/g, "%%");
};
var ps = (s) => `'${clean(s).replace(/['\u2018\u2019\u201a\u201b]/g, "$&$&")}'`;

// src/sys.ts
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname as dirname2, posix } from "node:path";
var decode = (data) => typeof data === "string" ? data : Buffer.from(data).toString(data[0] === 255 && data[1] === 254 ? "utf16le" : "utf8");
function ensureLogDir(sys, log, path = posix) {
  if (log && log !== "native" && sys.readdir(path.dirname(log)).length === 0)
    sys.write(log, "");
}
var PAUSE = new Int32Array(new SharedArrayBuffer(4));
function poll(probe, ms = 1000) {
  for (;; ) {
    const r = probe();
    if (r !== undefined)
      return r;
    Atomics.wait(PAUSE, 0, 0, ms);
  }
}
var missing = (e) => e.code === "ENOENT";
var realSys = {
  read(path) {
    try {
      return decode(readFileSync(path));
    } catch (e) {
      if (missing(e))
        return;
      throw e;
    }
  },
  readdir(dir) {
    try {
      return readdirSync(dir);
    } catch (e) {
      if (missing(e))
        return [];
      throw e;
    }
  },
  write(path, data) {
    mkdirSync(dirname2(path), { recursive: true });
    const tmp = `${path}.${process.pid}.tmp`;
    writeFileSync(tmp, data);
    renameSync(tmp, path);
  },
  remove(path) {
    rmSync(path, { force: true });
  },
  exec(argv, o) {
    const [cmd, ...args] = argv;
    if (!cmd)
      throw new OnCueError("COMMAND_FAILED", "empty argv");
    const r = spawnSync(cmd, args, { input: o.stdin, encoding: "utf8", windowsHide: true });
    if (r.error) {
      if (missing(r.error))
        throw new OnCueError("NOT_FOUND", `${cmd} not found`);
      throw new OnCueError("COMMAND_FAILED", `${argv.join(" ")}: ${r.error.message}`);
    }
    const res = { code: r.status ?? 128, out: r.stdout, err: r.stderr };
    if (!(o.ok ?? [0]).includes(res.code)) {
      throw new OnCueError("COMMAND_FAILED", `${argv.join(" ")} exited ${res.code}: ${res.err.trim()}`);
    }
    return res;
  }
};
function dryRunSys(inner, log = console.log) {
  return {
    read: (p) => inner.read(p),
    readdir: (d) => inner.readdir(d),
    write: (p) => log(`write ${p}`),
    remove: (p) => log(`remove ${p}`),
    exec(argv, o) {
      if (!o.mutates)
        return inner.exec(argv, o);
      log(`exec ${argv.join(" ")}`);
      return { code: 0, out: "", err: "" };
    }
  };
}

// src/backends/launchd.ts
var WEEKDAYS = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
var MARKER = /^<!-- managed-by oncue ([a-z0-9-]+)\/([a-z0-9-]+) -->$/m;
var dir = (env) => posix2.join(env.home, "Library/LaunchAgents");
var label = (ref) => `${ref.namespace}.${ref.name}`;
var plistPath = (ref, env) => posix2.join(dir(env), `${label(ref)}.plist`);
function owner(text) {
  const m = text?.match(MARKER);
  return m ? `${m[1]}/${m[2]}` : undefined;
}
function domain(env) {
  if (env.uid === undefined)
    throw new OnCueError("NO_BACKEND", "launchd needs the user's uid for the gui/<uid> domain");
  return `gui/${env.uid}`;
}
function posixPath(p, field) {
  if (!posix2.isAbsolute(p))
    throw new OnCueError("INVALID_SPEC", `${field} must be an absolute POSIX path for launchd`);
  return p;
}
var str = (s) => `<string>${xml(s)}</string>`;
var int = (n) => `<integer>${n}</integer>`;
var key = (k, v) => `<key>${k}</key>${v}`;
var calendarDict = (a) => `<dict>${[
  a.weekday !== undefined && key("Weekday", int(WEEKDAYS[a.weekday])),
  a.day !== undefined && key("Day", int(a.day)),
  a.hour !== undefined && key("Hour", int(a.hour)),
  key("Minute", int(a.minute))
].filter(Boolean).join("")}</dict>`;
var slots = (count, step) => Array.from({ length: count }, (_, i) => i * step);
function scheduleKeys(job) {
  const s = job.schedule;
  if (s.kind === "keepAlive") {
    const keep = s.restart === "always" ? "<true/>" : `<dict>${key("SuccessfulExit", "<false/>")}</dict>`;
    return key("KeepAlive", keep) + (s.delaySeconds === undefined ? "" : key("ThrottleInterval", int(s.delaySeconds)));
  }
  let at;
  if (s.kind === "calendar")
    at = s.at;
  else if (60 % s.minutes === 0)
    at = slots(60 / s.minutes, s.minutes).map((minute) => ({ minute }));
  else if (s.minutes % 60 === 0 && 24 % (s.minutes / 60) === 0)
    at = slots(1440 / s.minutes, s.minutes / 60).map((hour) => ({ hour, minute: 0 }));
  else
    return key("StartInterval", int(s.minutes * 60));
  const dicts = at.map(calendarDict);
  return key("StartCalendarInterval", dicts.length === 1 ? dicts[0] : `<array>${dicts.join("")}</array>`);
}
function render(job, env) {
  if (`${job.namespace}/${job.name}`.includes("--"))
    throw new OnCueError("UNSUPPORTED", 'launchd: namespace and name cannot contain "--"');
  if (job.timeout !== undefined)
    throw new OnCueError("UNSUPPORTED", "launchd: timeout is not supported");
  const log = job.log && job.log !== "native" ? posixPath(job.log, "log") : posix2.join(env.home, "Library/Logs", `${job.namespace}-${job.name}.log`);
  const vars = Object.entries(job.env ?? {});
  const schedule = scheduleKeys(job);
  const startInterval = schedule.startsWith("<key>StartInterval</key>");
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
    `<!-- managed-by oncue ${job.namespace}/${job.name} -->`,
    '<plist version="1.0"><dict>',
    key("Label", str(label(job))),
    key("WorkingDirectory", str(posixPath(job.cwd, "cwd"))),
    key("ProgramArguments", `<array>${job.command.map(str).join("")}</array>`),
    ...vars.length ? [key("EnvironmentVariables", `<dict>${vars.map(([k, v]) => key(xml(k), str(v))).join("")}</dict>`)] : [],
    key("StandardOutPath", str(log)),
    key("StandardErrorPath", str(log)),
    schedule,
    ...job.leaveChildrenOnStop ? [key("AbandonProcessGroup", "<true/>")] : [],
    "</dict></plist>"
  ];
  const warnings = job.catchUp === false && job.schedule.kind !== "keepAlive" && !startInterval ? ["launchd always runs a missed calendar slot on wake; catchUp: false is ignored"] : job.catchUp === true && startInterval ? ["launchd StartInterval (unaligned intervals) has no catch-up; catchUp: true is ignored"] : [];
  return { files: [{ path: plistPath(job, env), content: `${lines.join(`
`)}
` }], warnings };
}
var launchctl = (sys, mutates, ...args) => sys.exec(["launchctl", ...args], { mutates });
function print(ref, env, sys) {
  try {
    return launchctl(sys, false, "print", `${domain(env)}/${label(ref)}`).out;
  } catch (e) {
    if (e instanceof OnCueError && e.code === "COMMAND_FAILED")
      return;
    throw e;
  }
}
function bootout(ref, env, sys) {
  try {
    launchctl(sys, true, "bootout", `${domain(env)}/${label(ref)}`);
  } catch (e) {
    if (!(e instanceof OnCueError) || e.code !== "COMMAND_FAILED")
      throw e;
  }
}
var PAUSE2 = new Int32Array(new SharedArrayBuffer(4));
function bootstrap(path, env, sys, retries) {
  const argv = ["launchctl", "bootstrap", domain(env), path];
  try {
    for (let left = retries;sys.exec(argv, { mutates: true, ok: left > 0 ? [0, 5] : [0] }).code === 5; left--)
      Atomics.wait(PAUSE2, 0, 0, 500);
  } catch (e) {
    if (e instanceof OnCueError && e.code === "COMMAND_FAILED") {
      throw new OnCueError("COMMAND_FAILED", `${e.message} (LaunchAgents need a logged-in GUI session; over SSH there may be no ${domain(env)} domain)`);
    }
    throw e;
  }
}
function install(job, env, sys) {
  const r = render(job, env);
  const f = r.files[0];
  const cur = sys.read(f.path);
  const by = owner(cur);
  if (by && by !== `${job.namespace}/${job.name}`)
    throw new OnCueError("INVALID_SPEC", `${f.path} belongs to oncue job ${by}`);
  const loaded = print(job, env, sys) !== undefined;
  if (cur === f.content && loaded)
    return { changed: false, warnings: r.warnings };
  ensureLogDir(sys, job.log);
  if (cur !== f.content)
    sys.write(f.path, f.content);
  if (loaded)
    bootout(job, env, sys);
  bootstrap(f.path, env, sys, loaded ? 4 : 0);
  return { changed: true, warnings: r.warnings };
}
function uninstall(ref, env, sys) {
  const path = plistPath(ref, env);
  const text = sys.read(path);
  if (text === undefined)
    return { removed: false };
  if (owner(text) !== `${ref.namespace}/${ref.name}`)
    throw new OnCueError("INVALID_SPEC", `${path} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  bootout(ref, env, sys);
  sys.remove(path);
  return { removed: true };
}
var running = (native) => /^\s*state = running/m.test(native);
var runs = (native) => native.match(/^\s*runs = (\d+)/m)?.[1];
function status(ref, env, sys) {
  const text = sys.read(plistPath(ref, env));
  if (owner(text) !== `${ref.namespace}/${ref.name}`)
    return { installed: false, active: false, warnings: [], native: "" };
  const native = print(ref, env, sys);
  if (native === undefined)
    return { installed: true, active: false, warnings: [], native: "" };
  const exit = native.match(/^\s*last exit code = (\d+)/m);
  const keepAlive = text.includes("<key>KeepAlive</key>");
  return {
    installed: true,
    active: keepAlive ? running(native) : true,
    lastExit: exit ? Number(exit[1]) : undefined,
    warnings: [],
    native
  };
}
function run(ref, env, sys, wait) {
  const text = sys.read(plistPath(ref, env));
  if (text === undefined)
    throw new OnCueError("NOT_FOUND", `${ref.namespace}/${ref.name} is not installed`);
  if (owner(text) !== `${ref.namespace}/${ref.name}`)
    throw new OnCueError("INVALID_SPEC", `${plistPath(ref, env)} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  const target = `${domain(env)}/${label(ref)}`;
  if (!wait) {
    launchctl(sys, true, "kickstart", target);
    return {};
  }
  if (text.includes("<key>KeepAlive</key>"))
    throw new OnCueError("UNSUPPORTED", "run --wait does not apply to keepAlive jobs");
  const fail = (why) => new OnCueError("COMMAND_FAILED", `${target}: ${why}`);
  const before = print(ref, env, sys);
  if (before === undefined)
    throw fail("not loaded");
  const n0 = Number(runs(before) ?? NaN);
  if (Number.isNaN(n0))
    throw fail("launchctl print shows no run count");
  if (running(before))
    throw fail("already running; no new run started");
  launchctl(sys, true, "kickstart", target);
  return poll(() => {
    const now = print(ref, env, sys) ?? "";
    const n = Number(runs(now) ?? NaN);
    if (Number.isNaN(n))
      throw fail("launchctl print shows no run count");
    if (n > n0 + 1)
      throw fail("another run ended before this one's result was read");
    if (n < n0)
      throw fail("run count went down; the job was reloaded");
    if (running(now) || /^\s*state = spawn scheduled/m.test(now))
      return;
    if (n === n0)
      throw fail("kickstart started no new run");
    const signal = now.match(/^\s*last terminating signal = (.*)$/m);
    if (signal)
      throw fail(`run ended by signal ${signal[1]}`);
    const exit = now.match(/^\s*last exit code = (\d+)/m);
    if (!exit)
      throw fail("launchctl print reports no exit code");
    return { exit: Number(exit[1]) };
  });
}
function list(namespace, env, sys) {
  const names = sys.readdir(dir(env)).filter((f) => f.startsWith(`${namespace}.`) && f.endsWith(".plist")).flatMap((f) => {
    const m = sys.read(posix2.join(dir(env), f))?.match(MARKER);
    return m && m[1] === namespace && f === `${namespace}.${m[2]}.plist` ? [m[2]] : [];
  });
  names.sort();
  return names;
}
var launchd = {
  id: "launchd",
  platforms: ["darwin"],
  available(sys) {
    try {
      launchctl(sys, false, "version");
      return true;
    } catch (e) {
      return e instanceof OnCueError && e.code === "COMMAND_FAILED";
    }
  },
  render,
  install,
  uninstall,
  status,
  list,
  run
};

// src/backends/schtasks.ts
import { win32 as win322 } from "node:path";

// src/validate.ts
import { posix as posix3, win32 } from "node:path";
var NAME = /^[a-z0-9][a-z0-9-]{0,30}$/;
var ENV_KEY = /^[A-Za-z_][A-Za-z0-9_]*$/;
var WEEKDAYS2 = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
var JOB_KEYS = [
  "namespace",
  "name",
  "description",
  "command",
  "cwd",
  "env",
  "log",
  "schedule",
  "catchUp",
  "timeout",
  "leaveChildrenOnStop"
];
var fail = (msg) => {
  throw new OnCueError("INVALID_SPEC", msg);
};
var isObj = (v) => typeof v === "object" && v !== null && !Array.isArray(v);
var isAbs = (p) => posix3.isAbsolute(p) || win32.isAbsolute(p);
var isInt = (v, min, max) => Number.isInteger(v) && v >= min && v <= max;
function onlyKeys(o, allowed, where) {
  for (const k of Object.keys(o))
    if (!allowed.includes(k))
      fail(`unknown field ${where}${k}`);
}
function optInt(o, key, min, max, where) {
  if (o[key] !== undefined && !isInt(o[key], min, max))
    fail(`${where}.${key} must be an integer ${min}..${max}`);
}
function validateName(value, field = "name") {
  if (typeof value !== "string" || !NAME.test(value))
    fail(`${field} must match ${NAME}`);
  return value;
}
function validateJob(input, opts = {}) {
  if (!isObj(input))
    return fail("job must be an object");
  const j = input;
  onlyKeys(j, JOB_KEYS, "");
  for (const k of ["namespace", "name"])
    validateName(j[k], k);
  if (j.description !== undefined && typeof j.description !== "string")
    fail("description must be a string");
  const cmd = j.command;
  if (!Array.isArray(cmd) || cmd.length === 0 || !cmd.every((a) => typeof a === "string")) {
    fail("command must be a non-empty array of strings");
  }
  if (cmd[0] === "")
    fail("command[0] must not be empty");
  if (opts.install && !isAbs(cmd[0]))
    fail("command[0] must be absolute");
  if (typeof j.cwd !== "string" || !isAbs(j.cwd))
    fail("cwd must be an absolute path");
  if (j.env !== undefined) {
    if (!isObj(j.env))
      fail("env must be an object");
    for (const [k, v] of Object.entries(j.env)) {
      if (!ENV_KEY.test(k))
        fail(`env key ${JSON.stringify(k)} is not a valid name`);
      if (typeof v !== "string")
        fail(`env.${k} must be a string`);
    }
  }
  if (j.log !== undefined && (typeof j.log !== "string" || j.log !== "native" && !isAbs(j.log))) {
    fail('log must be "native" or an absolute path');
  }
  for (const k of ["catchUp", "leaveChildrenOnStop"]) {
    if (j[k] !== undefined && typeof j[k] !== "boolean")
      fail(`${k} must be a boolean`);
  }
  if (j.timeout !== undefined && !isInt(j.timeout, 1, 10080))
    fail("timeout must be an integer 1..10080");
  const s = j.schedule;
  if (!isObj(s))
    return fail("schedule must be an object");
  if (s.kind === "interval") {
    onlyKeys(s, ["kind", "minutes"], "schedule.");
    if (!isInt(s.minutes, 1, 44640))
      fail("schedule.minutes must be an integer 1..44640");
  } else if (s.kind === "calendar") {
    onlyKeys(s, ["kind", "at"], "schedule.");
    if (!Array.isArray(s.at) || s.at.length === 0)
      fail("schedule.at must be a non-empty array");
    s.at.forEach((a, i) => {
      const where = `schedule.at[${i}]`;
      if (!isObj(a))
        return fail(`${where} must be an object`);
      onlyKeys(a, ["minute", "hour", "weekday", "day"], `${where}.`);
      if (!isInt(a.minute, 0, 59))
        fail(`${where}.minute must be an integer 0..59`);
      optInt(a, "hour", 0, 23, where);
      optInt(a, "day", 1, 31, where);
      if (a.weekday !== undefined && !WEEKDAYS2.includes(a.weekday))
        fail(`${where}.weekday must be one of ${WEEKDAYS2}`);
      if (a.weekday !== undefined && a.day !== undefined)
        fail(`${where}: weekday and day cannot be combined`);
    });
  } else if (s.kind === "keepAlive") {
    onlyKeys(s, ["kind", "restart", "delaySeconds"], "schedule.");
    if (s.restart !== "always" && s.restart !== "on-failure")
      fail('schedule.restart must be "always" or "on-failure"');
    optInt(s, "delaySeconds", 0, 86400, "schedule");
    if (j.catchUp !== undefined)
      fail("catchUp applies to timers only");
    if (j.timeout !== undefined)
      fail("timeout applies to timers only");
  } else {
    fail('schedule.kind must be "interval", "calendar" or "keepAlive"');
  }
  return j;
}

// src/backends/schtasks.ts
var DAYS = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday"
};
var MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
];
var MARKER2 = /^managed-by oncue ([a-z0-9-]+)\/([a-z0-9-]+)$/;
var ENV_KEY2 = /^[A-Za-z_][A-Za-z0-9_]*$/;
var EPOCH = "2000-01-01T00:00:00";
var marker = (ref) => `managed-by oncue ${ref.namespace}/${ref.name}`;
var taskName = (ref) => `\\${ref.namespace}\\${ref.name}`;
var pad = (n) => String(n).padStart(2, "0");
function dir2(ref, env) {
  if (!env.localAppData)
    throw new OnCueError("NO_BACKEND", "Task Scheduler backend needs %LOCALAPPDATA%");
  return win322.join(env.localAppData, "oncue", ref.namespace);
}
var paths = (ref, env) => ({
  ps1: win322.join(dir2(ref, env), `${ref.name}.ps1`),
  xml: win322.join(dir2(ref, env), `${ref.name}.xml`)
});
function winPath(p, field) {
  if (!/^(?:[a-z]:[\\/]|[\\/]{2}[^\\/]+[\\/][^\\/]+)/i.test(p))
    throw new OnCueError("INVALID_SPEC", `${field} must be an absolute Windows path (drive or UNC) for Task Scheduler`);
  return p;
}
function nativeArg(a) {
  if (a === "" || a.includes('"') || /\s/.test(a) && a.endsWith("\\")) {
    throw new OnCueError("UNSUPPORTED", `Task Scheduler: argument ${JSON.stringify(a)} cannot be passed through Windows PowerShell`);
  }
  return ps(a);
}
var BATCH_META = /[%!&|<>^]/;
function batchSafe(command) {
  if (!/\.(bat|cmd)$/i.test(command[0]))
    return;
  const bad = command.find((a) => BATCH_META.test(a));
  if (bad !== undefined)
    throw new OnCueError("UNSUPPORTED", `Task Scheduler: ${JSON.stringify(bad)} cannot be passed safely to a batch file (% ! & | < > ^)`);
}
var el = (tag, body) => `<${tag}>${body}</${tag}>`;
var repetition = (interval, duration) => el("Repetition", el("Interval", interval) + (duration ? el("Duration", duration) : ""));
function calendarTrigger(a) {
  const start = el("StartBoundary", `2000-01-01T${pad(a.hour ?? 0)}:${pad(a.minute)}:00`);
  const hourly = a.hour === undefined ? repetition("PT1H", "P1D") : "";
  const by = a.weekday !== undefined ? el("ScheduleByWeek", el("DaysOfWeek", `<${DAYS[a.weekday]}/>`) + el("WeeksInterval", "1")) : a.day !== undefined ? el("ScheduleByMonth", el("DaysOfMonth", el("Day", String(a.day))) + el("Months", MONTHS.map((m) => `<${m}/>`).join(""))) : el("ScheduleByDay", el("DaysInterval", "1"));
  return el("CalendarTrigger", hourly + start + by);
}
function triggers(job, env) {
  const s = job.schedule;
  if (s.kind === "calendar")
    return s.at.map(calendarTrigger);
  if (s.kind === "interval")
    return [el("TimeTrigger", repetition(`PT${s.minutes}M`) + el("StartBoundary", EPOCH))];
  if (!env.user)
    throw new OnCueError("NO_BACKEND", "Task Scheduler keepAlive needs the user name for its logon trigger");
  return [
    el("LogonTrigger", el("UserId", xml(env.user))),
    el("TimeTrigger", repetition(`PT${Math.max(1, Math.ceil((s.delaySeconds ?? 0) / 60))}M`) + el("StartBoundary", EPOCH))
  ];
}
function render2(job, env) {
  const p = paths(job, env);
  const keepAlive = job.schedule.kind === "keepAlive";
  const log = job.log && job.log !== "native" ? winPath(job.log, "log") : win322.join(dir2(job, env), `${job.name}.log`);
  const cwd = winPath(job.cwd, "cwd");
  const command = job.command.map(nativeArg);
  batchSafe(job.command);
  const vars = Object.entries(job.env ?? {}).map(([k, v]) => {
    if (!ENV_KEY2.test(k))
      throw new OnCueError("INVALID_SPEC", `env key ${JSON.stringify(k)} is not a valid name`);
    return `$env:${k} = ${ps(v)}`;
  });
  const script = [
    `# ${marker(job)}`,
    ...vars,
    `Set-Location -LiteralPath ${ps(cwd)}`,
    "try {",
    `  & ${command.join(" ")} 2>&1 | ForEach-Object { "$_" } | Out-File -LiteralPath ${ps(log)} -Append -Encoding utf8`,
    "} catch {",
    `  "$_" | Out-File -LiteralPath ${ps(log)} -Append -Encoding utf8`,
    "  exit 1",
    "}",
    "exit $LASTEXITCODE"
  ];
  const settings = [
    el("MultipleInstancesPolicy", "IgnoreNew"),
    el("DisallowStartIfOnBatteries", "false"),
    el("StopIfGoingOnBatteries", "false"),
    el("StartWhenAvailable", String(job.catchUp !== false)),
    ...keepAlive ? [el("ExecutionTimeLimit", "PT0S"), el("RestartOnFailure", el("Interval", "PT1M") + el("Count", "3"))] : job.timeout ? [el("ExecutionTimeLimit", `PT${job.timeout}M`)] : [],
    el("Enabled", "true")
  ];
  const task = [
    '<?xml version="1.0" encoding="UTF-16"?>',
    '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">',
    `  <RegistrationInfo>${el("Source", marker(job))}${job.description === undefined ? "" : el("Description", xml(job.description))}</RegistrationInfo>`,
    "  <Triggers>",
    ...triggers(job, env).map((t) => `    ${t}`),
    "  </Triggers>",
    `  <Principals><Principal id="Author">${el("LogonType", "InteractiveToken")}${el("RunLevel", "LeastPrivilege")}</Principal></Principals>`,
    "  <Settings>",
    ...settings.map((s) => `    ${s}`),
    "  </Settings>",
    '  <Actions Context="Author">',
    "    <Exec>",
    `      ${el("Command", "powershell.exe")}`,
    `      ${el("Arguments", xml(`-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${p.ps1}"`))}`,
    `      ${el("WorkingDirectory", xml(cwd))}`,
    "    </Exec>",
    "  </Actions>",
    "</Task>"
  ];
  const warnings = [
    ...job.schedule.kind === "keepAlive" && job.schedule.restart === "on-failure" ? ["Task Scheduler relaunches keepAlive jobs after any exit; restart: on-failure behaves as always"] : [],
    ...job.leaveChildrenOnStop ? ["Task Scheduler: leaveChildrenOnStop is ignored"] : []
  ];
  return {
    files: [
      { path: p.ps1, content: `\uFEFF${script.join(`
`)}
` },
      { path: p.xml, content: Buffer.from(`\uFEFF${task.join(`
`)}
`, "utf16le") }
    ],
    warnings
  };
}
var schtasks = (sys, ...args) => sys.exec(["schtasks.exe", ...args], { mutates: true });
function mayFail(sys, ...args) {
  try {
    schtasks(sys, ...args);
  } catch (e) {
    if (!(e instanceof OnCueError) || e.code !== "COMMAND_FAILED")
      throw e;
  }
}
var query = (namespace) => `$ErrorActionPreference = 'Stop'; ConvertTo-Json -Compress -InputObject @(Get-ScheduledTask -TaskPath '\\${validateName(namespace, "namespace")}\\' -ErrorAction SilentlyContinue | ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; [pscustomobject]@{ Name = $_.TaskName; Source = $_.Source; State = [string]$_.State; LastRun = if ($i.LastRunTime) { ([DateTimeOffset]$i.LastRunTime).ToUnixTimeSeconds() }; LastResult = $i.LastTaskResult; NextRun = if ($i.NextRunTime) { ([DateTimeOffset]$i.NextRunTime).ToUnixTimeSeconds() } } })`;
function tasks(namespace, sys) {
  const native = sys.exec(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query(namespace)], {
    mutates: false
  }).out;
  return { tasks: native.trim() ? JSON.parse(native) : [], native };
}
function owner2(t) {
  const m = t?.Source?.match(MARKER2);
  return m ? `${m[1]}/${m[2]}` : undefined;
}
var find = (ref, sys) => {
  const r = tasks(ref.namespace, sys);
  return { task: r.tasks.find((t) => t.Name === ref.name), native: r.native };
};
function install2(job, env, sys) {
  const r = render2(job, env);
  const ref = `${job.namespace}/${job.name}`;
  const { task } = find(job, sys);
  const by = owner2(task);
  if (by && by !== ref)
    throw new OnCueError("INVALID_SPEC", `task ${taskName(job)} belongs to oncue job ${by}`);
  const xmlPath = paths(job, env).xml;
  const pending = r.files.filter((f) => sys.read(f.path) !== decode(f.content));
  const keepAlive = job.schedule.kind === "keepAlive";
  const live = task?.State !== "Disabled" && (!keepAlive || task?.State === "Running");
  if (pending.length === 0 && by === ref && live)
    return { changed: false, warnings: r.warnings };
  const wasKeepAlive = sys.read(xmlPath)?.includes("<LogonTrigger>") ?? false;
  ensureLogDir(sys, job.log, win322);
  for (const f of pending)
    sys.write(f.path, f.content);
  schtasks(sys, "/create", "/tn", taskName(job), "/xml", xmlPath, "/f");
  if (keepAlive || wasKeepAlive)
    mayFail(sys, "/end", "/tn", taskName(job));
  if (keepAlive)
    schtasks(sys, "/run", "/tn", taskName(job));
  return { changed: true, warnings: r.warnings };
}
function uninstall2(ref, env, sys) {
  const p = paths(ref, env);
  const { task } = find(ref, sys);
  const texts = [p.ps1, p.xml].map((path) => ({ path, text: sys.read(path) })).filter((f) => f.text !== undefined);
  const files = texts.map((f) => f.path);
  if (!task && files.length === 0)
    return { removed: false };
  const unmarked = texts.find((f) => !f.text.includes(`# ${marker(ref)}
`) && !f.text.includes(`<Source>${marker(ref)}</Source>`));
  if (unmarked)
    throw new OnCueError("INVALID_SPEC", `${unmarked.path} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  if (task && owner2(task) !== `${ref.namespace}/${ref.name}`) {
    throw new OnCueError("INVALID_SPEC", `task ${taskName(ref)} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  }
  if (task) {
    mayFail(sys, "/end", "/tn", taskName(ref));
    schtasks(sys, "/delete", "/tn", taskName(ref), "/f");
  }
  for (const f of files)
    sys.remove(f);
  return { removed: true };
}
var unixDate = (s) => s && s >= 946684800 ? new Date(s * 1000) : undefined;
function status2(ref, env, sys) {
  const { task, native } = find(ref, sys);
  if (!task || owner2(task) !== `${ref.namespace}/${ref.name}`)
    return { installed: false, active: false, warnings: [], native: "" };
  const keepAlive = sys.read(paths(ref, env).xml)?.includes("<LogonTrigger>") ?? false;
  const lastRun = unixDate(task.LastRun);
  return {
    installed: true,
    active: keepAlive ? task.State === "Running" : task.State === "Ready" || task.State === "Running",
    lastExit: lastRun && task.LastResult !== null ? task.LastResult : undefined,
    lastRun,
    nextRun: unixDate(task.NextRun),
    warnings: [],
    native
  };
}
function run2(ref, env, sys, wait) {
  if (wait)
    throw new OnCueError("UNSUPPORTED", "Task Scheduler: run --wait is not supported");
  const { task } = find(ref, sys);
  if (!task)
    throw new OnCueError("NOT_FOUND", `${ref.namespace}/${ref.name} is not installed`);
  const p = paths(ref, env);
  const unmarked = owner2(task) !== `${ref.namespace}/${ref.name}` ? `task ${taskName(ref)}` : !sys.read(p.ps1)?.includes(`# ${marker(ref)}
`) ? p.ps1 : !sys.read(p.xml)?.includes(`<Source>${marker(ref)}</Source>`) ? p.xml : undefined;
  if (unmarked)
    throw new OnCueError("INVALID_SPEC", `${unmarked} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  schtasks(sys, "/run", "/tn", taskName(ref));
  return {};
}
function list2(namespace, _env, sys) {
  const names = tasks(namespace, sys).tasks.filter((t) => owner2(t) === `${namespace}/${t.Name}`).map((t) => t.Name);
  names.sort();
  return names;
}
var taskScheduler = {
  id: "schtasks",
  platforms: ["win32"],
  available(sys) {
    try {
      sys.exec(["schtasks.exe", "/?"], { mutates: false });
      return true;
    } catch (e) {
      return e instanceof OnCueError && e.code === "COMMAND_FAILED";
    }
  },
  render: render2,
  install: install2,
  uninstall: uninstall2,
  status: status2,
  list: list2,
  run: run2
};

// src/backends/systemd.ts
import { posix as posix4 } from "node:path";
var DAYS2 = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };
var MARKER3 = /^# managed-by oncue ([a-z0-9-]+)\/([a-z0-9-]+)$/m;
var dir3 = (env) => posix4.join(env.home, ".config/systemd/user");
var unit = (ref) => `${ref.namespace}-${ref.name}`;
var marker2 = (ref) => `# managed-by oncue ${ref.namespace}/${ref.name}`;
var pad2 = (n) => String(n).padStart(2, "0");
function owner3(text) {
  const m = text?.match(MARKER3);
  return m ? `${m[1]}/${m[2]}` : undefined;
}
function posixPath2(p, field) {
  if (!posix4.isAbsolute(p))
    throw new OnCueError("INVALID_SPEC", `${field} must be an absolute POSIX path for systemd`);
  if (p.endsWith(" "))
    throw new OnCueError("UNSUPPORTED", `systemd: ${field} ${JSON.stringify(p)} ends with a space`);
  return systemdText(p);
}
var calendar = (a) => `${a.weekday ? `${DAYS2[a.weekday]} ` : ""}*-*-${a.day === undefined ? "*" : pad2(a.day)} ${a.hour === undefined ? "*" : pad2(a.hour)}:${pad2(a.minute)}`;
function timerLines(job) {
  const s = job.schedule;
  const persistent = job.catchUp === false ? [] : ["Persistent=true"];
  if (s.kind === "calendar")
    return [...s.at.map((a) => `OnCalendar=${calendar(a)}`), ...persistent];
  if (s.kind !== "interval")
    return [];
  const n = s.minutes;
  if (n % 60 === 0 && 24 % (n / 60) === 0)
    return [`OnCalendar=*-*-* ${n === 1440 ? "00" : `0/${n / 60}`}:00`, ...persistent];
  if (60 % n === 0)
    return [`OnCalendar=*:0/${n}`, ...persistent];
  return [`OnStartupSec=${n}min`, `OnUnitActiveSec=${n}min`];
}
function render3(job, env) {
  const u = posix4.join(dir3(env), unit(job));
  const desc = `Description=${systemdText(job.description ?? `${job.namespace}/${job.name}`)}`;
  const s = job.schedule;
  const log = job.log && job.log !== "native" ? `append:${posixPath2(job.log, "log")}` : undefined;
  const service = [
    marker2(job),
    "[Unit]",
    desc,
    "",
    "[Service]",
    `Type=${s.kind === "keepAlive" ? "simple" : "oneshot"}`,
    `WorkingDirectory=${posixPath2(job.cwd, "cwd")}`,
    `ExecStart=${job.command.map((c, i) => systemdArg(c, i === 0)).join(" ")}`,
    ...Object.entries(job.env ?? {}).map(([k, v]) => `Environment=${systemdEnv(k, v)}`),
    ...log ? [`StandardOutput=${log}`, `StandardError=${log}`] : [],
    ...s.kind === "keepAlive" ? [`Restart=${s.restart}`] : [],
    ...s.kind === "keepAlive" && s.delaySeconds !== undefined ? [`RestartSec=${s.delaySeconds}`] : [],
    ...job.timeout ? [`TimeoutStartSec=${job.timeout}min`] : [],
    ...job.leaveChildrenOnStop ? ["KillMode=process"] : [],
    ...s.kind === "keepAlive" ? ["", "[Install]", "WantedBy=default.target"] : []
  ];
  const files = [{ path: `${u}.service`, content: `${service.join(`
`)}
` }];
  const timerKeys = timerLines(job);
  if (s.kind !== "keepAlive") {
    const timer = [marker2(job), "[Unit]", desc, "", "[Timer]", ...timerKeys, "", "[Install]", "WantedBy=timers.target"];
    files.push({ path: `${u}.timer`, content: `${timer.join(`
`)}
` });
  }
  const monotonic = timerKeys[0]?.startsWith("OnStartupSec") ?? false;
  const warnings = job.catchUp === true && monotonic ? ["systemd: unaligned intervals use monotonic timers, which cannot catch up; catchUp: true is ignored"] : [];
  return { files, warnings };
}
var systemctl = (sys, mutates, ...args) => sys.exec(["systemctl", "--user", ...args], { mutates });
function mayFail2(sys, ...args) {
  try {
    systemctl(sys, true, ...args);
  } catch (e) {
    if (!(e instanceof OnCueError) || e.code !== "COMMAND_FAILED")
      throw e;
  }
}
function show(sys, units, props, unix = false) {
  const args = ["show", ...units, "-p", props.join(",")];
  let native;
  try {
    native = systemctl(sys, false, ...args, ...unix ? ["--timestamp=unix"] : []).out;
  } catch (e) {
    if (!unix || !(e instanceof OnCueError) || e.code !== "COMMAND_FAILED")
      throw e;
    native = systemctl(sys, false, ...args).out;
  }
  const blocks = native.split(/\n\n/).map((b) => Object.fromEntries(b.split(`
`).filter(Boolean).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)])));
  return { blocks, native };
}
var unixDate2 = (v) => v && /^@\d+$/.test(v) ? new Date(Number(v.slice(1)) * 1000) : undefined;
function install3(job, env, sys) {
  const r = render3(job, env);
  const u = posix4.join(dir3(env), unit(job));
  const timer = job.schedule.kind !== "keepAlive";
  const [main, other] = timer ? [`${unit(job)}.timer`, `${unit(job)}.service`] : [`${unit(job)}.service`, `${unit(job)}.timer`];
  const ref = `${job.namespace}/${job.name}`;
  const pending = r.files.filter((f) => {
    const cur = sys.read(f.path);
    const by = owner3(cur);
    if (by && by !== ref)
      throw new OnCueError("INVALID_SPEC", `${f.path} belongs to oncue job ${by}`);
    return cur !== f.content;
  });
  const timerOwner = timer ? undefined : owner3(sys.read(`${u}.timer`));
  if (timerOwner && timerOwner !== ref)
    throw new OnCueError("INVALID_SPEC", `${u}.timer belongs to oncue job ${timerOwner}`);
  const staleTimer = timerOwner === ref;
  const [m, o] = show(sys, [main, other], ["UnitFileState", "ActiveState"]).blocks;
  const enabled = m?.UnitFileState === "enabled";
  const active = m?.ActiveState === "active";
  const disableOther = o?.UnitFileState === "enabled" && (timer || staleTimer);
  const filesChanged = pending.length > 0 || staleTimer || disableOther;
  if (!filesChanged && enabled && active)
    return { changed: false, warnings: r.warnings };
  ensureLogDir(sys, job.log);
  if (disableOther)
    mayFail2(sys, "disable", "--now", other);
  if (staleTimer)
    sys.remove(`${u}.timer`);
  for (const f of pending)
    sys.write(f.path, f.content);
  if (filesChanged)
    systemctl(sys, true, "daemon-reload");
  if (!enabled || !active)
    systemctl(sys, true, "enable", "--now", main);
  if (filesChanged && active)
    systemctl(sys, true, "restart", main);
  return { changed: true, warnings: r.warnings };
}
function owned(ref, env, sys) {
  const u = posix4.join(dir3(env), unit(ref));
  return [`${u}.service`, `${u}.timer`].flatMap((path) => {
    const text = sys.read(path);
    return text === undefined ? [] : [{ path, mine: owner3(text) === `${ref.namespace}/${ref.name}` }];
  });
}
function uninstall3(ref, env, sys) {
  const files = owned(ref, env, sys);
  if (files.length === 0)
    return { removed: false };
  const foreign = files.find((f) => !f.mine);
  if (foreign)
    throw new OnCueError("INVALID_SPEC", `${foreign.path} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  const u = unit(ref);
  if (files.some((f) => f.path.endsWith(".timer"))) {
    mayFail2(sys, "disable", "--now", `${u}.timer`);
    mayFail2(sys, "stop", `${u}.service`);
    mayFail2(sys, "clean", "--what=state", `${u}.timer`);
  } else {
    mayFail2(sys, "disable", "--now", `${u}.service`);
  }
  for (const f of files)
    sys.remove(f.path);
  systemctl(sys, true, "daemon-reload");
  mayFail2(sys, "reset-failed", `${u}.service`);
  return { removed: true };
}
function lingerWarning(env, sys) {
  if (env.uid === undefined)
    return [];
  try {
    const out = sys.exec(["loginctl", "show-user", String(env.uid), "-p", "Linger", "--value"], { mutates: false }).out.trim();
    return out === "no" ? ["linger is off: jobs stop at logout (loginctl enable-linger)"] : [];
  } catch {
    return [];
  }
}
function status3(ref, env, sys) {
  const files = owned(ref, env, sys).filter((f) => f.mine);
  const warnings = lingerWarning(env, sys);
  if (files.length === 0)
    return { installed: false, active: false, warnings, native: "" };
  const u = unit(ref);
  const timer = files.some((f) => f.path.endsWith(".timer"));
  const props = [
    "LoadState",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainStatus",
    "ExecMainStartTimestamp",
    "ExecMainExitTimestamp"
  ];
  const { blocks, native } = show(sys, timer ? [`${u}.service`, `${u}.timer`] : [`${u}.service`], [...props, ...timer ? ["NextElapseUSecRealtime", "LastTriggerUSec"] : []], true);
  const svc = blocks[0] ?? {};
  const tmr = timer ? blocks[1] ?? {} : undefined;
  return {
    installed: true,
    active: (tmr ?? svc).ActiveState === "active",
    lastExit: svc.ExecMainExitTimestamp && svc.ExecMainStatus ? Number(svc.ExecMainStatus) : undefined,
    lastRun: unixDate2(tmr ? tmr.LastTriggerUSec : svc.ExecMainStartTimestamp),
    nextRun: unixDate2(tmr?.NextElapseUSecRealtime),
    ...svc.Result === "timeout" && { timedOut: true },
    warnings,
    native
  };
}
function run3(ref, env, sys, wait) {
  const files = owned(ref, env, sys);
  if (files.length === 0)
    throw new OnCueError("NOT_FOUND", `${ref.namespace}/${ref.name} is not installed`);
  const service = `${unit(ref)}.service`;
  const bad = files.find((f) => !f.mine)?.path ?? (files.some((f) => f.path.endsWith(".service")) ? undefined : posix4.join(dir3(env), service));
  if (bad)
    throw new OnCueError("INVALID_SPEC", `${bad} is not managed by oncue as ${ref.namespace}/${ref.name}`);
  if (!wait) {
    systemctl(sys, true, "start", "--no-block", service);
    return {};
  }
  if (!files.some((f) => f.path.endsWith(".timer")))
    throw new OnCueError("UNSUPPORTED", "run --wait does not apply to keepAlive jobs");
  const props = ["ActiveState", "Result", "ExecMainStatus", "ExecMainStartTimestampMonotonic"];
  const before = show(sys, [service], props).blocks[0] ?? {};
  let failed;
  try {
    systemctl(sys, true, "start", service);
  } catch (e) {
    if (!(e instanceof OnCueError) || e.code !== "COMMAND_FAILED")
      throw e;
    failed = e;
  }
  const svc = show(sys, [service], props).blocks[0] ?? {};
  if (svc.ExecMainStartTimestampMonotonic === before.ExecMainStartTimestampMonotonic)
    throw failed ?? new OnCueError("COMMAND_FAILED", `${service} was already running; no new run started`);
  if (svc.ActiveState !== "inactive" && svc.ActiveState !== "failed")
    throw new OnCueError("COMMAND_FAILED", `another run of ${service} started before this run's result was read`);
  if (failed && svc.Result === "success")
    throw failed;
  return { exit: Number(svc.ExecMainStatus), ...svc.Result === "timeout" && { timedOut: true } };
}
function list3(namespace, env, sys) {
  const names = sys.readdir(dir3(env)).filter((f) => f.startsWith(`${namespace}-`) && f.endsWith(".service")).flatMap((f) => {
    const m = sys.read(posix4.join(dir3(env), f))?.match(MARKER3);
    return m && m[1] === namespace && f === `${namespace}-${m[2]}.service` ? [m[2]] : [];
  });
  names.sort();
  return names;
}
var systemd = {
  id: "systemd",
  platforms: ["linux"],
  available(sys) {
    try {
      systemctl(sys, false, "show-environment");
      return true;
    } catch {
      return false;
    }
  },
  render: render3,
  install: install3,
  uninstall: uninstall3,
  status: status3,
  list: list3,
  run: run3
};

// src/backends/index.ts
var BACKENDS = [systemd, launchd, taskScheduler];

// src/select.ts
var HINTS = {
  linux: ": systemctl --user failed (no user session bus; check XDG_RUNTIME_DIR, or loginctl enable-linger)"
};
function selectBackend(env, sys, id) {
  if (id !== undefined) {
    const b = BACKENDS.find((x) => x.id === id);
    if (!b)
      throw new OnCueError("NO_BACKEND", `unknown backend ${JSON.stringify(id)}`);
    return b;
  }
  const b = BACKENDS.find((x) => x.platforms.includes(env.platform) && x.available(sys, env));
  if (!b)
    throw new OnCueError("NO_BACKEND", `no scheduler available on ${env.platform}${HINTS[env.platform] ?? ""}`);
  return b;
}

// src/index.ts
var hostEnv = () => ({
  platform: process.platform,
  home: homedir(),
  uid: process.getuid?.(),
  localAppData: process.env.LOCALAPPDATA,
  user: process.env.USERNAME && (process.env.USERDOMAIN ? `${process.env.USERDOMAIN}\\${process.env.USERNAME}` : process.env.USERNAME)
});
function setup(o) {
  const env = o.env ?? hostEnv();
  const sys = o.sys ?? realSys;
  const backend = typeof o.backend === "object" ? o.backend : selectBackend(env, sys, o.backend);
  return { env, sys, backend };
}
var ref = (r) => ({
  namespace: validateName(r?.namespace, "namespace"),
  name: validateName(r?.name)
});
function install4(spec, o = {}) {
  const job = validateJob(spec);
  const cmd = job.command[0];
  const exe = which(cmd);
  if (!exe)
    throw new OnCueError("NOT_FOUND", isAbsolute2(cmd) ? `${cmd} is not an executable file` : `${cmd} not found on PATH`);
  const { env, sys, backend } = setup(o);
  return backend.install(validateJob({ ...job, command: [exe, ...job.command.slice(1)] }, { install: true }), env, sys);
}
var placeholderEnv = (platform) => ({
  platform,
  home: "/home/user",
  uid: 501,
  localAppData: "C:\\Users\\user\\AppData\\Local",
  user: "PC\\user"
});
function render4(spec, o = {}) {
  const job = validateJob(spec);
  const host = o.env ?? hostEnv();
  const backend = typeof o.backend === "object" ? o.backend : BACKENDS.find((b) => o.backend === undefined ? b.platforms.includes(host.platform) : b.id === o.backend);
  if (!backend)
    throw new OnCueError("NO_BACKEND", o.backend === undefined ? `no scheduler for ${host.platform}` : `unknown backend ${JSON.stringify(o.backend)}`);
  const exe = job.command[0];
  const unresolved = posix5.isAbsolute(exe) || win323.isAbsolute(exe) ? [] : [`command[0] ${JSON.stringify(exe)} is shown as given; install writes its absolute path from PATH`];
  if (backend.platforms.includes(host.platform)) {
    const r = backend.render(job, host);
    return { ...r, warnings: [...r.warnings, ...unresolved] };
  }
  const r = backend.render(job, placeholderEnv(backend.platforms[0]));
  return {
    ...r,
    warnings: [
      ...r.warnings,
      ...unresolved,
      `rendered for ${backend.platforms.join("/")} on ${host.platform}: paths, uid and user are placeholders`
    ]
  };
}
function uninstall4(r, o = {}) {
  const valid = ref(r);
  const { env, sys, backend } = setup(o);
  return backend.uninstall(valid, env, sys);
}
function status4(r, o = {}) {
  const valid = ref(r);
  const { env, sys, backend } = setup(o);
  return backend.status(valid, env, sys);
}
function list4(namespace, o = {}) {
  const ns = validateName(namespace, "namespace");
  const { env, sys, backend } = setup(o);
  return backend.list(ns, env, sys);
}
function run4(r, o = {}) {
  const valid = ref(r);
  const { env, sys, backend } = setup(o);
  if (!backend.run)
    throw new OnCueError("UNSUPPORTED", `${backend.id}: run is not supported`);
  return backend.run(valid, env, sys, o.wait ?? false);
}

// src/cli.ts
var USAGE = `usage:
  oncue install <spec.json|-> [--backend id] [--capture-path bun,gh,git] [--dry-run]
  oncue uninstall <namespace> <name> [--backend id] [--dry-run]
  oncue status <namespace> [name] [--backend id] [--json]
  oncue list <namespace> [--backend id]
  oncue run <namespace> <name> [--wait] [--backend id]
  oncue render <spec.json|-> [--backend id]`;
var EXIT = {
  INVALID_SPEC: 2,
  UNSUPPORTED: 2,
  NO_BACKEND: 3,
  NOT_FOUND: 3,
  COMMAND_FAILED: 4
};
var COMMANDS = {
  install: { args: [1, 1], flags: ["backend", "capture-path", "dry-run"] },
  uninstall: { args: [2, 2], flags: ["backend", "dry-run"] },
  status: { args: [1, 2], flags: ["backend", "json"] },
  list: { args: [1, 1], flags: ["backend"] },
  run: { args: [2, 2], flags: ["backend", "wait"] },
  render: { args: [1, 1], flags: ["backend"] }
};

class UsageError extends Error {
}
function readSpec(arg, stdin) {
  let text;
  try {
    text = arg === "-" ? stdin() : decode(readFileSync2(arg));
  } catch (e) {
    throw new UsageError(`cannot read ${arg}: ${e.message}`);
  }
  try {
    return JSON.parse(text.replace(/^\uFEFF/, ""));
  } catch (e) {
    throw new OnCueError("INVALID_SPEC", `${arg}: ${e.message}`);
  }
}
function withPath(spec, tools, platform) {
  const job = validateJob(spec);
  return { ...job, env: { ...job.env, PATH: capturePath(tools.split(",").filter(Boolean), undefined, { platform }) } };
}
function main(argv, io = {}) {
  const out = io.stdout ?? ((s) => process.stdout.write(`${s}
`));
  const err = io.stderr ?? ((s) => process.stderr.write(`${s}
`));
  const stdin = io.stdin ?? (() => decode(readFileSync2(0)));
  try {
    let parsed;
    try {
      parsed = parseArgs({
        args: argv,
        allowPositionals: true,
        options: {
          backend: { type: "string" },
          "capture-path": { type: "string" },
          "dry-run": { type: "boolean" },
          json: { type: "boolean" },
          wait: { type: "boolean" }
        }
      });
    } catch (e) {
      throw new UsageError(e.message);
    }
    const { values: v, positionals } = parsed;
    const [cmd = "", ...args] = positionals;
    const spec = Object.hasOwn(COMMANDS, cmd) ? COMMANDS[cmd] : undefined;
    if (!spec)
      throw new UsageError(cmd ? `unknown command ${cmd}` : "missing command");
    if (args.length < spec.args[0] || args.length > spec.args[1])
      throw new UsageError(`wrong number of arguments for ${cmd}`);
    const bad = Object.keys(v).find((f) => !spec.flags.includes(f));
    if (bad)
      throw new UsageError(`--${bad} does not apply to ${cmd}`);
    const sys = v["dry-run"] ? dryRunSys(io.sys ?? realSys, (l) => out(`dry-run: ${l}`)) : io.sys;
    const o = { backend: v.backend, env: io.env, sys };
    const warn = (ws) => ws.forEach((w) => err(`warning: ${w}`));
    const [a = "", b] = args;
    switch (cmd) {
      case "render": {
        const r = render4(readSpec(a, stdin), o);
        for (const f of r.files)
          out(`==> ${f.path}
${decode(f.content).replace(/^\uFEFF/, "")}`);
        warn(r.warnings);
        break;
      }
      case "install": {
        let job = readSpec(a, stdin);
        if (v["capture-path"] !== undefined)
          job = withPath(job, v["capture-path"], io.env?.platform ?? process.platform);
        const r = install4(job, o);
        warn(r.warnings);
        out(r.changed ? v["dry-run"] ? "would install" : "installed" : "unchanged");
        break;
      }
      case "uninstall":
        out(uninstall4({ namespace: a, name: b ?? "" }, o).removed ? v["dry-run"] ? "would remove" : "removed" : "not installed");
        break;
      case "status": {
        const names = b === undefined ? list4(a, o) : [b];
        const all = names.map((name) => ({ name, ...status4({ namespace: a, name }, o) }));
        if (v.json)
          out(JSON.stringify(b === undefined ? all : all[0], null, 2));
        else
          for (const s of all) {
            out(`${s.name}: ${s.installed ? s.active ? "active" : "inactive" : "not installed"}${s.lastExit === undefined ? "" : `, last exit ${s.lastExit}`}${s.timedOut ? ", timed out" : ""}${s.nextRun ? `, next ${s.nextRun.toISOString()}` : ""}`);
            warn(s.warnings);
          }
        break;
      }
      case "list":
        for (const n of list4(a, o))
          out(n);
        break;
      case "run": {
        if (!v.wait) {
          run4({ namespace: a, name: b ?? "" }, o);
          out("started");
          break;
        }
        const r = run4({ namespace: a, name: b ?? "" }, { ...o, wait: true });
        out(r.timedOut ? "timed out" : `exit ${r.exit ?? "unknown"}`);
        return r.timedOut ? 124 : r.exit ?? 1;
      }
    }
    return 0;
  } catch (e) {
    if (e instanceof UsageError) {
      err(`oncue: ${e.message}
${USAGE}`);
      return 2;
    }
    if (e instanceof OnCueError) {
      err(`oncue: ${e.code}: ${e.message}`);
      return EXIT[e.code];
    }
    err(`oncue: unexpected error: ${e?.stack ?? e}`);
    return 1;
  }
}
function runCli() {
  process.stdout.on("error", (e) => {
    if (e.code !== "EPIPE")
      throw e;
  });
  process.exitCode = main(process.argv.slice(2));
}
if (false)
  ;

// src/bin.ts
runCli();
