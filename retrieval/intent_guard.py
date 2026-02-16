from __future__ import annotations
import re

# map columns to keywords that justify them
COLUMN_KEYWORDS = {
    "NO_OF_ENDS": ["end", "ends"],
    "REED_SPACE": ["reed", "reed space"],
    "PPI_INCH": ["ppi", "pick", "picks"],
    "WEAVE": ["weave"],
    "QUALITY": ["quality"],
    "OZ": ["oz", "ounce", "weight", "weigh"],
    "WARP_ITEM_DESC1": ["warp"],
    "WARP_ITEM_DESC2": ["warp"],
    "WARP_ITEM_DESC3": ["warp"],
    "WEFT_ITEM_DESC1": ["weft"],
    "WEFT_ITEM2": ["weft"],
    "WEFT_ITEM3": ["weft"],
    "FULL_DESCRIPTION": ["description", "full description", "constructed", "uses", "integration"],
}

def _user_mentions_column(question: str, col: str) -> bool:
    q = question.lower()
    for kw in COLUMN_KEYWORDS.get(col, []):
        if kw in q:
            return True
    return False

def guard_intent(question: str, intent: dict) -> dict:
    """
    Remove hallucinated filters not supported by user text.
    Also enforce group_count filters are pure (no extra fields).
    """
    q = question.lower()
    out = dict(intent)
    filters = out.get("filters", []) or []
    new_filters = []

    for f in filters:
        kind = f.get("kind")

        # group_count should never introduce column/value/operator
        if kind == "group_count":
            new_filters.append({
                "kind": "group_count",
                "group": f.get("group"),
                "count": int(f.get("count", 0) or 0)
            })
            continue

        col = (f.get("column") or "").upper()

        # If filter references a column, user must mention related concept
        if col and not _user_mentions_column(question, col):
            # drop hallucinated filter
            continue

        new_filters.append(f)

    out["filters"] = new_filters
    return out
