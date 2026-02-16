# retrieval/structured_runner.py
from __future__ import annotations

import json
from db.oracle import db
from llm.client import llm
from retrieval.sql_builder import build_structured_sql

STRUCT_FIX_SYSTEM = """
You fix intent JSON for a fabric database assistant.

You will be given:
- original user question
- current intent JSON
- oracle error OR empty-result message

Return JSON only (same schema). Do not invent columns. Use only allowed columns.
"""

def _fix_intent_with_llm(user_question: str, intent: dict, problem: str) -> dict:
    prompt = f"""
User question: {user_question}

Current intent JSON:
{json.dumps(intent, ensure_ascii=False)}

Problem:
{problem}

Return corrected intent JSON only.
""".strip()
    raw = llm.generate(STRUCT_FIX_SYSTEM, prompt)
    # Reuse your clean-json logic if you want; keeping simple here:
    s = raw.strip()
    s = s.strip("`")
    # Try to locate JSON object
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        s = s[start:end+1]
    return json.loads(s)

def run_structured_with_retries(user_question: str, intent: dict, allow_unlimited: bool, retry_limit: int = 2):
    """
    Retry loop for structured execution:
    - build SQL deterministically
    - execute
    - if Oracle error: ask LLM to correct INTENT JSON (not SQL)
    - if empty results and return_all/listy: ask LLM to broaden intent slightly
    """
    last_err = ""
    cur_intent = intent

    for attempt in range(retry_limit + 1):
        sql, binds = build_structured_sql(cur_intent, allow_unlimited)

        try:
            df = db.fetch_df(sql, binds)

            # Optional “empty list broadening” — only if user wanted a list
            if df.shape[0] == 0 and attempt < retry_limit:
                problem = "Query returned 0 rows. Broaden slightly without changing intent."
                cur_intent = _fix_intent_with_llm(user_question, cur_intent, problem)
                continue

            return df, sql, cur_intent

        except Exception as e:
            last_err = str(e)
            if attempt >= retry_limit:
                raise
            problem = f"Oracle error: {last_err}"
            cur_intent = _fix_intent_with_llm(user_question, cur_intent, problem)

    raise RuntimeError(f"Failed after retries. Last error: {last_err}")
