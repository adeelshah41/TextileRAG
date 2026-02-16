# retrieval/hybrid.py
from __future__ import annotations

from retrieval.embedder import embedder
from retrieval.combined_search import combined_top_styles
from retrieval.hybrid_fetch import fetch_by_styles  # <-- NEW (you create this file)

def run_hybrid(user_question: str, allow_unlimited: bool):
    """
    Proper hybrid:
    1) Combined keyword + vector ranking (FULL_DESCRIPTION + embeddings)
    2) Fetch rows for the ranked STYLE candidates directly (NO LLM SQL generation)
       -> avoids hallucinated WHERE clauses like "warp_desc LIKE '%triple%'"
    """
    # 1) Embed query
    qvec = embedder.embed(user_question)

    # 2) Combined ranking (returns STYLE + scores)
    ranked_df, debug_sql = combined_top_styles(user_question, qvec)

    # 3) Candidate styles
    styles = [str(x) for x in ranked_df["STYLE"].tolist()]

    # 4) Fetch actual rows for these styles
    df, used_sql = fetch_by_styles(styles, allow_unlimited)

    return df, used_sql, debug_sql, ranked_df
