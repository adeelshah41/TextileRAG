import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Oracle
    oracle_user: str = os.getenv("ORACLE_USER", "")
    oracle_password: str = os.getenv("ORACLE_PASSWORD", "")
    oracle_dsn: str = os.getenv("ORACLE_DSN", "")
    oracle_schema: str = os.getenv("ORACLE_SCHEMA", "")
    oracle_table: str = os.getenv("ORACLE_TABLE", "fabric_specs")

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")  # ollama | openai_compat

    # Ollama
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # OpenAI-compatible
    openai_compat_base_url: str = os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")
    openai_compat_api_key: str = os.getenv("OPENAI_COMPAT_API_KEY", "")
    openai_compat_model: str = os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini")

    # Behavior
    default_max_rows: int = int(os.getenv("DEFAULT_MAX_ROWS", "200"))
    hard_max_rows: int = int(os.getenv("HARD_MAX_ROWS", "6000"))
    vector_top_k: int = int(os.getenv("VECTOR_TOP_K", "20"))
    sql_retry_limit: int = int(os.getenv("SQL_RETRY_LIMIT", "5"))


settings = Settings()
