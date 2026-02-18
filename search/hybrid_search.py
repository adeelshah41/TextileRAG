# search/hybrid_search.py

import pandas as pd
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")

def run_hybrid_search(question, connection, top_k=50):
    query_vector = model.encode(question).astype("float32").tolist()
    cursor = connection.cursor()

    # 1️⃣ Keyword search
    keyword_sql = """
        SELECT ID,
               STYLE,
               OZ,
               WEAVE,
               QUALITY,
               FULL_DESCRIPTION,
               1 AS keyword_score
        FROM fabric_specs
        WHERE LOWER(FULL_DESCRIPTION) LIKE '%' || :kw || '%'
    """
    cursor.execute(keyword_sql, {"kw": question.lower()})
    keyword_rows = cursor.fetchall()

    # 2️⃣ Vector search
    vector_sql = f"""
        SELECT ID,
               STYLE,
               OZ,
               WEAVE,
               QUALITY,
               FULL_DESCRIPTION,
               VECTOR_DISTANCE(EMBEDDING_BGE_M3, :vec, COSINE) AS distance
        FROM fabric_specs
        ORDER BY distance
        FETCH FIRST {top_k} ROWS ONLY
    """
    cursor.execute(vector_sql, {"vec": query_vector})
    vector_rows = cursor.fetchall()
    cursor.close()

    df_keyword = pd.DataFrame(keyword_rows, columns=[
        "ID","STYLE","OZ","WEAVE","QUALITY","FULL_DESCRIPTION","keyword_score"
    ])

    df_vector = pd.DataFrame(vector_rows, columns=[
        "ID","STYLE","OZ","WEAVE","QUALITY","FULL_DESCRIPTION","distance"
    ])

    if df_vector.empty:
        return df_keyword

    df_vector["vector_score"] = 1 - df_vector["distance"]

    # Merge keyword + vector results
    df = pd.merge(
        df_vector,
        df_keyword[["ID","keyword_score"]],
        on="ID",
        how="left"
    )

    df["keyword_score"] = df["keyword_score"].fillna(0)
    df["hybrid_score"] = (0.7 * df["vector_score"]) + (0.3 * df["keyword_score"])

    df = df.sort_values("hybrid_score", ascending=False)

    return df.drop(columns=["distance"], errors="ignore").reset_index(drop=True)
