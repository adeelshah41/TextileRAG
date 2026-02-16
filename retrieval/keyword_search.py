# retrieval/keyword_search.py
from __future__ import annotations

import re
from core.config import settings
from db.oracle import db

_STOPWORDS = {
    "fabric","fabrics","denim","show","give","list","find","me","the","a","an","of","to","for","with","and","or",
    "similar","closest","like","recommend","suggest","alternatives","alternative","near","neighbors","nearest"
}

def _tokenize(text: str) -> list[str]:
    t = (text or "").lower()
    # keep hyphenated codes as tokens; remove punctuation that breaks Oracle Text
    t = re.sub(r"[\(\)\[\]\{\}:\"\'\,\.\!\?\/\\]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return [x for x in t.split(" ") if x and x not in _STOPWORDS]

def _build_contains_query(user_text: str) -> str:
    """
    Build a conservative Oracle Text CONTAINS query:
    - bag-of-words with AND
    - supports simple negation: "not X" / "without X" -> NOT token
    This avoids DRG-50901 parser errors.
    """
    raw = (user_text or "").strip()

    # detect explicit negations of single tokens (simple + safe)
    neg = set()
    for m in re.finditer(r"\b(?:not|without|exclude|excluding)\s+([a-z0-9\-]+)\b", raw, flags=re.IGNORECASE):
        neg.add(m.group(1).lower())

    toks = _tokenize(raw)
    pos = [t for t in toks if t not in neg]

    # If nothing usable, return a query that matches nothing (avoid full table)
    if not pos and not neg:
        return "NULL"

    parts = []
    for t in pos:
        # quote tokens with hyphens to be safer
        if "-" in t:
            parts.append(f'"{t}"')
        else:
            parts.append(t)

    q = " AND ".join(parts) if parts else ""

    for t in sorted(neg):
        if "-" in t:
            q += ((" AND " if q else "") + f'NOT "{t}"')
        else:
            q += ((" AND " if q else "") + f"NOT {t}")

    return q if q else "NULL"

def keyword_top_styles(query: str, top_k: int):
    """
    Keyword search on FULL_DESCRIPTION using Oracle Text.
    Uses sanitized CONTAINS query to prevent parser errors.
    Returns DataFrame with columns: STYLE, KW_SCORE
    """
    contains_q = _build_contains_query(query)

    sql = f"""
    SELECT STYLE, SCORE(1) AS KW_SCORE
    FROM {settings.oracle_table}
    WHERE CONTAINS(FULL_DESCRIPTION, :q, 1) > 0
    ORDER BY KW_SCORE DESC
    FETCH FIRST {int(top_k)} ROWS ONLY
    """.strip().replace("\n", " ")

    df = db.fetch_df(sql, {"q": contains_q})
    return df, sql
