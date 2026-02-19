# retrieval/executor.py
from retrieval.structured_runner import run_structured_with_retries
from retrieval.hybrid import run_hybrid
from retrieval.row_analyzer import analyze_rows

def execute_plan(plan: list, user_question: str, debug: bool = False):
    """
    Execute the multi-step plan returned by the planner.
    Returns final_answer (NL) and list of intermediate results.
    """
    intermediate_results = []
    last_rows = None

    for step in plan:
        tool = step.get("tool")
        args = step.get("args", {})
        step_num = step.get("step", 0)

        result = {}
        
        # Resolve rows_from_step references
        if "rows_from_step" in args:
            ref_step = args.pop("rows_from_step")
            if ref_step <= 0 or ref_step > len(intermediate_results):
                raise ValueError(f"Invalid rows_from_step: {ref_step}")
            last_rows = intermediate_results[ref_step - 1]["df"]

        if tool == "structured_sql":
            df, sql, _ = run_structured_with_retries(user_question, args, allow_unlimited=True)
            last_rows = df
            result.update({"step": step_num, "tool": tool, "df": df, "sql": sql})

        elif tool == "hybrid_search":
            df, used_sql, debug_sql, ranked_df = run_hybrid(user_question, allow_unlimited=True)
            last_rows = df
            result.update({
                "step": step_num,
                "tool": tool,
                "df": df,
                "sql": used_sql,
                "ranked_df": ranked_df
            })

        # executor.py, inside for step in plan
        elif tool == "row_analyzer":
            # Resolve rows_from_step
            if "rows_from_step" in args:
                ref_step = args.pop("rows_from_step")
                if ref_step <= 0 or ref_step > len(intermediate_results):
                    raise ValueError(f"Invalid rows_from_step: {ref_step}")
                last_rows = intermediate_results[ref_step - 1]["df"]

            if last_rows is None:
                raise ValueError("row_analyzer called but no previous rows found.")

            # Optional: limit number of rows for LLM
            MAX_ROWS = 20
            if last_rows.shape[0] > MAX_ROWS:
                last_rows = last_rows.head(MAX_ROWS)

            summary = analyze_rows(last_rows, args)
            result.update({"step": step_num, "tool": tool, "summary": summary})


        else:
            raise ValueError(f"Unknown tool: {tool}")

        intermediate_results.append(result)

    # Final answer is the summary of the last step if available
    final_answer = intermediate_results[-1].get("summary") or f"Fetched {len(last_rows)} rows."

    return final_answer, intermediate_results
