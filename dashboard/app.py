"""Stoa local dashboard — visualize token spend, FSM traces, and learnings."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Stoa Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Stoa Dashboard")
st.caption("Local visibility into your AI agent costs, execution traces, and auto-fixes.")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_savings, tab_bench, tab_learnings, tab_policy = st.tabs([
    "💰 Savings Calculator",
    "📊 Benchmark Results",
    "📖 Learnings Ledger",
    "🔒 Active Policy",
])


# ── Savings Calculator ─────────────────────────────────────────────────────────
with tab_savings:
    st.header("How much would Stoa save you?")
    st.write(
        "Enter your current monthly OpenAI (or other provider) spend. "
        "Stoa's savings come from calling the AI once to plan, then running "
        "the plan as ordinary code — paying zero API costs on repeat runs."
    )

    col1, col2 = st.columns(2)
    with col1:
        monthly = st.number_input("Monthly API spend ($)", min_value=1.0, value=500.0, step=50.0)
        wf_type = st.selectbox(
            "Workflow type",
            ["repeated", "mixed", "one-shot"],
            help="'Repeated' = same task run many times. 'One-shot' = unique tasks each time.",
        )

    with col2:
        savings_pct = {"repeated": 98, "mixed": 75, "one-shot": 15}.get(wf_type, 98)
        cost_with = monthly * (1 - savings_pct / 100)
        savings = monthly - cost_with

        st.metric("Current monthly cost", f"${monthly:,.2f}")
        st.metric("Estimated with Stoa", f"${cost_with:,.2f}", delta=f"-${savings:,.2f}")
        st.metric("Projected monthly savings", f"${savings:,.2f}")

    if wf_type == "one-shot":
        st.info(
            "One-shot workflows (different task every run) see smaller savings because "
            "the AI must be called for each unique task. The biggest wins come from "
            "repeated, high-volume workflows like nightly reports or data pipelines."
        )
    else:
        st.success(
            f"At ${monthly:,.0f}/month on {wf_type} workflows, Stoa would save you "
            f"approximately **${savings:,.0f}/month** — with break-even after ~20 runs."
        )


# ── Benchmark Results ──────────────────────────────────────────────────────────
with tab_bench:
    st.header("Benchmark Results")

    summary_path = Path("benchmarks/results/summary.json")
    if summary_path.exists():
        summaries = json.loads(summary_path.read_text())

        for s in summaries:
            with st.expander(s["workflow"].replace("_", " ").title(), expanded=True):
                raw = s.get("raw", {})
                stoa = s.get("stoa", {})
                savings = s.get("savings", {})

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Token reduction", f"{savings.get('token_reduction_pct', 0):.0f}%")
                c2.metric("Cost reduction", f"{savings.get('cost_reduction_pct', 0):.0f}%")
                c3.metric(
                    "Speed improvement",
                    f"{savings.get('latency_speedup_x', 0):.0f}×",
                )
                c4.metric(
                    "Failure rate reduction",
                    f"{savings.get('failure_rate_reduction_pct', 0):.1f}pp",
                )

        for chart in ["cost_comparison", "break_even", "latency_distribution", "determinism"]:
            img = Path(f"benchmarks/results/{chart}.png")
            if img.exists():
                st.image(str(img), use_container_width=True)
    else:
        st.info("No benchmark results yet. Run `make bench` or `stoa bench` to generate them.")
        st.code("make bench", language="bash")


# ── Learnings Ledger ───────────────────────────────────────────────────────────
with tab_learnings:
    st.header("Auto-fix Learnings Ledger")
    st.write(
        "When Stoa auto-repairs a broken step, it records the fix here. "
        "Every future run starts by reading this ledger — so the same fix "
        "is applied automatically, without manual intervention."
    )

    ledger_path = Path("learnings.md")
    if ledger_path.exists():
        text = ledger_path.read_text()
        entries = [e for e in text.split("## [") if e.strip() and not e.startswith("#")]
        if entries:
            st.success(f"{len(entries)} fixes recorded")
            for entry in entries[-10:]:  # show last 10
                lines = entry.strip().split("\n")
                header = lines[0] if lines else ""
                body = "\n".join(lines[1:]) if len(lines) > 1 else ""
                with st.expander(header):
                    st.markdown(body)
        else:
            st.info("No fixes recorded yet. Fixes appear here after Stoa auto-recovers a failed step.")
    else:
        st.info("learnings.md not found. It will be created automatically on the first run.")


# ── Active Policy ──────────────────────────────────────────────────────────────
with tab_policy:
    st.header("Active Tool Policy")
    st.write(
        "Every tool call an agent wants to make is checked against this policy "
        "before it executes. Tools not on the allow list are blocked — "
        "regardless of what the AI asks for."
    )

    policy_path = Path("policies/default.yaml")
    if policy_path.exists():
        import yaml
        policy = yaml.safe_load(policy_path.read_text())
        st.write(f"**Default:** `{policy.get('default', 'deny')}`")
        rules = policy.get("rules", [])
        if rules:
            for rule in rules:
                icon = "✅" if rule.get("allow") else "🚫"
                st.write(f"{icon} **{rule['tool']}** — {rule.get('description', '')}")
    else:
        st.info("No policy file found at policies/default.yaml. Run `stoa init` to create one.")
