# retrieval/vector_search.py
from __future__ import annotations

import json
from typing import Dict, Optional, Tuple

from core.config import settings
from db.oracle import db

def get_style_embedding(style: str) -> Optional[list[float]]:
    """
    Fetch the stored embedding for a given style.
    Returns None if not found or embedding is null.
    """
    sql = f"""
    SELECT STYLE_EMBEDDING
    FROM {settings.oracle_table}
    WHERE STYLE = :s
    """.strip().replace("\n", " ")
    df = db.fetch_df(sql, {"s": style})
    if df.shape[0] == 0:
        return None
    v = df.iloc[0, 0]
    if v is None:
        return None
    # Oracle driver typically returns VECTOR as JSON-ish string or array depending on setup.
    # We accept either: list already or JSON string.
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except Exception:
        return None

def vector_top_styles(query_vec: list[float], top_k: int, where_sql: str = "1=1", binds: Optional[Dict[str, object]] = None):
    qvec_json = json.dumps(query_vec)
    binds = dict(binds or {})
    binds["qvec"] = qvec_json

    sql = f"""
    SELECT STYLE,
           VECTOR_DISTANCE(STYLE_EMBEDDING, TO_VECTOR(:qvec)) AS DIST
    FROM {settings.oracle_table}
    WHERE {where_sql}
    ORDER BY DIST
    FETCH FIRST {int(top_k)} ROWS ONLY
    """.strip().replace("\n", " ")

    df = db.fetch_df(sql, binds)
    return df, sql
