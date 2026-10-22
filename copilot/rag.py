"""Lexical retrieval (BM25) over product catalogue and brochures, with metadata filters.

Pure Python so it runs anywhere with no model download. Azure AI Search or an embedding
index can replace `search()` later; the return shape (source_id + version) stays the same.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

_TOKEN = re.compile(r"[a-z0-9]+")
_INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)|"
    r"auto-?send|send (it|this|the message) now|reveal (the )?system prompt",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chunk:
    source_id: str
    product_id: str
    version: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    flagged: bool  # True when text looks like an instruction; it is treated as data only


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def chunks_from_catalog(catalog: Iterable[dict[str, Any]], brochures: Iterable[dict[str, Any]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for item in catalog:
        exclusions = "; ".join(item["exclusions"])
        text = f"{item['name']} version {item['version']}. Coverage: {item['coverage_summary']} Exclusions: {exclusions}."
        chunks.append(Chunk(item["source_id"], item["product_id"], item["version"], text))
    for doc in brochures:
        chunks.append(Chunk(doc["source_id"], doc["product_id"], doc["version"], doc["text"]))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._docs = [Counter(tokenize(c.text)) for c in chunks]
        self._lengths = [sum(d.values()) for d in self._docs]
        self._avg = sum(self._lengths) / max(len(self._lengths), 1)
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3, product_id: str | None = None,
               version: str | None = None) -> list[Hit]:
        terms = tokenize(query)
        scored: list[tuple[float, int]] = []
        for i, doc in enumerate(self._docs):
            chunk = self.chunks[i]
            if product_id and chunk.product_id != product_id:
                continue  # metadata filter applied BEFORE ranking
            if version and chunk.version != version:
                continue
            score = 0.0
            for t in terms:
                if t not in doc:
                    continue
                tf = doc[t]
                norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self._lengths[i] / self._avg))
                score += self._idf.get(t, 0.0) * norm
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Hit(self.chunks[i], round(s, 4), bool(_INJECTION.search(self.chunks[i].text)))
            for s, i in scored[:k]
        ]
