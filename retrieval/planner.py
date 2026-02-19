# retrieval/planner.py
import json
# from core.llm import llm  # Your LLM wrapper
from llm.client import llm

def planner_llm(question: str, debug: bool = False) -> dict:
    """
    Generates a multi-step plan as JSON for the agent.
    Tools: structured_sql, hybrid_search, row_analyzer
    """
    prompt = f"""
    You are a planner AI. 
    Given a user question, decide the steps needed to answer it using available tools.

    Tools:
    - structured_sql(filters) → deterministic SQL query
    - hybrid_search(query) → combined keyword + vector search
    - row_analyzer(rows, operation, columns) → reason over rows for comparison, aggregation, or entity lookup

    Requirements:
    - Multi-step if needed
    - Return plan as valid JSON array of steps
    - Each step: {{"step": int, "tool": str, "args": dict}}
    - IMPORTANT: To refer to rows from a previous step, use the key
        "rows_from_step": <step_number>
    DO NOT use a string like "rows_from_step:1"

    User question: \"\"\"{question}\"\"\" 
    Return only valid JSON.
    """

    # raw = llm.generate(prompt)
    raw = llm.generate(prompt, user="planner_agent")

    s = raw.strip()
    try:
        plan = json.loads(s)
    except Exception:
        raise ValueError(f"Planner returned invalid JSON:\n{raw}")
    
    if debug:
        print("Planner JSON:", plan)
    return plan
