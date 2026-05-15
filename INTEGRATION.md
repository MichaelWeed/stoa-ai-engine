# Integration Guide: Bringing Stoa Into Your Stack

Stoa (The Crucible) is designed to be the "Deterministic Engine" that sits behind your AI applications. It bridges the gap between unreliable, expensive LLM calls and reliable, zero-cost Python code.

This guide outlines how to incorporate Stoa into existing projects, using the **MichaelWeed.xyz** portfolio as a prime case study.

---

## 1. Integration Patterns

### A. Stoa as a Sidecar (HTTP API)

Best for: Next.js/React frontends, Node.js backends, or any non-Python environment.

- Run the Stoa API via Docker.
- Call the `/run` or `/plan` endpoints.
- **Benefits**: Complete isolation. The "Plan" can be generated once and stored in your database as a static script.

### B. Stoa as a Library (Python Native)

Best for: Django/FastAPI apps, data pipelines, or CLI tools.

- Import the `WorkflowRunner`.
- Run tasks programmatically within your existing event loop.
- **Benefits**: Low latency, shared memory for inputs/outputs.

### C. The "Stoa CLI" in CI/CD

Best for: Pre-calculating logic during build time.

- Run `stoa run workflow.yaml` as part of your deployment.
- Bake the results into your static site or app config.

---

## 2. Case Study: MichaelWeed.xyz (Atlas-G Protocol)

Your site already uses the **Atlas-G Protocol** to expose a machine-readable portfolio. Here is how Stoa would supercharge that for **high-compliance verification**:

### The Problem

Currently, when an AI agent interviews your portfolio, the LLM might hallucinate experience or describe a project with slight variations every time.

### The Stoa Solution: "Verified Reasoning"

Integrate Stoa into your portfolio's MCP (Model Context Protocol) server. When a verification request comes in:

1. **Request**: `Task: "Verify HIPAA compliance experience in projects folder."`
2. **The Crucible**: Stoa generates a plan:
   - Step 1: `grep` for "HIPAA" in `data/projects/*.json`.
   - Step 2: Extract "Project Name" and "Role".
   - Step 3: Count matches. If `count > 0`, return `verified=True`.
3. **Execution**: The plan runs in a secure sandbox. No LLM "chatting" occurs.
4. **Result**: Your site returns a **deterministic, evidence-backed answer** that costs $0 in tokens to repeat for the next 1,000 visitors.

---

## 3. Implementation Example (Python)

### Setting up a Runner

```python
from stoa.runner import WorkflowRunner

# Use run_inline for easy integration without YAML files
runner = WorkflowRunner()
result = runner.run_inline(
    name="verify_experience",
    task="Find all projects related to HIPAA in the projects directory.",
    inputs={"projects_dir": "./data/projects"}
)

if result.success:
    print(f"Verified projects: {result.output}")
```

---

## 4. Stoa vs. Manual Deterministic Coding

You mentioned you are already "extracting determinism." This usually means you identify a pattern (e.g., extracting a date from a string) and write a Python function for it.

**Why use Stoa instead of just writing that Python function?**

1. **Maintenance**: In a manual world, every time a new "extraction" requirement comes up, you write a new function. With Stoa, you just describe the task. Stoa writes the code and caches it.
2. **Security**: Stoa's sandbox ensures that even if the AI writes the code, it can't delete your files or access your environment variables unless explicitly allowed by a policy.
3. **Recovery**: If the data format changes and your manual code breaks, you have to fix it. Stoa can **self-heal** using its Reflexion engine to update the code automatically.
4. **Auditability**: Stoa provides a full FSM (Finite State Machine) trace of exactly what the AI planned and what the code did. Manual functions are usually "black boxes" in your logs.

---

## 5. Moving to Production

led" Plan
One of Stoa's most powerful features is that you can save the generated plan (the code) and never call the AI again for that specific task.

```python
# Save the plan for future use
with open(f"plans/{task_id}.py", "w") as f:
    f.write(result.generated_code)
```

---

## 4. Moving to Production

1. **Self-Host**: Deploy the `stoa-api` using the provided `Dockerfile` on Cloud Run or Fly.io.
2. **Policy Configuration**: Create a `policy.yaml` that strictly limits what tools Stoa can use (e.g., `allow: [read_file]`, `deny: [network]`).
3. **Idempotency**: Use a Redis-backed cache for Stoa's idempotency layer to ensure instant responses for repeated queries across your user base.

---

## 5. Why do this?

By incorporating Stoa, you transform your portfolio from a **Chatbot** into a **Verifiable Agentic Infrastructure**. It proves you don't just "talk" to AI—you engineer the systems that make AI reliable.
