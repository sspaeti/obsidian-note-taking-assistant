"""Embedding generation using sentence-transformers."""
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Optional
from tqdm import tqdm


class EmbeddingGenerator:
    """Wrapper for sentence-transformers embedding model."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize with sentence-transformers model.

        all-MiniLM-L6-v2 produces 384-dimensional vectors.
        It's fast, lightweight, and good for semantic similarity.
        """
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.dimension}")

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 64,
        show_progress: bool = True
    ) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (64 for CPU, 128+ for GPU)
            show_progress: Show tqdm progress bar

        Returns:
            List of numpy arrays (384-dimensional each)
        """
        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        iterator = range(0, len(texts), batch_size)
        if show_progress:
            iterator = tqdm(iterator, total=total_batches, desc="Generating embeddings")

        for i in iterator:
            batch = texts[i:i + batch_size]
            batch_embeddings = self.model.encode(
                batch,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            embeddings.extend(batch_embeddings)

        return embeddings

    @staticmethod
    def prepare_chunk_for_embedding(
        chunk_content: str,
        heading_context: Optional[str] = None,
        note_title: Optional[str] = None
    ) -> str:
        """
        Prepare chunk text for embedding with context.

        Adding title and heading context improves retrieval quality
        by providing semantic anchors for the chunk content.
        """
        parts = []
        if note_title:
            parts.append(f"Title: {note_title}")
        if heading_context:
            # Clean the heading (remove # symbols)
            clean_heading = heading_context.lstrip('#').strip()
            parts.append(f"Section: {clean_heading}")
        parts.append(chunk_content)
        return " | ".join(parts)
