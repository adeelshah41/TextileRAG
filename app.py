from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import settings
from core.logger import get_logger
from db.oracle import db

from retrieval.intent import extract_intent
from retrieval.sql_builder import build_structured_sql
from retrieval.hybrid import run_hybrid
from retrieval.router import wants_entire_list

from llm.client import llm
from llm.prompts import SYSTEM_ANSWER


log = get_logger("app")

st.set_page_config(page_title="SM Denim Fabric Assistant", layout="wide")

st.title("SM Denim Fabric Assistant")
st.caption("Oracle 23ai + Structured Query Engine + Hybrid (Vector + Keyword) Ranking")

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.subheader("Settings")
    st.write(f"LLM_PROVIDER: `{settings.llm_provider}`")
    st.write(f"HARD_MAX_ROWS: `{settings.hard_max_rows}`")
    st.write(f"HYBRID_ALPHA: `{settings.hybrid_alpha}`")
    show_debug = st.checkbox("Show debug info", value=True)

st.divider()

# -----------------------------
# Example questions
# -----------------------------
example_qs = [
    "give the list of all the fabrics that weigh exactly 10 oz (entire list)",
    "fabrics constructed with triple warp yarn counts",
    "fabric using single weft yarn count of 8/1 OE",
    "similar to style 2544 but lighter",
    "what is the biggest weight available among the fabrics"
]

st.write("**Try examples:**")
cols = st.columns(2)
for i, q in enumerate(example_qs):
    if cols[i % 2].button(q, use_container_width=True):
        st.session_state["q"] = q

q = st.text_area(
    "Ask a question about SM Denim fabric specifications:",
    value=st.session_state.get("q", ""),
    height=100,
)

# -----------------------------
# MAIN EXECUTION
# -----------------------------
if st.button("Run", type="primary", use_container_width=True) and q.strip():

    user_question = q.strip()
    allow_unlimited = wants_entire_list(user_question)

    st.info(f"Large list requested: **{allow_unlimited}**")

    try:
        # ---------------------------------------------------
        # 1️⃣ INTENT EXTRACTION
        # ---------------------------------------------------
        intent = extract_intent(user_question)

        if show_debug:
            st.write("**Extracted Intent:**")
            st.json(intent)

        # ---------------------------------------------------
        # 2️⃣ EXECUTION STRATEGY
        # ---------------------------------------------------
        if intent["type"] == "structured":

            sql, binds = build_structured_sql(intent, allow_unlimited)
            df = db.fetch_df(sql, binds)
            used_sql = sql
            mode = "STRUCTURED"
            debug_sql = None
            ranked_df = None

        elif intent["type"] == "hybrid":

            df, used_sql, debug_sql, ranked_df = run_hybrid(
                user_question, allow_unlimited
            )
            mode = "HYBRID"

        else:
            raise ValueError("Unknown intent type")

        # ---------------------------------------------------
        # 3️⃣ ANSWER SYNTHESIS
        # ---------------------------------------------------
        row_count = int(df.shape[0])

        if allow_unlimited and row_count > 50:
            final_answer = (
                f"I found {row_count} matching fabrics. "
                "The full list is displayed below and can be downloaded as CSV."
            )
        else:
            preview_rows = df.head(30).to_dict(orient="records")

            answer_prompt = f"""
User question: {user_question}

Total rows returned: {row_count}

Returned rows preview (first up to 30 rows):
{preview_rows}

Instructions:
- Use 'Total rows returned' when mentioning counts.
- Do NOT infer counts from preview.
- If many rows, state that full list is shown below.
""".strip()

            final_answer = llm.generate(SYSTEM_ANSWER, answer_prompt)

        # ---------------------------------------------------
        # 4️⃣ DISPLAY RESULTS
        # ---------------------------------------------------
        st.subheader("Answer")
        st.write(final_answer)

        st.subheader("Results")

        if df.shape[0] == 0:
            st.warning("No rows returned.")
        else:
            st.write(f"Returned **{row_count}** rows.")
            st.dataframe(df, use_container_width=True, height=450)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download results as CSV",
                data=csv_bytes,
                file_name="fabric_results.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # ---------------------------------------------------
        # 5️⃣ DEBUG SECTION
        # ---------------------------------------------------
        if show_debug:
            st.divider()
            st.subheader("Debug")

            st.write("**Execution Mode:**", mode)

            st.write("**SQL Used:**")
            st.code(used_sql, language="sql")

            if mode == "HYBRID" and debug_sql:
                st.write("**Keyword SQL:**")
                st.code(debug_sql["keyword_sql"], language="sql")

                st.write("**Vector SQL:**")
                st.code(debug_sql["vector_sql"], language="sql")

                st.write("**Hybrid Ranking Table:**")
                st.dataframe(ranked_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
