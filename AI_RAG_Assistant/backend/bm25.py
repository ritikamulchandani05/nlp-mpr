"""Keyword search over a session's chunks using BM25."""
import re

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"\w+")


def tokenize(text):
    return _TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, ids, texts):
        self.ids = list(ids)
        self.texts = list(texts)
        self._bm25 = BM25Okapi([tokenize(t) or [""] for t in self.texts]) if self.texts else None

    def search(self, query, k):
        """Return up to k (chunk_id, score) pairs with a positive score."""
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.ids[i], float(scores[i])) for i in order if scores[i] > 0]
