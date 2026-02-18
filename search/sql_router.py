# search/sql_router.py

import re
import pandas as pd

def is_structured_query(question: str) -> bool:
    patterns = [
        r"\b\d+\s?oz\b",
        r"\bwarp\b",
        r"\bweft\b",
        r"\bppi\b",
    ]
    return any(re.search(p, question.lower()) for p in patterns)


def run_structured_query(question: str, connection):
    cursor = connection.cursor()

    # Weight query (OZ is VARCHAR)
    match = re.search(r"(\d+)\s?oz", question.lower())
    if match:
        weight = match.group(1)
        sql = """
            SELECT ID,
                   STYLE,
                   OZ,
                   WEAVE,
                   QUALITY,
                   FULL_DESCRIPTION
            FROM fabric_specs
            WHERE LOWER(OZ) LIKE :w
        """
        cursor.execute(sql, {"w": f"%{weight}%"})
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
        cursor.close()
        return pd.DataFrame(rows, columns=cols), sql

    cursor.close()
    return pd.DataFrame(), None
