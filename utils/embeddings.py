import os
from typing import Iterable, List

from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EMBEDDING_DIMENSION = 384


class LocalEmbedder:
    """Generate normalized embeddings locally with one shared model."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        vectors = self.model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()