from __future__ import annotations

from core.logger import get_logger
from retrieval.embedder import embedder
from retrieval.vector_search import vector_top_styles
from retrieval.sql_engine import generate_sql, run_sql_with_retries

log = get_logger("retrieval.hybrid")


def run_hybrid(user_question: str, allow_unlimited: bool):
    qvec = embedder.embed(user_question)
    shortlist_df, vector_sql = vector_top_styles(qvec)

    # Extract style whitelist
    styles = [str(x) for x in shortlist_df["STYLE"].tolist()] if "STYLE" in shortlist_df.columns else []
    if not styles:
        # fallback to pure SQL if vector step fails silently
        sql = generate_sql(user_question, allow_unlimited, style_whitelist=None)
        df, used_sql = run_sql_with_retries(user_question, sql)
        return df, used_sql, vector_sql, shortlist_df

    # Now generate SQL constrained to shortlist
    sql = generate_sql(user_question, allow_unlimited, style_whitelist=styles)
    df, used_sql = run_sql_with_retries(user_question, sql)

    return df, used_sql, vector_sql, shortlist_df
