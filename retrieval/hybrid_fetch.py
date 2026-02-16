# retrieval/hybrid_fetch.py
from core.config import settings
from db.oracle import db

def fetch_by_styles(styles: list[str], allow_unlimited: bool):
    if not styles:
        return db.fetch_df(f"SELECT STYLE, OZ, WEAVE, QUALITY, FULL_DESCRIPTION FROM {settings.oracle_table} WHERE 1=0"), ""

    # hard cap styles list to avoid huge IN clauses
    styles = styles[:500]

    # numeric-only if STYLE is numeric in DB
    # styles = [s for s in styles if str(s).isdigit()]

    in_list = ", ".join([f":s{i}" for i in range(len(styles))])
    binds = {f"s{i}": styles[i] for i in range(len(styles))}

    sql = f"""
    SELECT STYLE, OZ, WEAVE, QUALITY, FULL_DESCRIPTION,
           WARP_ITEM_DESC1, WARP_ITEM_DESC2, WARP_ITEM_DESC3,
           WEFT_ITEM_DESC1, WEFT_ITEM2, WEFT_ITEM3,
           NO_OF_ENDS, REED_SPACE, PPI_INCH
    FROM {settings.oracle_table}
    WHERE STYLE IN ({in_list})
    """.strip().replace("\n", " ")

    if not allow_unlimited:
        sql += f" FETCH FIRST {settings.default_max_rows} ROWS ONLY"

    df = db.fetch_df(sql, binds)
    return df, sql
