#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

const CACHE_SCHEMA = "global-cli-v1";
const CACHE_DIR =
  process.env.FIRECRAWL_AGENT_CACHE_DIR ||
  join(tmpdir(), "firecrawl-agent-cache");
const DEFAULT_TTL_MS = 24 * 60 * 60 * 1000;
const CACHE_TTL_MS = parsePositiveInteger(
  process.env.FIRECRAWL_AGENT_CACHE_TTL_MS,
  DEFAULT_TTL_MS,
);
const REFRESH = process.env.FIRECRAWL_AGENT_REFRESH === "1";

const [command, ...args] = process.argv.slice(2);

switch (command) {
  case "search":
    search(args);
    break;
  case "map":
    mapSite(args);
    break;
  case "read":
    scrapeToFile(args, "markdown", "page", "md");
    break;
  case "summary":
    scrapeToFile(args, "summary", "summary", "txt");
    break;
  case "status":
    requireArity(args, 0, "status");
    runFirecrawl(["--status"]);
    break;
  case "clear":
    requireArity(args, 0, "clear");
    clearCache();
    break;
  default:
    usage(command ? `Unknown command: ${command}` : undefined);
}

function search(parts) {
  if (parts.length === 0) usage("Usage: search <query>");
  const query = parts.join(" ").trim();
  if (!query) usage("Usage: search <query>");

  const output = cachePath("search", query, "json");
  ensureCached(output, [
    "search",
    query,
    "--limit",
    "5",
    "--sources",
    "web",
    "--json",
    "--output",
    output,
  ]);

  const payload = readJson(output);
  const results = projectResults(payload?.data?.web || payload?.web, 5);
  process.stdout.write(`${JSON.stringify({ results }, null, 2)}\n`);
}

function mapSite(parts) {
  if (parts.length < 2) usage("Usage: map <base-url> <query>");
  const [baseUrl, ...queryParts] = parts;
  validateUrl(baseUrl);
  const query = queryParts.join(" ").trim();
  if (!query) usage("Usage: map <base-url> <query>");

  const output = cachePath("map", `${baseUrl}\n${query}`, "json");
  ensureCached(output, [
    "map",
    baseUrl,
    "--search",
    query,
    "--limit",
    "20",
    "--ignore-query-parameters",
    "--json",
    "--output",
    output,
  ]);

  const payload = readJson(output);
  const results = projectResults(payload?.data?.links || payload?.links, 20);
  process.stdout.write(`${JSON.stringify({ results }, null, 2)}\n`);
}

function scrapeToFile(parts, format, prefix, extension) {
  requireArity(parts, 1, `${prefix} <url>`);
  const [url] = parts;
  validateUrl(url);

  const output = cachePath(prefix, url, extension);
  ensureCached(output, [
    "scrape",
    url,
    "--format",
    format,
    "--only-main-content",
    "--exclude-tags",
    "nav,footer,aside",
    "--max-age",
    "172800000",
    "--output",
    output,
  ]);
  process.stdout.write(`${output}\n`);
}

function ensureCached(output, cliArgs) {
  mkdirSync(dirname(output), { recursive: true });
  if (isFresh(output)) return;
  const temporary = temporaryPath(output);
  const temporaryArgs = cliArgs.map((arg) =>
    arg === output ? temporary : arg,
  );
  runFirecrawl(temporaryArgs, true);
  if (!existsSync(temporary) || statSync(temporary).size === 0) {
    rmSync(temporary, { force: true });
    fail(`Firecrawl did not create ${output}`);
  }

  try {
    rmSync(output, { force: true });
    renameSync(temporary, output);
  } catch (error) {
    if (existsSync(output) && statSync(output).size > 0) {
      rmSync(temporary, { force: true });
      return;
    }
    rmSync(temporary, { force: true });
    fail(`Could not cache Firecrawl output: ${error.message}`);
  }
}

function runFirecrawl(args, captureOutput = false) {
  const invocation = firecrawlInvocation(args);
  const result = spawnSync(invocation.command, invocation.args, {
    encoding: "utf8",
    stdio: captureOutput ? ["ignore", "pipe", "pipe"] : "inherit",
    windowsHide: true,
  });

  if (result.error) fail(missingCliMessage(result.error.message));
  if (result.status !== 0) {
    const detail = captureOutput
      ? (result.stderr || result.stdout || "").trim()
      : "";
    fail(detail || `Firecrawl exited with status ${result.status}`);
  }
}

function firecrawlInvocation(args) {
  if (process.platform !== "win32") {
    return { command: "firecrawl", args };
  }

  const pathResult = spawnSync("firecrawl", ["--version"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  if (!pathResult.error || pathResult.error.code !== "ENOENT") {
    return { command: "firecrawl", args };
  }

  const npmCli = join(
    dirname(process.execPath),
    "node_modules",
    "npm",
    "bin",
    "npm-cli.js",
  );
  if (!existsSync(npmCli)) {
    fail(missingCliMessage(`Cannot locate npm-cli.js beside ${process.execPath}`));
  }

  const rootResult = spawnSync(process.execPath, [npmCli, "root", "--global"], {
    encoding: "utf8",
    windowsHide: true,
  });
  const globalRoot = rootResult.stdout?.trim();
  const firecrawlCli = globalRoot
    ? join(globalRoot, "firecrawl-cli", "dist", "index.js")
    : "";
  if (rootResult.status !== 0 || !firecrawlCli || !existsSync(firecrawlCli)) {
    fail(missingCliMessage(rootResult.stderr?.trim()));
  }
  return { command: process.execPath, args: [firecrawlCli, ...args] };
}

function cachePath(prefix, value, extension) {
  const digest = createHash("sha256")
    .update(`${CACHE_SCHEMA}\0${prefix}\0${value}`)
    .digest("hex")
    .slice(0, 24);
  return join(CACHE_DIR, `${prefix}-${digest}.${extension}`);
}

function temporaryPath(output) {
  const extensionIndex = output.lastIndexOf(".");
  const stem = output.slice(0, extensionIndex);
  const extension = output.slice(extensionIndex);
  const nonce = createHash("sha256")
    .update(`${process.pid}\0${Date.now()}\0${Math.random()}`)
    .digest("hex")
    .slice(0, 12);
  return `${stem}.tmp-${process.pid}-${nonce}${extension}`;
}

function isFresh(path) {
  if (REFRESH || !existsSync(path)) return false;
  const stat = statSync(path);
  return stat.size > 0 && Date.now() - stat.mtimeMs <= CACHE_TTL_MS;
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`Invalid cached Firecrawl JSON at ${path}: ${error.message}`);
  }
}

function projectResults(value, limit) {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry) => entry && typeof entry === "object")
    .slice(0, limit)
    .map(({ title, url, description }) => ({ title, url, description }));
}

function clearCache() {
  if (!existsSync(CACHE_DIR)) {
    process.stdout.write(`Cache already empty: ${CACHE_DIR}\n`);
    return;
  }

  const cacheFile = /^(search|map|page|summary)-[a-f0-9]{24}(?:\.tmp-\d+-[a-f0-9]{12})?\.(json|md|txt)$/u;
  let removed = 0;
  for (const entry of readdirSync(CACHE_DIR, { withFileTypes: true })) {
    if (entry.isFile() && cacheFile.test(entry.name)) {
      rmSync(join(CACHE_DIR, entry.name), { force: true });
      removed += 1;
    }
  }
  process.stdout.write(`Cleared ${removed} Firecrawl cache file(s) from ${CACHE_DIR}\n`);
}

function validateUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    usage(`Invalid URL: ${value}`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    usage(`Only http and https URLs are supported: ${value}`);
  }
  if (url.username || url.password) {
    usage("Credentials are not allowed in URLs");
  }
}

function requireArity(parts, count, syntax) {
  if (parts.length !== count) usage(`Usage: ${syntax}`);
}

function parsePositiveInteger(value, fallback) {
  if (value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    fail("FIRECRAWL_AGENT_CACHE_TTL_MS must be a positive integer");
  }
  return parsed;
}

function usage(error) {
  if (error) process.stderr.write(`${error}\n\n`);
  process.stderr.write(
    "Usage: firecrawl-agent <search|map|summary|read|status|clear> [arguments]\n",
  );
  process.exit(2);
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function missingCliMessage(detail) {
  const suffix = detail ? ` (${detail})` : "";
  return `Global Firecrawl CLI not found. Run: npm install -g firecrawl-cli@1.19.26${suffix}`;
}
