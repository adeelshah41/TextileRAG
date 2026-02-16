from core.config import settings

WARP_COLS = ["WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3"]
WEFT_COLS = ["WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3"]

def _count_expr(cols):
    return " + ".join(
        [f"CASE WHEN TRIM({c}) IS NOT NULL THEN 1 ELSE 0 END" for c in cols]
    )

def build_structured_sql(intent: dict, allow_unlimited: bool):
    table = settings.oracle_table

    where_clauses = []
    binds = {}

    for i, f in enumerate(intent.get("filters", [])):
        if f["kind"] == "group_count":
            cols = WARP_COLS if f["group"] == "warp" else WEFT_COLS
            expr = _count_expr(cols)
            where_clauses.append(f"({expr}) = :cnt{i}")
            binds[f"cnt{i}"] = int(f["count"])

        elif f["kind"] == "contains":
            col = f["column"]
            where_clauses.append(f"LOWER({col}) LIKE LOWER('%' || :val{i} || '%')")
            binds[f"val{i}"] = f["value"]

        elif f["kind"] == "numeric":
            col = f["column"]
            op = f["operator"]
            where_clauses.append(f"{col} {op} :num{i}")
            binds[f"num{i}"] = f["value"]

        elif f["kind"] == "equals":
            col = f["column"]
            where_clauses.append(f"{col} = :eq{i}")
            binds[f"eq{i}"] = f["value"]

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sql = f"""
    SELECT *
    FROM {table}
    WHERE {where_sql}
    """.strip().replace("\n", " ")

    if not allow_unlimited:
        sql += f" FETCH FIRST {settings.hard_max_rows} ROWS ONLY"

    return sql, binds
