# retrieval/sql_builder.py
from __future__ import annotations

import re
from core.config import settings

# Canonical “slot” columns for yarn descriptions.
# IMPORTANT: keep these aligned with your Oracle schema.
WARP_COLS = ["WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3"]
WEFT_COLS = ["WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3"]

# Optional: central mapping for scalability (future groups can be added here cleanly)
GROUP_COLS = {
    "warp": WARP_COLS,
    "weft": WEFT_COLS,
}

# Semantic numeric expressions (domain mapping)
NUMERIC_EXPR = {
    # OZ values like "12.00 Oz"
    "OZ": "TO_NUMBER(REGEXP_SUBSTR(OZ, '[0-9]+(\\.[0-9]+)?'))",
    # others are usually numeric already; keep as-is unless you discover they are strings too
    "PPI_INCH": "TO_NUMBER(PPI_INCH)",
    "NO_OF_ENDS": "TO_NUMBER(NO_OF_ENDS)",
    "REED_SPACE": "TO_NUMBER(REED_SPACE)",
}

ALLOWED_SELECT = """
STYLE, FINISH_TYPE, OZ, WEAVE, QUALITY, ITEM,
WARP_ITEM_DESC1, WARP_ITEM_DESC2, WARP_ITEM_DESC3,
NO_OF_ENDS, REED_SPACE,
WEFT_ITEM_DESC1, WEFT_ITEM2, WEFT_ITEM3,
PPI_INCH, FULL_DESCRIPTION
""".strip().replace("\n", " ")


def _count_expr(cols: list[str]) -> str:
    """
    Count how many of the given columns are “present”.
    Oracle treats empty strings as NULL, so TRIM(col) IS NOT NULL is a solid presence test.
    """
    return " + ".join([f"CASE WHEN TRIM({c}) IS NOT NULL THEN 1 ELSE 0 END" for c in cols])


def _norm_expr(expr: str) -> str:
    return f"LOWER(REGEXP_REPLACE(TRIM({expr}), '\\s+', ' '))"


def norm_text_sql(expr: str) -> str:
    # kept for compatibility with existing imports/usages
    return _norm_expr(expr)


def is_yarn_token(val: str) -> bool:
    # detects yarn tokens like "8/1 OE", "10/1 RING", "7/1 OESLUB"
    v = " ".join(str(val).split())
    return bool(re.search(r"\b\d+\s*/\s*\d+\b", v))


def build_structured_sql(intent: dict, allow_unlimited: bool):
    """
    Deterministic SQL builder.
    Scalable approach:
      - each filter kind compiles independently
      - no intent mutation, no “special-case rewrites” that delete other binds/filters
    """
    where: list[str] = []
    binds: dict[str, object] = {}

    filters = intent.get("filters", []) or []

    for i, f in enumerate(filters):
        kind = f.get("kind")

        if kind == "group_count":
            group = (f.get("group") or "").lower().strip()
            if group not in GROUP_COLS:
                raise ValueError(f"Unsupported group for group_count: {group!r}")
            try:
                count = int(f.get("count"))
            except Exception:
                raise ValueError(f"Invalid count for group_count: {f.get('count')!r}")

            cols = GROUP_COLS[group]
            where.append(f"({_count_expr(cols)}) = :cnt{i}")
            binds[f"cnt{i}"] = count

        elif kind == "contains":
            col = f.get("column")
            if not col:
                raise ValueError("contains filter missing 'column'")
            raw_val = str(f.get("value", ""))
            val = " ".join(raw_val.split()).lower()

            if is_yarn_token(raw_val):
                # Exact token match (normalized), not substring
                where.append(f"REGEXP_LIKE({_norm_expr(col)}, :re{i})")
                binds[f"re{i}"] = f"^{re.escape(val)}$"
            else:
                where.append(f"{_norm_expr(col)} LIKE '%' || :val{i} || '%'")
                binds[f"val{i}"] = val

        elif kind == "equals":
            col = f.get("column")
            if not col:
                raise ValueError("equals filter missing 'column'")
            raw_val = str(f.get("value", ""))
            val = " ".join(raw_val.split()).lower()

            where.append(f"REGEXP_LIKE({_norm_expr(col)}, :re{i})")
            binds[f"re{i}"] = f"^{re.escape(val)}$"
        elif kind == "group_match":
            group = (f.get("group") or "").lower().strip()
            if group not in GROUP_COLS:
                raise ValueError(f"Unsupported group for group_match: {group!r}")

            raw_val = str(f.get("value", ""))
            val = " ".join(raw_val.split()).lower()

            cols = GROUP_COLS[group]

            # exact token match if yarn token, else LIKE
            if is_yarn_token(raw_val):
                parts = [f"REGEXP_LIKE({_norm_expr(c)}, :gre{i})" for c in cols]
                where.append("(" + " OR ".join(parts) + ")")
                binds[f"gre{i}"] = f"^{re.escape(val)}$"
            else:
                parts = [f"{_norm_expr(c)} LIKE '%' || :gval{i} || '%'" for c in cols]
                where.append("(" + " OR ".join(parts) + ")")
                binds[f"gval{i}"] = val

        elif kind == "numeric":
            col = f.get("column")
            if not col:
                raise ValueError("numeric filter missing 'column'")
            op = str(f.get("operator", "=")).strip()

            # Tighten allowed operators to keep this scalable + safe
            if op not in ("=", "!=", "<>", "<", "<=", ">", ">="):
                raise ValueError(f"Unsupported numeric operator: {op!r}")

            expr = NUMERIC_EXPR.get(col, col)  # if column known numeric-ish -> use expr
            where.append(f"{expr} {op} :num{i}")
            binds[f"num{i}"] = f.get("value")

        else:
            raise ValueError(f"Unsupported filter kind: {kind}")

    where_sql = " AND ".join(where) if where else "1=1"

    sql = f"""
    SELECT {ALLOWED_SELECT}
    FROM {settings.oracle_table}
    WHERE {where_sql}
    """.strip().replace("\n", " ")

    # If user asked entire list, don't cap; otherwise cap safely
    if not allow_unlimited:
        sql += f" FETCH FIRST {settings.hard_max_rows} ROWS ONLY"

    return sql, binds

def promote_group_contains(intent: dict) -> dict:
    out = dict(intent)
    filters = out.get("filters", []) or []

    # detect group_count requests
    weft_count = None
    warp_count = None
    for f in filters:
        if f.get("kind") == "group_count":
            g = (f.get("group") or "").lower()
            if g == "weft":
                weft_count = int(f.get("count", 0) or 0)
            elif g == "warp":
                warp_count = int(f.get("count", 0) or 0)

    new_filters = []
    for f in filters:
        if f.get("kind") in ("contains", "equals"):
            col = (f.get("column") or "").upper()
            v = str(f.get("value", ""))

            # promote weft token filters when multi-weft requested
            if weft_count and weft_count > 1 and col in ("WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3"):
                if is_yarn_token(v):
                    new_filters.append({
                        "kind": "group_match",
                        "group": "weft",
                        "match": "token",
                        "value": v,
                    })
                    continue

            # promote warp token filters when multi-warp requested (optional)
            if warp_count and warp_count > 1 and col in ("WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3"):
                if is_yarn_token(v):
                    new_filters.append({
                        "kind": "group_match",
                        "group": "warp",
                        "match": "token",
                        "value": v,
                    })
                    continue

        new_filters.append(f)

    out["filters"] = new_filters
    return out
