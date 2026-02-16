import re

DISALLOWED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)

COMMENT = re.compile(r"(--|/\*|\*/)", re.IGNORECASE)


def is_safe_select(sql: str) -> tuple[bool, str]:
    s = sql.strip()

    if ";" in s:
        return False, "Semicolons are not allowed."
    if COMMENT.search(s):
        return False, "SQL comments are not allowed."
    if DISALLOWED.search(s):
        return False, "Only SELECT statements are allowed."
    if not s[:6].upper() == "SELECT":
        return False, "Only SELECT statements are allowed."
    if re.search(r"\bSELECT\s+\*\b", s, re.IGNORECASE):
        return False, "SELECT * is not allowed."

    return True, ""
