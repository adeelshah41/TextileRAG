import re

def detect_yarn_count_constraint(q: str):
    """
    Returns (group, count) if query contains single/double/triple + warp/weft.
    Else returns None.
    """
    ql = q.lower()

    m = re.search(r"\b(single|double|triple)\b", ql)
    if not m:
        return None

    word = m.group(1)
    count = {"single": 1, "double": 2, "triple": 3}[word]

    if "warp" in ql:
        return ("WARP", count)
    if "weft" in ql:
        return ("WEFT", count)

    return None
