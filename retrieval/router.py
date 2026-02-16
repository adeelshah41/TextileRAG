from llm.client import llm

ROUTER_SYSTEM = """
You are a routing classifier for a fabric assistant.

Return ONLY one of these tokens:
DETERMINISTIC
SQL
HYBRID

Definitions:

DETERMINISTIC:
- Questions about counting/boolean logic on structured yarn columns
  (WARP_ITEM_DESC1/2/3, WEFT_ITEM_DESC1/2/3)
- Examples:
  - "How many warp yarn counts are used in style 2544?"
  - "Is style 2544 double warp?"
  - "Warp1 and warp2 but not warp3"

SQL:
- Exact filtering/aggregation that is naturally expressed as SQL conditions
- Examples:
  - "list fabrics exactly 10 oz"
  - "max weight"
  - "warp item desc1 equals 7/1 RINGSLUB"

HYBRID:
- Any descriptive, semantic, fuzzy, or phrase-based search
- Any query that looks like searching FULL_DESCRIPTION content
- Examples:
  - "technical density defined by 4500 ends"
  - "fabric using single weft yarn count of 8/1 OE"
  - "3 x 1 bt weave slub fabric"
  - "constructed with triple warp yarn counts"

Return only the token.
"""

def route_mode(user_question: str) -> str:
    out = llm.generate(ROUTER_SYSTEM, user_question)
    return (out or "").strip().upper()
