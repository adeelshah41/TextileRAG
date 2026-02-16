# retrieval/keyword_search.py
from __future__ import annotations

from core.config import settings
from db.oracle import db

def keyword_top_styles(query: str, top_k: int):
    """
    Keyword search only on FULL_DESCRIPTION using Oracle Text.
    Returns DataFrame with columns: STYLE, KW_SCORE
    """
    sql = f"""
    SELECT STYLE, SCORE(1) AS KW_SCORE
    FROM {settings.oracle_table}
    WHERE CONTAINS(FULL_DESCRIPTION, :q, 1) > 0
    ORDER BY KW_SCORE DESC
    FETCH FIRST {int(top_k)} ROWS ONLY
    """.strip().replace("\n", " ")

    df = db.fetch_df(sql, {"q": query})
    return df, sql
