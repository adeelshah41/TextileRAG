# app.py
from __future__ import annotations

import streamlit as st
import pandas as pd
import json
import copy

from core.config import settings
from core.logger import get_logger
from retrieval.structured_runner import run_structured_with_retries
from retrieval.hybrid import run_hybrid
from retrieval.intent_guard import enrich_intent
from retrieval.planner import planner_llm
from retrieval.executor import execute_plan

log = get_logger("app")

st.set_page_config(page_title="SM Denim Fabric Assistant", layout="wide")

st.title("SM Denim Fabric Assistant")
st.caption("Fully Autonomous Multi-Step Agent (Oracle 23ai + Hybrid + Row Analyzer)")

# --- Sidebar ---
with st.sidebar:
    st.subheader("Settings")
    st.write(f"LLM_PROVIDER: `{settings.llm_provider}`")
    st.write(f"HARD_MAX_ROWS: `{settings.hard_max_rows}`")
    show_debug = st.checkbox("Show debug", value=True)

st.divider()

# --- Example Questions ---
example_qs = [
    "give the list of all the fabrics that weigh exactly 10 oz (entire list)",
    "fabrics constructed with triple warp yarn counts",
    "fabric using single weft yarn count of 8/1 OE",
    "similar to style 2544 but lighter",
    "recommend alternatives to rain slub stretch",
    "highlight the differences between 1382 and 1552",
    "what is the number of warp yarns used in style 2869-SF and name them",
]

st.write("**Try examples:**")
cols = st.columns(2)
for i, qq in enumerate(example_qs):
    if cols[i % 2].button(qq, use_container_width=True):
        st.session_state["q"] = qq

# --- User Question Input ---
q = st.text_area("Ask a question:", value=st.session_state.get("q", ""), height=90)

# --- Agent Execution ---
if st.button("Run", type="primary", use_container_width=True) and q.strip():
    user_question = q.strip()

    try:
        # --- Planner: Generate structured plan ---
        plan = planner_llm(user_question, debug=show_debug)

        if show_debug:
            st.subheader("Planner Output (JSON Plan)")
            st.json(plan)

        # --- Executor: Execute the plan step by step ---
        final_answer, intermediate_results = execute_plan(plan, user_question, debug=show_debug)

        # --- Display final answer ---
        st.subheader("Answer")
        st.write(final_answer)

        # --- Display intermediate results (if any) ---
        if show_debug and intermediate_results:
            st.subheader("Intermediate Results")
            for step in intermediate_results:
                st.write(f"Step {step['step']} - Tool: {step['tool']}")
                if "df" in step:
                    st.dataframe(step["df"], use_container_width=True)
                if "sql" in step:
                    st.code(step["sql"], language="sql")
                if "summary" in step:
                    st.write(step["summary"])

    except Exception as e:
        st.error(f"Error: {e}")


