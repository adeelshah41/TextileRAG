from core.config import settings

WARP_COLS = ["WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3"]
WEFT_COLS = ["WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3"]

def _count_expr(cols):
    return " + ".join([f"CASE WHEN TRIM({c}) IS NOT NULL THEN 1 ELSE 0 END" for c in cols])

def build_sql_from_intent(intent: dict, allow_unlimited: bool):
    t = intent["type"]

    if t == "group_count_filter":
        group = intent["group"]
        count = int(intent["count"])
        cols = WARP_COLS if group == "warp" else WEFT_COLS
        cnt = _count_expr(cols)

        sql = f"""
        SELECT STYLE, OZ, WEAVE, QUALITY,
               {", ".join(cols)}
        FROM {settings.oracle_table}
        WHERE ({cnt}) = :cnt
        """.strip().replace("\n", " ")
        binds = {"cnt": count}

        # optional contains constraint
        if "contains" in intent and intent["contains"]:
            col = intent["contains"]["column"]
            val = intent["contains"]["value"]
            sql += f" AND TRIM({col}) LIKE '%' || :val || '%'"
            binds["val"] = val

        if not allow_unlimited:
            sql += f" FETCH FIRST {settings.default_max_rows} ROWS ONLY"

        return sql, binds

    raise ValueError(f"Unsupported intent: {t}")
