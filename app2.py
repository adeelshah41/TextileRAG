import oracledb
import array
import json
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os
from huggingface_hub import InferenceClient
import streamlit as st
# --- CONFIGURATION ---
load_dotenv()

st.set_page_config(page_title="SM Denim Fabric Assistant", layout="wide")
st.title("SM Denim Fabric Assistant")
st.caption("Oracle 23ai + Structured Intent + Deterministic SQL + Hybrid (Keyword+Vector)")
with st.sidebar:
    st.subheader("Settings")
    show_debug = st.checkbox("Show debug", value=True)
st.divider()

example_qs = [
    "give the list of all the fabrics that weigh exactly 10 oz (entire list)",
    "fabrics constructed with triple warp yarn counts",
    "fabric using single weft yarn count of 8/1 OE",
    "similar to style 2544 but lighter",
    "recommend alternatives to rain slub stretch",
]
st.write("**Try examples:**")
cols = st.columns(2)
for i, qq in enumerate(example_qs):
    if cols[i % 2].button(qq, use_container_width=True):
        st.session_state["q"] = qq

q = st.text_area("Ask a question:", value=st.session_state.get("q", ""), height=90)

@st.cache_resource
def load_hf_client():
    return InferenceClient(api_key=os.environ["HF_TOKEN"])

client = load_hf_client()

# 🔥 Using Qwen2.5-72B-Instruct
# LLM_MODEL = "Qwen/Qwen2.5-32B-Instruct"
LLM_MODEL = "Qwen/Qwen2.5-7B-Instruct"
# LLM_MODEL = "Qwen/Qwen2.5-72B-Instruct"

@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("BAAI/bge-m3")

model = load_embedding_model()

SYSTEM_PROMPT = """
### ROLE
You are a Textile Data Engineer. Your job is to extract search parameters from user queries to help filter an Oracle Database of fabric specifications.

### DATABASE SCHEMA REFERENCE
- PPI_INCH (Number): The picks per inch.
- OZ (Number/String): The weight in ounces (e.g., 10.25).
- WEAVE (String): The pattern (e.g., 'Satin', 'Z', 'Bt', 'Slub').
- STYLE (String): Unique style identifiers.
- REED_SPACE (Number): The width/technical density.

### EXTRACTION RULES
1. Extract "Hard Filters" (numeric constraints like PPI or Oz) into a JSON object.
2. If a user says "at least", "over", or "more than", use the "min" keys.
3. If a user says "less than" or "under", use the "max" keys.
4. Extract the "Semantic Search" term (the descriptive part) into the 'search_text' key.
5. If a parameter isn't mentioned, return null for that key.
6. If user asks for "entire list", set return_all = true.
7. If user asks for a specific number (e.g. 5 fabrics), set limit = that number.
8. If user asks "how many", set count_only = true.
9. If none specified, limit = 3.
### OUTPUT FORMAT
Return ONLY a JSON object with this structure:
{
  "search_text": string or null,
  "ppi_min": number or null,
  "ppi_max": number or null,
  "oz_min": number or null,
  "oz_max": number or null,
  "weave_pattern": string or null,
  "limit": number or null,
  "return_all": boolean or null,
  "count_only": boolean or null
}

"""

RESPONSE_PROMPT = """
You are a professional textile fabric assistant.

The user asked:
{user_query}

Here are the database results:
{results}

Generate a clear, professional, user-friendly response.

Guidelines:
- If multiple fabrics are returned, present them clearly as a list.
- If one fabric is returned, describe it naturally.
- If no fabrics are found, politely say so.
- Do not mention SQL, database, or internal system logic.
- Be concise but informative.
"""
@st.cache_resource
def get_pool():
    return oracledb.create_pool(
        user="rag",
        password="rag",
        dsn="172.16.121.230:1521/FREEPDB1",
        min=1,
        max=4,
        increment=1
    )

pool = get_pool()

# 1. UPDATED SEARCH FUNCTION (UNCHANGED)




def get_hybrid_context(search_text, filters):
    query_embedding = model.encode(search_text or "").tolist()
    vector_data = array.array("f", query_embedding)

    with pool.acquire() as conn:
        with conn.cursor() as cursor:
            sql = """
                SELECT STYLE, WEAVE, PPI_INCH, OZ, FULL_DESCRIPTION,
                       VECTOR_DISTANCE(EMBEDDING_BGE_M3, :1, COSINE) as score
                FROM fabric_specs
                WHERE 1=1
            """

            params = [vector_data]

            if filters.get("ppi_min"):
                sql += " AND PPI_INCH >= :2"
                params.append(filters["ppi_min"])

            if filters.get("ppi_max"):
                sql += f" AND PPI_INCH <= :{len(params)+1}"
                params.append(filters["ppi_max"])

            if filters.get("weave_pattern"):
                sql += f" AND LOWER(WEAVE) LIKE :{len(params)+1}"
                params.append(f"%{filters['weave_pattern'].lower()}%")

            if filters.get("oz_min"):
                sql += f" AND OZ >= :{len(params)+1}"
                params.append(filters["oz_min"])

            limit = filters.get("limit")
            return_all = filters.get("return_all")
            count_only = filters.get("count_only")

            if count_only:
                sql = f"SELECT COUNT(*) FROM ({sql})"
            elif not return_all:
                sql += f" ORDER BY score ASC FETCH FIRST {limit or 3} ROWS ONLY"
            else:
                sql += " ORDER BY score ASC"

            cursor.execute(sql, params)
            return cursor.fetchall()


# 2. LLM EXTRACTION FUNCTION (UPDATED TO QWEN)
def extract_filters_with_qwen(user_input):
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        temperature=0.0,
        max_tokens=300,
        stream=False
    )

    raw_response = completion.choices[0].message.content.strip()

    # Safer JSON extraction
    if "```" in raw_response:
        raw_response = raw_response.split("```")[1]

    return json.loads(raw_response)



# 3. MAIN CHATBOT AGENT (SAME FLOW)
def textile_chatbot_agent(user_input):

    # --- STAGE 1: EXTRACTION ---
    extracted_filters = extract_filters_with_qwen(user_input)

    # --- STAGE 2: SEARCH ---
    search_term = extracted_filters.get("search_text") or user_input
    rows = get_hybrid_context(search_term, extracted_filters)
    return generate_user_response(user_input, rows)

    # --- STAGE 3: RESPONSE ---
def format_response(rows, filters):
    if not rows:
        return "❌ No fabrics found matching your criteria."

    # COUNT ONLY
    if filters.get("count_only"):
        return f"📊 Total fabrics found: {rows[0][0]}"

    # MULTIPLE RESULTS
    if filters.get("return_all") or filters.get("limit"):
        styles = []
        for r in rows:
            styles.append(
                f"• **{r[0]}** — {r[1]} weave | {r[2]} PPI | {r[3]} oz"
            )
        return "### 🔎 Matching Fabrics\n\n" + "\n".join(styles)

    # DEFAULT: BEST MATCH
    top = rows[0]

    return f"""
### 🎯 Best Matching Fabric

**Style:** {top[0]}  
**Weave:** {top[1]}  
**PPI:** {top[2]}  
**Weight:** {top[3]} oz  

This fabric closely matches your search criteria based on structural and semantic similarity.
"""
    
def generate_user_response(user_input, rows):
    # Convert DB rows to readable structured text
    if not rows:
        results_text = "No matching fabrics were found."
    else:
        results_text = "\n".join(
            [f"Style: {r[0]}, Weave: {r[1]}, PPI: {r[2]}, Weight: {r[3]} oz"
             for r in rows]
        )

    prompt = RESPONSE_PROMPT.format(
        user_query=user_input,
        results=results_text
    )

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "You generate polished textile fabric answers."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=500
    )

    return completion.choices[0].message.content.strip()

def textile_chatbot_agent(user_input):

    # Stage 1: Extract filters
    extracted_filters = extract_filters_with_qwen(user_input)

    # Stage 2: Search
    search_term = extracted_filters.get("search_text") or user_input
    rows = get_hybrid_context(search_term, extracted_filters)

    # Stage 3: LLM Response Generation
    return generate_user_response(user_input, rows)
# Example Usage

if st.button("Run", type="primary", use_container_width=True) and q.strip():    
    botresponse = textile_chatbot_agent(q.strip())
    st.write(botresponse)
    print(botresponse)
