from __future__ import annotations
import re

# map columns to keywords that justify them
COLUMN_KEYWORDS = {
    "NO_OF_ENDS": ["end", "ends"],
    "REED_SPACE": ["reed", "reed space"],
    "PPI_INCH": ["ppi", "pick", "picks"],
    "WEAVE": ["weave"],
    "QUALITY": ["quality"],
    "ITEM": ["item"],
    "STYLE": ["style"],
    "FINISH_TYPE": ["finish", "finish type", "finishtype"],
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
        kw = kw.lower()
        # use word boundary for short tokens; substring ok for multi-word phrases
        if " " in kw:
            if kw in q:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", q):
                return True
    return False
def guard_intent(question: str, intent: dict) -> dict:
    """
    Remove hallucinated filters not supported by user text.
    Enforce group_count filters are pure (no extra fields).
    Enforce safety: never allow return_all when there are no filters.
    """
    out = dict(intent)
    filters = out.get("filters", []) or []
    new_filters = []

    for f in filters:
        kind = f.get("kind")

        # group_count should never introduce column/value/operator
        if kind == "group_count":
            new_filters.append({
                "kind": "group_count",
                "group": (f.get("group") or "").lower(),
                "count": int(f.get("count", 0) or 0),
            })
            continue

        col = (f.get("column") or "").upper()

        # If filter references a column, user must mention related concept
        if col and not _user_mentions_column(question, col):
            continue

        new_filters.append(f)

    out["filters"] = new_filters

    # SAFETY: If no filters, do not allow full-table return
    if not out["filters"]:
        out["return_all"] = False
        # optional but sensible: structured w/ no filters is useless
        if out.get("type") == "structured":
            out["type"] = "hybrid"

    return out

def enrich_intent(question: str, intent: dict) -> dict:
    """
    Deterministic enrichment for common domain patterns when the LLM misses them.
    Only adds filters that are strongly implied by user text.
    """
    out = dict(intent)
    q = question.strip()

    # If LLM found filters, keep them; enrichment is mainly for misses.
    if out.get("filters"):
        return out

    ql = q.lower()

    # FINISH_TYPE pattern: "finish type: MRCZ-LHR" / "finish MRCZ-LHR"
    m = re.search(r"(?:finish\s*type|finish)\s*[:=]?\s*([A-Z0-9]+(?:-[A-Z0-9]+)+)", q, re.I)
    if m:
        code = m.group(1).strip()
        out["type"] = "structured"
        out["filters"] = [{
            "kind": "equals",
            "column": "FINISH_TYPE",
            "value": code
        }]
        out["return_all"] = False
        return out

    return out
