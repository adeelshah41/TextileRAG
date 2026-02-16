# retrieval/hybrid.py
from __future__ import annotations

from typing import Dict, Optional, Tuple

from retrieval.embedder import embedder
from retrieval.combined_search import combined_top_styles
from retrieval.hybrid_fetch import fetch_by_styles
from retrieval.vector_search import get_style_embedding

def run_hybrid(user_question: str, allow_unlimited: bool, intent: Optional[dict] = None):
    """
    RAG-first hybrid:
    - If intent.reference_style is provided and exists -> style-to-style retrieval (true neighbors)
    - Otherwise embed the user question
    - Hybrid rank = RRF(keyword) + RRF(vector)
    - Fetch preserves rank order
    """
    intent = intent or {}
    ref_style = intent.get("reference_style")
    k = intent.get("k")  # optional; you can wire it into settings if desired

    # Query vector selection
    qvec = None
    if ref_style:
        qvec = get_style_embedding(str(ref_style))
    if not qvec:
        qvec = embedder.embed(user_question)

    # Optional: metadata prefilter can be added later by compiling intent["filters"] into where_sql/binds
    ranked_df, debug_sql = combined_top_styles(user_question, qvec)

    styles = [str(x) for x in ranked_df["STYLE"].tolist()]
    df, used_sql = fetch_by_styles(styles, allow_unlimited)

    return df, used_sql, debug_sql, ranked_df
