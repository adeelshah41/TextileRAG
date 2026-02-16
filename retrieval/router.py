from llm.client import llm

ROUTER_SYSTEM = """
You are a query routing classifier for a fabric assistant.

Classify the user's question into exactly ONE of the following categories:

DETERMINISTIC:
- Questions requiring counting structured columns
- Logical checks (double/triple warp, presence/absence)
- Pure calculations based on structured fields

SQL:
- Structured filtering, aggregation, numeric comparisons
- Exact matches, ranges, max/min/count

HYBRID:
- Similarity, recommendations, alternative suggestions
- Queries requiring semantic comparison

FULLTEXT:
- Searching descriptive phrases inside FULL_DESCRIPTION
- Narrative text-based queries

Return ONLY one word:
DETERMINISTIC or SQL or HYBRID or FULLTEXT
"""

def route_mode(user_question: str) -> str:
    response = llm.generate(ROUTER_SYSTEM, user_question)
    decision = response.strip().upper()

    if decision not in ["DETERMINISTIC", "SQL", "HYBRID", "FULLTEXT"]:
        return "SQL"  # safe fallback

    return decision


def wants_entire_list(user_question: str) -> bool:
    q = user_question.lower()
    return ("entire" in q or "all" in q) and ("list" in q or "show" in q or "give" in q)
