# retrieval/combined_search.py
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import settings
from retrieval.keyword_search import keyword_top_styles
from retrieval.vector_search import vector_top_styles

def _minmax(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    mn, mx = float(series.min()), float(series.max())
    if mx - mn < 1e-9:
        return pd.Series([1.0] * len(series), index=series.index)
    return (series - mn) / (mx - mn)

def combined_top_styles(query: str, query_vec: list[float]):
    """
    Returns:
      ranked_df: columns STYLE, COMBINED_SCORE, KW_SCORE_N, DENSE_SCORE_N
      debug_sql: dict with 'keyword_sql' and 'vector_sql'
    """
    # 1) get sparse results (keyword)
    kw_df, kw_sql = keyword_top_styles(query, settings.hybrid_k_keyword)
    if "KW_SCORE" not in kw_df.columns:
        kw_df["KW_SCORE"] = 0.0

    # 2) get dense results (vector)
    v_df, v_sql = vector_top_styles(query_vec, settings.hybrid_k_vector)
    if "DIST" not in v_df.columns:
        v_df["DIST"] = np.nan

    # Convert distance -> similarity score (higher is better)
    # simple stable transform:
    # dense_score = 1 / (1 + dist)
    v_df["DENSE_SCORE"] = 1.0 / (1.0 + v_df["DIST"].astype(float))

    # 3) union candidates
    cand = pd.merge(
        kw_df[["STYLE", "KW_SCORE"]],
        v_df[["STYLE", "DENSE_SCORE"]],
        on="STYLE",
        how="outer",
    ).fillna({"KW_SCORE": 0.0, "DENSE_SCORE": 0.0})

    # 4) normalize each score to 0..1 so alpha blending makes sense
    cand["KW_SCORE_N"] = _minmax(cand["KW_SCORE"].astype(float))
    cand["DENSE_SCORE_N"] = _minmax(cand["DENSE_SCORE"].astype(float))

    # 5) blend
    a = float(settings.hybrid_alpha)
    cand["COMBINED_SCORE"] = (1 - a) * cand["KW_SCORE_N"] + a * cand["DENSE_SCORE_N"]

    # 6) rank
    ranked = cand.sort_values("COMBINED_SCORE", ascending=False).head(settings.hybrid_k_final)

    return ranked, {"keyword_sql": kw_sql, "vector_sql": v_sql}
