
# retrieval/vector_search.py
from __future__ import annotations

import json
from core.config import settings
from db.oracle import db

def vector_top_styles(query_vec: list[float], top_k: int):
    qvec_json = json.dumps(query_vec)

    sql = f"""
    SELECT STYLE,
           VECTOR_DISTANCE(STYLE_EMBEDDING, TO_VECTOR(:qvec)) AS DIST
    FROM {settings.oracle_table}
    ORDER BY DIST
    FETCH FIRST {int(top_k)} ROWS ONLY
    """.strip().replace("\n", " ")

    df = db.fetch_df(sql, {"qvec": qvec_json})
    return df, sql
