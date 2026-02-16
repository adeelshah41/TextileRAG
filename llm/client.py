from __future__ import annotations

import requests
from core.config import settings
from core.logger import get_logger

log = get_logger("llm.client")


class LLMClient:
    def generate(self, system: str, user: str) -> str:
        if settings.llm_provider == "ollama":
            return self._ollama(system, user)
        if settings.llm_provider == "openai_compat":
            return self._openai_compat(system, user)
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")

    def _ollama(self, system: str, user: str) -> str:
        base = settings.ollama_host.rstrip("/")

        # sanity check: is it ollama?
        try:
            tags = requests.get(f"{base}/api/tags", timeout=10)
            tags.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {base}. "
                f"Make sure 'ollama serve' is running. Underlying error: {e}"
            )

        # Try /api/chat first
        chat_url = f"{base}/api/chat"
        payload_chat = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }

        r = requests.post(chat_url, json=payload_chat, timeout=120)
        if r.status_code == 404:
            # Fallback to /api/generate
            gen_url = f"{base}/api/generate"
            prompt = f"<<SYS>>\n{system}\n<</SYS>>\n\n{user}"
            payload_gen = {
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            }
            r2 = requests.post(gen_url, json=payload_gen, timeout=120)
            r2.raise_for_status()
            data2 = r2.json()
            return data2.get("response", "").strip()

        r.raise_for_status()
        data = r.json()
        return data["message"]["content"].strip()

    def _openai_compat(self, system: str, user: str) -> str:
        if not settings.openai_compat_api_key:
            raise RuntimeError("OPENAI_COMPAT_API_KEY is missing in .env")

        base = settings.openai_compat_base_url.rstrip("/")
        url = f"{base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.openai_compat_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openai_compat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }

        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code == 404:
            raise RuntimeError(
                f"404 from LLM endpoint. For Groq, base URL must be "
                f"https://api.groq.com/openai/v1 (NOT https://api.groq.com/v1). "
                f"Current: {base}"
            )
        if not r.ok:
            raise RuntimeError(f"Groq error {r.status_code}: {r.text}")
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()



llm = LLMClient()
