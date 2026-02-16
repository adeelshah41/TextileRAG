from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer
from core.logger import get_logger

log = get_logger("retrieval.embedder")


class QueryEmbedder:
    def __init__(self) -> None:
        # Produces 384-d vectors
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def embed(self, text: str) -> list[float]:
        v = self.model.encode([text], normalize_embeddings=True)[0]
        v = np.asarray(v, dtype=np.float32)
        return v.tolist()


embedder = QueryEmbedder()
