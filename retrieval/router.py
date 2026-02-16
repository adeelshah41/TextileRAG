# retrieval/router.py
from __future__ import annotations

import re

def wants_entire_list(user_question: str) -> bool:
    q = (user_question or "").lower()
    return ("entire" in q or "all" in q) and ("list" in q or "show" in q or "give" in q)

def route_mode(user_question: str) -> str:
    """
    RAG-first routing:
    - HYBRID is the default.
    - STRUCTURED only when user clearly wants an exact list using strict constraints.
    """
    q = (user_question or "").lower()

    # Strong signals for structured listing
    if wants_entire_list(user_question):
        return "STRUCTURED"

    if re.search(r"\b(exactly|equal to|equals)\b", q) and re.search(r"\b(oz|ppi|ends|reed|finish|weave|quality|style)\b", q):
        return "STRUCTURED"

    if re.search(r"\b(list|show|give)\b", q) and re.search(r"\b(oz|ppi|ends|reed|finish|weave|quality|style|warp|weft)\b", q):
        # "list fabrics with X" is often structured, but keep HYBRID unless it's strict
        if re.search(r"\b(>=|<=|>|<|=)\b", q) or re.search(r"\b(exact|exactly)\b", q):
            return "STRUCTURED"

    return "HYBRID"
