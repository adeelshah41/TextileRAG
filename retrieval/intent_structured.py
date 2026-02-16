import json
from llm.client import llm

STRUCT_INTENT_SYSTEM = """
Extract structured intent as JSON ONLY.

Schema:
- type: "group_count_filter" | "field_contains"
- group: "warp" | "weft" (only for group_count_filter)
- count: integer (only for group_count_filter)
- contains: optional object { "column": "WEFT_ITEM_DESC1"|"WARP_ITEM_DESC1"|... , "value": string }

Rules:
- "single/double/triple" -> 1/2/3 and group_count_filter
- If question mentions "warp yarn counts" -> group="warp"
- If question mentions "weft yarn count" -> group="weft"
- If question includes a yarn token like "8/1 OE" and says weft -> contains.column="WEFT_ITEM_DESC1", contains.value="8/1 OE"
Return JSON only.
"""

def extract_structured_intent(q: str) -> dict:
    raw = llm.generate(STRUCT_INTENT_SYSTEM, q).strip()
    raw = raw.strip("` \n")
    return json.loads(raw)
