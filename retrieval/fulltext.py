from db.oracle import db
from core.config import settings

def run_fulltext(user_question: str, allow_unlimited: bool):
    """
    Searches FULL_DESCRIPTION for descriptive phrases.
    """

    phrase = user_question.lower()

    sql = f"""
    SELECT STYLE, OZ, WEAVE, QUALITY, FULL_DESCRIPTION
    FROM {settings.oracle_table}
    WHERE LOWER(FULL_DESCRIPTION) LIKE '%' || :phrase || '%'
    """

    if not allow_unlimited:
        sql += f" FETCH FIRST 200 ROWS ONLY"

    df = db.fetch_df(sql, {"phrase": phrase})

    return df, sql
