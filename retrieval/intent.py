import json
from llm.client import llm

INTENT_SYSTEM = """
You are an intent extraction engine for a fabric database assistant.

Return ONLY valid JSON.

Schema:
{
  "type": "structured" | "hybrid",
  "filters": [
    {
      "kind": "group_count" | "contains" | "numeric" | "equals",
      "group": "warp" | "weft",              # only for group_count
      "column": string,                      # for contains/numeric/equals
      "operator": "=" | ">" | "<" | ">=" | "<=",  # for numeric
      "value": string or number,
      "count": number                        # for group_count
    }
  ],
  "return_all": true | false
}

Rules:
- If question asks for ALL fabrics matching constraints → type="structured"
- If question is descriptive/similarity/recommendation → type="hybrid"
- "single/double/triple warp/weft" → group_count with count=1/2/3
- Weight questions → numeric on OZ
- PPI/ends/reed → numeric
- Yarn token like "8/1 OE" → contains on appropriate column
- Never generate SQL.
"""

def extract_intent(question: str) -> dict:
    raw = llm.generate(INTENT_SYSTEM, question).strip()
    raw = raw.strip("` \n")
    return json.loads(raw)
