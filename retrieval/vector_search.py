from __future__ import annotations

import json
from core.config import settings
from core.logger import get_logger
from db.oracle import db

log = get_logger("retrieval.vector_search")


def vector_top_styles(query_vec: list[float], top_k: int | None = None):
    """
    Returns top styles by vector similarity.
    Uses TO_VECTOR(:qvec_json). If your Oracle build uses a different function,
    change TO_VECTOR(...) accordingly.
    """
    k = top_k or settings.vector_top_k
    qvec_json = json.dumps(query_vec)

    sql = f"""
    SELECT STYLE, FULL_DESCRIPTION
    FROM {settings.oracle_table}
    ORDER BY VECTOR_DISTANCE(STYLE_EMBEDDING, TO_VECTOR(:qvec))
    FETCH FIRST {int(k)} ROWS ONLY
    """.strip().replace("\n", " ")

    rows = db.fetch_df(sql, {"qvec": qvec_json})
    return rows, sql

