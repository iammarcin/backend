"""BM25 sparse vector provider for hybrid search."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Use a large prime for hash space to minimize collisions
# Qdrant sparse vectors use uint32 indices (max ~4 billion)
HASH_SPACE = 2**31 - 1  # Large prime-ish number


class BM25SparseVectorProvider:
    """Generate BM25 sparse vectors for keyword-based search.

    Uses hash-based token IDs to ensure consistency between indexing and search.
    The same word will always produce the same token ID regardless of when
    it's encountered.

    Sparse vectors are represented as:
    {
        "indices": [token_id_1, token_id_2, ...],
        "values": [score_1, score_2, ...]
    }

    Where scores are BM25 weights for each token.
    """

    def __init__(
        self,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> None:
        """Initialize BM25 provider.

        Args:
            k1: Controls term frequency saturation (typical: 1.2-2.0)
            b: Controls document length normalization (typical: 0.75)
        """
        self.k1 = k1
        self.b = b

    def tokenize(self, text: str) -> list[str]:
        """Simple tokenization - lowercase and split on word boundaries."""
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens

    def get_token_id(self, token: str) -> int:
        """Get deterministic token ID using hash.

        This ensures the same word always gets the same ID,
        regardless of indexing order or instance.
        """
        # Use Python's built-in hash, constrained to positive int32 range
        return abs(hash(token)) % HASH_SPACE

    def generate(self, text: str) -> dict[str, Any]:
        """Generate sparse vector for text using BM25.

        Returns:
            Sparse vector in Qdrant format:
            {
                "indices": [token_id, ...],
                "values": [bm25_score, ...]
            }
        """
        tokens = self.tokenize(text)

        if not tokens:
            return {"indices": [], "values": []}

        # Count term frequencies
        term_freq = Counter(tokens)
        doc_length = len(tokens)

        # For single document BM25, we simplify:
        # - IDF = 1.0 (Qdrant computes real IDF at search time)
        # - avgdl = doc_length (or use global average if available)
        avgdl = doc_length  # Simplified for now

        # Compute BM25 scores
        indices = []
        values = []

        for token, freq in term_freq.items():
            token_id = self.get_token_id(token)

            # BM25 score (simplified without IDF, Qdrant adds it)
            score = (freq * (self.k1 + 1)) / (
                freq + self.k1 * (1 - self.b + self.b * (doc_length / avgdl))
            )

            indices.append(token_id)
            values.append(score)

        return {
            "indices": indices,
            "values": values,
        }

    async def generate_async(self, text: str) -> dict[str, Any]:
        """Async wrapper for generate (for consistency with dense provider)."""
        return self.generate(text)


__all__ = ["BM25SparseVectorProvider"]
