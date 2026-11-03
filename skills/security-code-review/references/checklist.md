# Coverage Checklist

Adapt to the codebase; skip areas the stack does not have.

## Identity, Sessions, and Authorization

- Authentication is enforced server-side on every protected route and action.
- Passwords use a modern adaptive hash (Argon2id, scrypt, bcrypt); reset and MFA
  flows are single-use, expiring, rate-limited, and resist enumeration.
- Session cookies/tokens have expiry, rotation, revocation, `HttpOnly`, `Secure`,
  and `SameSite`; tokens are not in client-accessible storage without a
  justified design.
- CSRF protection covers cookie-authenticated state changes; OAuth/OIDC state,
  nonce, PKCE, redirect URIs, and token validation are correct.
- Authorization is checked per resource and field/action, not only per route or
  UI. Test IDOR, vertical escalation, tenant isolation, mass assignment, and
  confused-deputy paths.
- Sensitive actions require the right principal, role, ownership, and
  re-authentication or step-up where appropriate.

## Input, Output, and Code Execution

- Validate and normalize untrusted input at boundaries (size, type, format,
  business rules). Never rely on client-side validation.
- Parameterize SQL/NoSQL/LDAP/template queries; never concatenate attacker
  input into queries or commands.
- Encode output for its actual context. Treat `eval`, dynamic imports, shell
  execution, unsafe deserialization, raw HTML, and escape bypasses as high-risk sinks.
- Uploads and archives: size/type limits, content inspection where needed, no
  path traversal or Zip Slip, storage outside executable/public paths, safe
  filename handling and decompression limits.
- Server-side URL fetches: validate scheme and host; reject private, loopback,
  link-local, metadata, and reserved IPs after resolving all records; control
  redirects and timeouts; consider DNS rebinding/TOCTOU.
- Where relevant: XSS (reflected, stored, DOM), CSRF, open redirects,
  clickjacking, prototype pollution, XXE, path traversal, request smuggling,
  parser differentials.

## APIs, Webhooks, and Abuse Resistance

- Authentication, authorization, schema validation, response field allowlists,
  pagination, payload limits, timeouts, safe errors.
- CORS restricted to intended origins and methods; security headers and TLS fit
  the deployment model.
- Webhook signatures verified over the raw body, with timestamp/replay
  protection and idempotent handlers where duplicate delivery matters.
- Rate limits and resource budgets on login, recovery, search, uploads, and
  expensive queries, per user, tenant, and IP as appropriate.
- Business invariants around payments, balances, discounts, retries, approvals,
  and state transitions. Never trust client-provided prices, roles, ownership,
  or completion state.

## Secrets, Data, and Cryptography

- No credentials, tokens, keys, or production secrets in source, logs, fixtures,
  prompts, URLs, or history. If exposed, recommend rotation; deleting the line
  is not remediation.
- Minimize PII collection and exposure; enforce tenant boundaries, response
  allowlists, retention, and redaction. No secrets or sensitive data in errors,
  analytics, telemetry, or audit records.
- Established libraries and modern primitives with correct key handling,
  randomness, nonces, verification, constant-time comparison where relevant,
  and key rotation. No home-made protocols.
- Security-relevant events are audited without passwords, tokens, or full
  payment data, with integrity and actor/request context.

## Dependencies, Infrastructure, and Delivery

- Identify the install boundary, package manager, authoritative lockfile, CI
  install mode, and runtime reachability before interpreting advisories.
- Dependency audits are known-advisory evidence, not proof of safety. Check
  reachability, runtime vs dev use, fix availability, provenance, typosquats,
  transitive changes, and install scripts. No blind `--force` remediation.
- Least privilege, exposed services, network boundaries, container isolation,
  filesystem permissions, cloud IAM, KMS/secrets handling, CI permissions,
  artifact integrity, unsafe deployment defaults.
- Production config: debug mode, permissive CORS, missing TLS, weak headers,
  public storage, broad roles, exposed management interfaces. Mark
  environment-only claims as needing deployment verification.

## AI/LLM Features

- Prompts, retrieved documents, tool results, and model output are untrusted.
  Validate structured output before it reaches SQL, shells, HTML, file paths, or
  tool arguments.
- Enforce permissions in application code, not prompts. Scope tools and agent
  capabilities to least privilege; confirm destructive or irreversible actions.
- Prevent prompt injection, cross-tenant retrieval, sensitive-data leakage,
  unsafe tool chaining, poisoned documents, and unbounded token/cost/loop usage.
