# retrieval/hybrid_fetch.py
from __future__ import annotations

from typing import Dict, List, Tuple
from core.config import settings
from db.oracle import db

def fetch_by_styles(styles: List[str], allow_unlimited: bool):
    if not styles:
        return db.fetch_df(f"SELECT STYLE, OZ, WEAVE, QUALITY, FULL_DESCRIPTION FROM {settings.oracle_table} WHERE 1=0"), ""

    # cap to avoid huge IN lists
    styles = styles[:500]

    in_list = ", ".join([f":s{i}" for i in range(len(styles))])
    binds: Dict[str, object] = {f"s{i}": styles[i] for i in range(len(styles))}

    # Preserve incoming rank order deterministically
    order_case = "CASE STYLE " + " ".join([f"WHEN :s{i} THEN {i}" for i in range(len(styles))]) + f" ELSE {len(styles)} END"

    sql = f"""
    SELECT STYLE, FINISH_TYPE, OZ, WEAVE, QUALITY, ITEM, FULL_DESCRIPTION,
           WARP_ITEM_DESC1, WARP_ITEM_DESC2, WARP_ITEM_DESC3,
           WEFT_ITEM_DESC1, WEFT_ITEM2, WEFT_ITEM3,
           NO_OF_ENDS, REED_SPACE, PPI_INCH
    FROM {settings.oracle_table}
    WHERE STYLE IN ({in_list})
    ORDER BY {order_case}
    """.strip().replace("\n", " ")

    if not allow_unlimited:
        sql += f" FETCH FIRST {settings.default_max_rows} ROWS ONLY"

    df = db.fetch_df(sql, binds)
    return df, sql
