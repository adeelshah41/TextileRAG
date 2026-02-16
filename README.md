<<<<<<< HEAD
# TextileRAG
=======
# SM Denim Fabric Assistant (Oracle 23ai + Hybrid Vector + Text-to-SQL)

## Setup
1) Create a venv and install:
   pip install -r requirements.txt

2) Copy .env.example to .env and fill values.

3) Make sure Oracle DB is reachable and fabric_specs exists.

4) (Recommended) Install and run Ollama for free local LLM:
   - Install Ollama
   - ollama pull llama3.1:8b
   - ollama serve

## Run
streamlit run app.py

## Notes
- The app uses sentence-transformers/all-MiniLM-L6-v2 to embed the user question into 384 dims.
- Vector search uses VECTOR_DISTANCE(style_embedding, TO_VECTOR(:json_vec)).
  If your Oracle build uses a different function name, adjust in retrieval/vector_search.py.


>>>>>>> 0458e50 (Initial commit: SM RAG Project)
