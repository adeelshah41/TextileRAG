# retrieval/intent.py
from __future__ import annotations

import json
import re
from llm.client import llm
import re


ALLOWED_COLUMNS = [
    "STYLE", "FINISH_TYPE", "OZ", "WEAVE", "QUALITY", "ITEM",
    "WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3",
    "NO_OF_ENDS", "REED_SPACE",
    "WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3",
    "PPI_INCH", "FULL_DESCRIPTION"
]

INTENT_SYSTEM = f"""
Return JSON only. No markdown. No leading 'json'. No extra text.

Allowed columns (use EXACTLY these, do not invent):
{", ".join(ALLOWED_COLUMNS)}

Schema:
{{
  "type": "structured" | "hybrid",
  "filters": [
    {{
      "kind": "group_count" | "contains" | "equals" | "numeric",
      "group": "warp" | "weft",
      "column": "<one of allowed columns>",
      "operator": "=" | ">" | "<" | ">=" | "<=",
      "value": string|number,
      "count": 1|2|3
    }}
  ],
  "return_all": true|false
}}

Rules:
- If user asks to LIST ALL matching fabrics, or asks an exact condition -> type="structured".
- If user asks similar/recommend/suggest/closest/like -> type="hybrid".
- "single/double/triple" + warp/weft -> group_count with count 1/2/3.
- If user says "weigh exactly 10 oz" -> numeric filter on column "OZ" with value 10 and operator "=".
- For "8/1 OE weft" use contains on column "WEFT_ITEM_DESC1".
"""

def _clean_json(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = re.sub(r"^\s*json\s+", "", s, flags=re.IGNORECASE)
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    return m.group(0) if m else s

def extract_intent(question: str) -> dict:
    raw = llm.generate(INTENT_SYSTEM, question)
    
    if not raw or not raw.strip():
        raise ValueError("Intent extraction: empty LLM response.")
    s = _clean_json(raw)
    try:
        obj = json.loads(s)
        obj = normalize_intent(obj)
    except Exception:
        raise ValueError(f"Intent extraction returned invalid JSON:\n\n{raw}")
    return obj

def normalize_intent(intent: dict) -> dict:
    """
    Enforces the intent contract:
    - group_count only keeps (kind, group, count)
    - if group_count wrongly includes (column/value), convert them into a separate 'contains'
    - ensure return_all is boolean
    """
    intent = dict(intent or {})
    intent["type"] = (intent.get("type") or "").strip().lower()
    intent["return_all"] = bool(intent.get("return_all", False))

    fixed_filters = []
    for f in intent.get("filters", []) or []:
        kind = (f.get("kind") or "").strip()

        if kind == "group_count":
            group = (f.get("group") or "").strip().lower()
            count = int(f.get("count", 0) or 0)

            # Keep only the valid keys for group_count
            fixed_filters.append({"kind": "group_count", "group": group, "count": count})

            # If the model incorrectly stuffed a value/column here, salvage it as a contains filter
            col = f.get("column")
            val = f.get("value")
            if col and val:
                fixed_filters.append({"kind": "contains", "column": col, "value": val})

        elif kind in ("contains", "equals", "numeric"):
            # keep as-is (builder will validate)
            fixed_filters.append(f)

        else:
            # drop unknown filter types
            continue

    intent["filters"] = fixed_filters
    return intent


def upgrade_contains_to_equals_for_yarn_count(question: str, intent: dict) -> dict:
    q = question.lower()
    if "yarn count of" not in q:
        return intent

    upgraded = []
    for f in intent.get("filters", []):
        if f.get("kind") == "contains":
            val = str(f.get("value", ""))
            # yarn token heuristic: has digit/digit pattern
            if re.search(r"\b\d+\s*/\s*\d+\b", val):
                f = dict(f)
                f["kind"] = "equals"
        upgraded.append(f)

    intent["filters"] = upgraded
    return intent
