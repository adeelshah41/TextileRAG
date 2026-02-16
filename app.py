from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from core.config import settings
from core.logger import get_logger
from retrieval.router import route_mode, wants_entire_list
from retrieval.sql_engine import generate_sql, run_sql_with_retries
from retrieval.hybrid import run_hybrid
from llm.client import llm
from llm.prompts import SYSTEM_ANSWER
from retrieval.fulltext import run_fulltext


log = get_logger("app")

st.set_page_config(page_title="SM Denim Fabric Assistant", layout="wide")

st.title("SM Denim Fabric Assistant")
st.caption("Oracle 23ai (VECTOR) + Hybrid Vector Retrieval + Text-to-SQL + Validation loop")

with st.sidebar:
    st.subheader("Settings")
    st.write(f"LLM_PROVIDER: `{settings.llm_provider}`")
    st.write(f"DEFAULT_MAX_ROWS: `{settings.default_max_rows}`")
    st.write(f"VECTOR_TOP_K: `{settings.vector_top_k}`")
    show_debug = st.checkbox("Show debug (SQL, vector shortlist)", value=True)

st.divider()

example_qs = [
    "give the list of all the fabrics that weigh exactly 10 oz (entire list)",
    "give me the list of all the fabrics having 7/1   RINGSLUB as warp item description.",
    "what is the biggest weight available among the fabrics."
]
st.write("**Try examples:**")
cols = st.columns(2)
for i, q in enumerate(example_qs):
    if cols[i % 2].button(q, use_container_width=True):
        st.session_state["q"] = q

q = st.text_area("Ask a question about SM Denim fabric specifications:", value=st.session_state.get("q", ""), height=90)

if st.button("Run", type="primary", use_container_width=True) and q.strip():

    user_question = q.strip()
    allow_unlimited = wants_entire_list(user_question)

    mode = route_mode(user_question)

    st.info(f"Mode: **{mode}**  | large number of rows requested: **{allow_unlimited}**")

    try:
        vector_sql = None
        shortlist_df = None

        if mode == "SQL":
            sql = generate_sql(user_question, allow_unlimited)
            df, used_sql = run_sql_with_retries(user_question, sql)

        elif mode == "HYBRID":
            df, used_sql, debug_sql, ranked_df = run_hybrid(
                user_question, allow_unlimited
            )
            st.code(debug_sql["keyword_sql"], language="sql")
            st.code(debug_sql["vector_sql"], language="sql")
            st.dataframe(ranked_df)


        elif mode == "FULLTEXT":
            df, used_sql = run_fulltext(user_question, allow_unlimited)


        else:
            raise ValueError("Unknown routing mode")

        # ----------------------------
        # Answer synthesis layer
        # ----------------------------
        preview_rows = df.head(30).to_dict(orient="records")

        answer_prompt = f"""
User question: {user_question}

Returned rows preview (first up to 30 rows):
{preview_rows}
        """.strip()

        final_answer = llm.generate(SYSTEM_ANSWER, answer_prompt)

        st.subheader("Answer")
        st.write(final_answer)

        st.subheader("Results")

        if df.shape[0] == 0:
            st.warning("No rows returned.")
        else:
            st.write(f"Returned **{df.shape[0]}** rows.")
            st.dataframe(df, use_container_width=True, height=420)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download results as CSV",
                data=csv_bytes,
                file_name="fabric_results.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # ----------------------------
        # Debug section
        # ----------------------------
        if show_debug:
            st.divider()
            st.subheader("Debug")
            st.write("**SQL Used:**")
            st.code(used_sql, language="sql")

            if vector_sql:
                st.write("**Vector SQL Used:**")
                st.code(vector_sql, language="sql")

            if shortlist_df is not None:
                st.write("**Vector shortlist:**")
                st.dataframe(shortlist_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
