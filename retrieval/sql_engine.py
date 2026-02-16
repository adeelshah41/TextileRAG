from __future__ import annotations

import re
from core.config import settings
from core.logger import get_logger
from llm.client import llm
from llm.prompts import SYSTEM_SQL, SYSTEM_FIX, FABRIC_SCHEMA_HINT
from db.oracle import db
from db.safety import is_safe_select
from data.fewshot_examples import FEW_SHOT

log = get_logger("retrieval.sql_engine")


def _fewshot_block() -> str:
    blocks = []
    for ex in FEW_SHOT:
        blocks.append(f"Q: {ex['question']}\nSQL: {ex['sql']}")
    return "\n\n".join(blocks)


def _extract_sql(text: str) -> str:
    """
    Pull SQLQuery: ... line
    """
    m = re.search(r"SQLQuery:\s*(.*)", text, re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).strip()


def generate_sql(user_question: str, allow_unlimited: bool, style_whitelist: list[str] | None = None) -> str:
    fewshot = _fewshot_block()
    whitelist_hint = ""
    if style_whitelist:
        # Keep it short; if too long, LLM prompt gets huge.
        preview = ", ".join(style_whitelist[:50])
        whitelist_hint = f"\nYou MUST restrict results to STYLE IN ({preview}{', ...' if len(style_whitelist)>50 else ''}).\n"

    limit_hint = ""
    if allow_unlimited:
        limit_hint = f"\nUser requested the entire list. You MAY omit row limit, but do not exceed {settings.hard_max_rows} rows if you add a limit.\n"
    else:
        limit_hint = f"\nAdd: FETCH FIRST {settings.default_max_rows} ROWS ONLY unless the question is clearly an aggregation (MAX/MIN/COUNT).\n"

    user_prompt = f"""
{FABRIC_SCHEMA_HINT}

Few-shot examples:
{fewshot}

Task:
Write Oracle SQL for: {user_question}
{limit_hint}
{whitelist_hint}
""".strip()

    out = llm.generate(SYSTEM_SQL, user_prompt)
    sql = _extract_sql(out)
    print(f"Generated SQL:\n{sql}")
    return sql


def run_sql_with_retries(user_question: str, initial_sql: str):
    """
    Execute with validation + retry loop:
    - validate SQL safety
    - on error, ask model to fix using error message
    - on empty results for non-aggregate, ask model to broaden slightly
    """
    sql = initial_sql
    last_err = ""
    for attempt in range(settings.sql_retry_limit + 1):
        ok, reason = is_safe_select(sql)
        if not ok:
            raise ValueError(f"Unsafe SQL blocked: {reason}\nSQL: {sql}")

        try:
            df = db.fetch_df(sql)
            # Empty handling (retry if looks like a list query)
            if df.shape[0] == 0 and not _looks_like_aggregate(sql) and attempt < settings.sql_retry_limit:
                fix_prompt = f"""
User question: {user_question}
Current SQLQuery: {sql}
Problem: SQL returned 0 rows. Broaden the query slightly without changing the user's intent.
Keep it safe and still specific.
""".strip()
                out = llm.generate(SYSTEM_FIX, fix_prompt)
                sql = _extract_sql(out) or sql
                continue

            return df, sql

        except Exception as e:
            last_err = str(e)
            if attempt >= settings.sql_retry_limit:
                raise

            fix_prompt = f"""
User question: {user_question}
Current SQLQuery: {sql}
Oracle error: {last_err}
Fix the SQL. Keep the same intent.
""".strip()
            out = llm.generate(SYSTEM_FIX, fix_prompt)
            sql2 = _extract_sql(out)
            if sql2:
                sql = sql2

    raise RuntimeError(f"Failed after retries. Last error: {last_err}")


def _looks_like_aggregate(sql: str) -> bool:
    s = sql.upper()
    return any(k in s for k in [" MAX(", " MIN(", " COUNT(", " AVG(", " SUM("])
