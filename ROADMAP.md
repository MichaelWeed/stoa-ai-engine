# Stoa Roadmap

The open-source version solves five specific problems for local and small-team
deployments. This document describes what a production deployment would additionally
require, and why each item is out of scope for an open-source MVP.

---

## What's in the open-source release (v0.1)

- [x] Compiled AI: plan once, execute N times with zero AI inference cost
- [x] FSM orchestration with hard step/token/time circuit breakers
- [x] AST safety validator for AI-generated code
- [x] Docker sandbox with network isolation and memory limits
- [x] Pre-action RBAC policy gateway (deny-all default)
- [x] Reflexion auto-repair + learnings.md ledger
- [x] LiteLLM provider abstraction (OpenAI / Anthropic / Google / Ollama)
- [x] Idempotency cache (skip re-running completed tasks)
- [x] Local Streamlit dashboard
- [x] Benchmark harness with reproducible cost/latency/determinism measurements

---

## Enterprise path (not in this repo)

### 1. Multi-tenant identity and access management
**What's missing:** The open-source version loads API keys from `.env`. A
multi-tenant deployment needs OAuth2 / OIDC for user authentication, JWT tokens
for per-request authorization, and per-tenant API key isolation so one tenant's
credentials are never visible to another.

**Estimated effort:** 2–3 weeks. Recommend FastAPI + Auth0 or Keycloak.

### 2. Kernel-level sandbox isolation
**What's missing:** Docker provides process isolation but shares the host kernel.
For regulated industries (healthcare, finance, government), kernel-level isolation
is required. This means replacing Docker-in-Docker with Firecracker microVMs or
gVisor, which intercept and audit every system call.

**Estimated effort:** 1–2 weeks. Requires a Linux host; not available on macOS
without a VM layer.

**Reference:** AWS Firecracker, Google gVisor, Kata Containers.

### 3. SOC2-compliant audit logs
**What's missing:** Enterprise compliance (SOC2, HIPAA, FedRAMP) requires
tamper-evident logs of every agent action, including who triggered it, what it
did, and what data it accessed. The open-source version logs to stdout and a
local SQLite database — sufficient for local debugging, not for a compliance audit.

**Estimated effort:** 1 week. Recommend structured JSON logs → Datadog / Splunk,
or OpenTelemetry for vendor-neutral tracing.

### 4. Kubernetes operator for multi-worker deployments
**What's missing:** The open-source version runs as a single process. For
high-concurrency deployments (hundreds of simultaneous workflows), you need a
Kubernetes operator that scales worker pods, handles pod failure gracefully,
and provides distributed rate limiting across workers.

**Estimated effort:** 3–4 weeks.

### 5. Tool extension framework
**What's missing:** The current tool registry includes `http_get` and `read_file`.
A production deployment needs a plugin system where teams can register arbitrary
tools (database queries, internal APIs, file upload services) with their own
schema validation and authorization rules.

**Estimated effort:** 1–2 weeks.

---

## If you need help with the enterprise path

The open-source repo is intentionally scoped to local deployments. If your team
needs help deploying Stoa into a production environment — or if you want to
extend it for a specific regulated industry — open an issue or reach out directly
via the contact information in the GitHub profile.
