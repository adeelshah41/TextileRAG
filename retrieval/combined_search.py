# retrieval/combined_search.py
from __future__ import annotations

import pandas as pd
from typing import Dict, Tuple

from core.config import settings
from retrieval.keyword_search import keyword_top_styles
from retrieval.vector_search import vector_top_styles

def _rrf_scores(df: pd.DataFrame, key_col: str, rank_col_name: str, k: int = 60) -> pd.DataFrame:
    """
    Reciprocal Rank Fusion score per item based on its rank in df (1..n).
    score = 1 / (k + rank)
    """
    if df.empty:
        return pd.DataFrame(columns=[key_col, rank_col_name])

    tmp = df[[key_col]].copy()
    tmp["__rank"] = range(1, len(tmp) + 1)
    tmp[rank_col_name] = 1.0 / (k + tmp["__rank"].astype(float))
    return tmp.drop(columns=["__rank"])

def combined_top_styles(query: str, query_vec: list[float], where_sql: str = "1=1", where_binds: Dict[str, object] | None = None):
    """
    Returns:
      ranked_df: columns STYLE, COMBINED_SCORE, KW_RRF, VEC_RRF
      debug_sql: dict with 'keyword_sql' and 'vector_sql'
    """
    # 1) keyword candidates
    kw_df, kw_sql = keyword_top_styles(query, settings.hybrid_k_keyword)

    # 2) vector candidates (apply metadata prefilter if provided)
    v_df, v_sql = vector_top_styles(query_vec, settings.hybrid_k_vector, where_sql=where_sql, binds=where_binds)

    # Ensure expected columns exist
    if "STYLE" not in kw_df.columns:
        kw_df["STYLE"] = []
    if "STYLE" not in v_df.columns:
        v_df["STYLE"] = []

    kw_rrf = _rrf_scores(kw_df, "STYLE", "KW_RRF", k=60)
    v_rrf = _rrf_scores(v_df, "STYLE", "VEC_RRF", k=60)

    cand = pd.merge(kw_rrf, v_rrf, on="STYLE", how="outer").fillna({"KW_RRF": 0.0, "VEC_RRF": 0.0})
    cand["COMBINED_SCORE"] = cand["KW_RRF"] + cand["VEC_RRF"]

    ranked = cand.sort_values("COMBINED_SCORE", ascending=False).head(settings.hybrid_k_final)

    return ranked, {"keyword_sql": kw_sql, "vector_sql": v_sql}
