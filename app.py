# app.py
from __future__ import annotations

import streamlit as st

from core.config import settings
from core.logger import get_logger
from retrieval.router import wants_entire_list
from retrieval.intent import extract_intent
from retrieval.structured_runner import run_structured_with_retries
from retrieval.hybrid import run_hybrid
from retrieval.intent_guard import guard_intent,enrich_intent

log = get_logger("app")

st.set_page_config(page_title="SM Denim Fabric Assistant", layout="wide")

st.title("SM Denim Fabric Assistant")
st.caption("Oracle 23ai + Structured Intent + Deterministic SQL + Hybrid (Keyword+Vector)")

with st.sidebar:
    st.subheader("Settings")
    st.write(f"LLM_PROVIDER: `{settings.llm_provider}`")
    st.write(f"HARD_MAX_ROWS: `{settings.hard_max_rows}`")
    show_debug = st.checkbox("Show debug", value=True)

st.divider()

example_qs = [
    "give the list of all the fabrics that weigh exactly 10 oz (entire list)",
    "fabrics constructed with triple warp yarn counts",
    "fabric using single weft yarn count of 8/1 OE",
    "similar to style 2544 but lighter",
    "recommend alternatives to rain slub stretch",
]
st.write("**Try examples:**")
cols = st.columns(2)
for i, qq in enumerate(example_qs):
    if cols[i % 2].button(qq, use_container_width=True):
        st.session_state["q"] = qq

q = st.text_area("Ask a question:", value=st.session_state.get("q", ""), height=90)

if st.button("Run", type="primary", use_container_width=True) and q.strip():
    user_question = q.strip()
    # allow_unlimited = wants_entire_list(user_question)


    try:
        intent = extract_intent(user_question)
        intent = guard_intent(user_question, intent)
        intent = enrich_intent(user_question, intent)

        intent = guard_intent(user_question, intent)  # re-guard after enrichment

   
        allow_unlimited = wants_entire_list(user_question) or bool(intent.get("return_all"))

        if show_debug:
            st.write("**Intent (raw):**")
            st.json(intent)
        
        # Execute
        if intent.get("type") == "structured":
            df, used_sql, used_intent = run_structured_with_retries(
                user_question, intent, allow_unlimited, retry_limit=2
            )
            mode = "STRUCTURED"
            debug_sql = None
            ranked_df = None

        elif intent.get("type") == "hybrid":
            df, used_sql, debug_sql, ranked_df = run_hybrid(user_question, allow_unlimited)
            mode = "HYBRID"
            used_intent = intent

        else:
            raise ValueError(f"Unknown intent type: {intent.get('type')}")
        
        

        # Answer (no LLM for structured lists -> avoids 413)
        row_count = int(df.shape[0])
        if mode == "STRUCTURED":
            final_answer = f"I found {row_count} matching fabrics. Results are shown below."
        else:
            final_answer = f"I found {row_count} results from hybrid search (ranked). Results are shown below."

        st.subheader("Answer")
        st.write(final_answer)

        st.subheader("Results")
        if row_count == 0:
            st.warning("No rows returned.")
        else:
            st.write(f"Returned **{row_count}** rows.")
            st.dataframe(df, use_container_width=True, height=450)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download results as CSV",
                data=csv_bytes,
                file_name="fabric_results.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if show_debug:
            st.divider()
            st.subheader("Debug")
            st.write("**Mode:**", mode)
            st.write("**SQL Used:**")
            st.code(used_sql, language="sql")

            if mode == "STRUCTURED":
                st.write("**Final Intent Used (after retries if any):**")
                st.json(used_intent)

            if mode == "HYBRID" and debug_sql:
                st.write("**Keyword SQL:**")
                st.code(debug_sql["keyword_sql"], language="sql")
                st.write("**Vector SQL:**")
                st.code(debug_sql["vector_sql"], language="sql")
                st.write("**Hybrid ranking:**")
                st.dataframe(ranked_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
