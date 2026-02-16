# retrieval/sql_builder.py
from __future__ import annotations
import re
from core.config import settings

WARP_COLS = ["WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3"]
WEFT_COLS = ["WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3"]

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

def _count_expr(cols):
    return " + ".join([f"CASE WHEN TRIM({c}) IS NOT NULL THEN 1 ELSE 0 END" for c in cols])

def build_structured_sql(intent: dict, allow_unlimited: bool):
    where = []
    binds = {}

    for i, f in enumerate(intent.get("filters", [])):
        kind = f.get("kind")

        if kind == "group_count":
            group = f.get("group")
            count = int(f.get("count"))
            cols = WARP_COLS if group == "warp" else WEFT_COLS
            where.append(f"({_count_expr(cols)}) = :cnt{i}")
            binds[f"cnt{i}"] = count

        elif kind == "contains":
            col = f.get("column")
            raw_val = str(f.get("value"))
            val = " ".join(raw_val.split()).lower()

            if _is_yarn_token(raw_val):
                # token/boundary match (avoid matching 18/1 when user asked 8/1)
                # (^|[^0-9])8/1 oe($|[^0-9a-z]) is a practical boundary rule
                pattern = rf"(^|[^0-9]){re.escape(val)}($|[^0-9a-z])"
                where.append(f"REGEXP_LIKE({_norm_expr(col)}, :re{i})")
                binds[f"re{i}"] = pattern
            else:
                where.append(f"{_norm_expr(col)} LIKE '%' || :val{i} || '%'")
                binds[f"val{i}"] = val


        elif kind == "equals":
            col = f.get("column")
            val = " ".join(str(f.get("value")).split()).lower()
            where.append(f"{norm_text_sql(col)} = :eq{i}")
            binds[f"eq{i}"] = val



        elif kind == "numeric":
            col = f.get("column")
            op = f.get("operator", "=")
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

def norm_text_sql(expr: str) -> str:
    # lower + collapse whitespace + trim
    return f"LOWER(REGEXP_REPLACE(TRIM({expr}), '\\s+', ' '))"


def _norm_expr(col: str) -> str:
    return f"LOWER(REGEXP_REPLACE(TRIM({col}), '\\s+', ' '))"

def _is_yarn_token(val: str) -> bool:
    # e.g. "8/1 OE", "10/1 RING", "7/1 OESLUB"
    v = " ".join(val.split())
    return bool(re.search(r"\b\d+\s*/\s*\d+\b", v))
