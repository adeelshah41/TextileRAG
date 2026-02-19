# retrieval/row_analyzer.py
# from core.llm import llm
from llm.client import llm
def analyze_rows(df, args: dict) -> str:
    """
    Reason over rows using LLM.
    args: operation = [compare, summarize, count, entity]
          columns = list of columns for comparison
    """
    operation = args.get("operation", "summarize")
    # Only keep necessary columns to reduce LLM input size
    default_cols = ["STYLE", "WEAVE", "WARP_ITEM_DESC1", "WARP_ITEM_DESC2", "WARP_ITEM_DESC3",
                    "WEFT_ITEM_DESC1", "WEFT_ITEM2", "WEFT_ITEM3", "OZ", "FINISH_TYPE", "QUALITY"]
    columns = args.get("columns", default_cols)
    columns = [c for c in columns if c in df.columns]  # ignore missing columns

    # Convert only the subset of rows
    rows_json = df[columns].to_dict(orient="records")


    prompt = f"""
You are an expert fabric analyst.
Operation: {operation}
Columns: {columns}
Rows: {rows_json}

Return a concise, user-friendly natural language answer.
"""
    # answer = llm.generate(prompt)
    answer = llm.generate(prompt, user="row_analyzer")

    return answer
