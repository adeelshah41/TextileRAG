# retrieval/hybrid.py
from __future__ import annotations

from retrieval.embedder import embedder
from retrieval.combined_search import combined_top_styles
from retrieval.sql_engine import generate_sql, run_sql_with_retries

def run_hybrid(user_question: str, allow_unlimited: bool):
    qvec = embedder.embed(user_question)

    ranked_df, debug_sql = combined_top_styles(user_question, qvec)

    styles = [str(x) for x in ranked_df["STYLE"].tolist()]

    sql = generate_sql(user_question, allow_unlimited, style_whitelist=styles)
    df, used_sql = run_sql_with_retries(user_question, sql)

    # return ranked_df too for debugging if you want
    return df, used_sql, debug_sql, ranked_df
