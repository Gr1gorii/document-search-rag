import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STOP_WORDS = set(
    "a an and are as at be by can do does for from how i in is it of on or that the "
    "this to was what when where which why with you your using use fastapi please "
    "explain tell me about would should my".split()
)


def tokenize(text: str) -> list[str]:
    return [word for word in re.findall(r"[\w]+", text.lower()) if word not in STOP_WORDS]


@dataclass(frozen=True)
class Chunk:
    id: str
    page: str
    title: str
    section: str
    url: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self.chunk), "score": round(self.score, 3)}


def query_coverage(question: str, hits: list[Hit]) -> float:
    query = set(tokenize(question))
    evidence = set(
        tokenize(
            " ".join(f"{hit.chunk.title} {hit.chunk.section} {hit.chunk.text}" for hit in hits)
        )
    )
    return len(query & evidence) / len(query) if query else 0.0


class SearchIndex:
    """BM25 keeps this small corpus searchable without an embedding service."""

    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Corpus is empty; run scripts/build_corpus.py")
        self.chunks = chunks
        self.terms = [Counter(tokenize(f"{c.title} {c.section} {c.text}")) for c in chunks]
        self.lengths = [sum(counts.values()) for counts in self.terms]
        self.average_length = sum(self.lengths) / len(chunks)
        document_counts: Counter[str] = Counter()
        for counts in self.terms:
            document_counts.update(counts.keys())
        self.idf = {
            word: math.log(1 + (len(chunks) - count + 0.5) / (count + 0.5))
            for word, count in document_counts.items()
        }

    @classmethod
    def load(cls, path: Path) -> "SearchIndex":
        return cls([Chunk(**item) for item in json.loads(path.read_text(encoding="utf-8"))])

    def search(self, question: str, top_k: int = 4) -> list[Hit]:
        query = sorted(set(tokenize(question)))
        hits = []
        for chunk, counts, length in zip(self.chunks, self.terms, self.lengths, strict=True):
            score = 0.0
            for word in query:
                frequency = counts[word]
                if frequency:
                    normalizer = frequency + 1.5 * (0.25 + 0.75 * length / self.average_length)
                    score += self.idf[word] * frequency * 2.5 / normalizer
            if score:
                hits.append(Hit(chunk, score))
        return sorted(hits, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]
