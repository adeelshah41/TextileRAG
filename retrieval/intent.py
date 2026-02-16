# retrieval/intent.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from llm.client import llm

ALLOWED_COLUMNS = [
    "STYLE", "FINISH_TYPE", "OZ", "WEAVE", "QUALITY", "ITEM",
    "WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3",
    "NO_OF_ENDS", "REED_SPACE",
    "WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3",
    "PPI_INCH", "FULL_DESCRIPTION",
]

# RAG-first schema: intent guides retrieval, not SQL generation.
# - reference_style: enables style-to-style KNN
# - k: how many results user asked for
# - filters: optional metadata constraints (validated + compiled deterministically)
INTENT_SYSTEM = f"""
Return JSON only. No markdown. No leading 'json'. No extra text.

Allowed columns (use EXACTLY these, do not invent):
{", ".join(ALLOWED_COLUMNS)}

Schema:
{{
  "type": "hybrid" | "structured",
  "reference_style": string|null,
  "k": number|null,
  "filters": [
    {{
      "kind": "group_count" | "group_match" | "contains" | "equals" | "numeric",
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
- Prefer type="hybrid" for almost all queries, especially: similar/closest/like/recommend/suggest/alternatives, texture/feel, descriptive requests.
- Use type="structured" only for strict listing with precise filters (e.g. "list all 10 oz", "exactly 70 ppi", etc.).
- If user references a style (e.g., "similar to style 2544"), set reference_style="2544" and type="hybrid".
- If user asks "top 10" or "give 5", set k accordingly.
- For warp/weft tokens or phrases that may appear in any slot, use:
  kind="group_match", group="warp|weft", value="<token/phrase>".
  Do NOT pin to a specific WEFT_ITEM_DESC1/WARP_ITEM_DESC1 unless user explicitly says slot 1/2/3.
- "single/double/triple" + warp/weft -> kind="group_count" with count 1/2/3.
- Numeric constraints (oz/ppi/ends/reed) -> kind="numeric" with operator/value on correct column.
"""

_STYLE_REF_RE = re.compile(
    r"\b(?:style\s*[:#]?\s*)?([A-Z0-9]+(?:-[A-Z0-9]+)*)\b",
    flags=re.IGNORECASE
)

_TOPK_RE = re.compile(r"\btop\s+(\d+)\b|\bgive\s+me\s+(\d+)\b|\bshow\s+(\d+)\b", flags=re.IGNORECASE)

def _clean_json(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = re.sub(r"^\s*json\s+", "", s, flags=re.IGNORECASE)
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    return m.group(0) if m else s

def _extract_topk(question: str) -> Optional[int]:
    m = _TOPK_RE.search(question or "")
    if not m:
        return None
    for g in m.groups():
        if g and g.isdigit():
            k = int(g)
            if 1 <= k <= 200:
                return k
    return None

def _extract_reference_style(question: str) -> Optional[str]:
    q = (question or "").strip()
    if not q:
        return None

    # Only treat it as reference style when query implies similarity/neighbors.
    if not re.search(r"\b(similar|closest|like|neighbors|nearest|alternative|alternatives)\b", q, re.IGNORECASE):
        return None

    # Look for "style 2544" explicitly first.
    m = re.search(r"\bstyle\s*[:#]?\s*([A-Z0-9]+(?:-[A-Z0-9]+)*)\b", q, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Otherwise pick the best looking code-like token, but avoid generic words.
    candidates = []
    for m in _STYLE_REF_RE.finditer(q):
        tok = m.group(1).strip()
        if len(tok) < 3:
            continue
        if tok.lower() in {"fabric", "fabrics", "style", "similar", "closest", "like", "top"}:
            continue
        candidates.append(tok)

    # Prefer tokens with digits (often your style codes)
    candidates.sort(key=lambda t: (not any(ch.isdigit() for ch in t), len(t)))
    return candidates[0] if candidates else None

def extract_intent(question: str) -> dict:
    # Deterministic enrichment first (scalable): top-k + reference style
    k = _extract_topk(question)
    ref_style = _extract_reference_style(question)

    raw = llm.generate(INTENT_SYSTEM, question)
    if not raw or not raw.strip():
        raise ValueError("Intent extraction: empty LLM response.")
    s = _clean_json(raw)

    try:
        obj = json.loads(s)
    except Exception:
        raise ValueError(f"Intent extraction returned invalid JSON:\n\n{raw}")

    obj = normalize_intent(obj)

    # Deterministic overrides (do not depend on LLM correctness)
    if ref_style:
        obj["reference_style"] = ref_style
        obj["type"] = "hybrid"
    if k is not None:
        obj["k"] = k

    return obj

def normalize_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    intent = dict(intent or {})
    intent["type"] = (intent.get("type") or "hybrid").strip().lower()
    if intent["type"] not in {"hybrid", "structured"}:
        intent["type"] = "hybrid"

    intent["return_all"] = bool(intent.get("return_all", False))

    ref = intent.get("reference_style")
    intent["reference_style"] = str(ref).strip() if ref else None

    k = intent.get("k")
    try:
        k = int(k) if k is not None else None
    except Exception:
        k = None
    if k is not None and not (1 <= k <= 200):
        k = None
    intent["k"] = k

    fixed_filters: List[Dict[str, Any]] = []
    for f in intent.get("filters", []) or []:
        kind = (f.get("kind") or "").strip()

        if kind == "group_count":
            group = (f.get("group") or "").strip().lower()
            count = int(f.get("count", 0) or 0)
            fixed_filters.append({"kind": "group_count", "group": group, "count": count})
            continue

        if kind == "group_match":
            group = (f.get("group") or "").strip().lower()
            val = f.get("value")
            if group in {"warp", "weft"} and val is not None:
                fixed_filters.append({"kind": "group_match", "group": group, "value": str(val)})
            continue

        if kind in {"contains", "equals"}:
            col = (f.get("column") or "").strip().upper()
            val = f.get("value")
            if col in ALLOWED_COLUMNS and val is not None:
                fixed_filters.append({"kind": kind, "column": col, "value": val})
            continue

        if kind == "numeric":
            col = (f.get("column") or "").strip().upper()
            op = (f.get("operator") or "=").strip()
            val = f.get("value")
            if col in ALLOWED_COLUMNS and op in {"=", ">", "<", ">=", "<="}:
                fixed_filters.append({"kind": "numeric", "column": col, "operator": op, "value": val})
            continue

        # drop unknown kinds

    intent["filters"] = fixed_filters
    return intent
