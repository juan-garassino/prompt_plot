"""
Drawing memory for PromptPlot v3.0

Stores successful generations with their prompts, GCode, and quality scores.
Finds similar past drawings via OpenAI embeddings (cosine), falling back to
Jaccard if no embedding provider is available.
"""

import json
import os
import time
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Any


@dataclass
class MemoryEntry:
    prompt: str
    gcode: str
    grade: str
    canvas_utilization: float
    draw_travel_ratio: float
    command_count: int
    timestamp: float
    creative_mode: str = "figurative"
    figurative_score: float = 0.0
    abstract_score: float = 0.0
    embedding: Optional[List[float]] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            prompt=data["prompt"],
            gcode=data["gcode"],
            grade=data.get("grade", "C"),
            canvas_utilization=data.get("canvas_utilization", 0.0),
            draw_travel_ratio=data.get("draw_travel_ratio", 0.0),
            command_count=data.get("command_count", 0),
            timestamp=data.get("timestamp", 0.0),
            creative_mode=data.get("creative_mode", "figurative"),
            figurative_score=data.get("figurative_score", 0.0),
            abstract_score=data.get("abstract_score", 0.0),
            embedding=data.get("embedding"),
        )


def embed_prompt(provider: Any, text: str) -> Optional[List[float]]:
    """Embed text via OpenAI text-embedding-3-small. Returns None on failure."""
    api_key = None
    if provider is not None:
        api_key = getattr(provider, "api_key", None)
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai as _openai
        client = _openai.OpenAI(api_key=api_key)
        resp = client.embeddings.create(model="text-embedding-3-small", input=text)
        return list(resp.data[0].embedding)
    except Exception:
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DrawingMemory:
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".promptplot" / "memory"
        self.storage_path = Path(storage_path)
        self.storage_file = self.storage_path / "drawings.jsonl"

    def _ensure_dir(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, prompt: str, gcode: str, grade: str = "C",
             canvas_utilization: float = 0.0, draw_travel_ratio: float = 0.0,
             command_count: int = 0, creative_mode: str = "figurative",
             figurative_score: float = 0.0, abstract_score: float = 0.0,
             provider: Any = None) -> MemoryEntry:
        self._ensure_dir()
        embedding = embed_prompt(provider, prompt) if provider is not None else None
        entry = MemoryEntry(
            prompt=prompt,
            gcode=gcode,
            grade=grade,
            canvas_utilization=canvas_utilization,
            draw_travel_ratio=draw_travel_ratio,
            command_count=command_count,
            timestamp=time.time(),
            creative_mode=creative_mode,
            figurative_score=figurative_score,
            abstract_score=abstract_score,
            embedding=embedding,
        )
        with open(self.storage_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def load_all(self) -> List[MemoryEntry]:
        if not self.storage_file.exists():
            return []
        entries = []
        with open(self.storage_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(MemoryEntry.from_dict(data))
                except (json.JSONDecodeError, KeyError):
                    continue
        return entries

    def find_similar(self, prompt: str, top_k: int = 1, creative_mode: Optional[str] = None) -> List[MemoryEntry]:
        """Jaccard-based similarity (fallback path, no network needed)."""
        entries = self.load_all()
        if not entries:
            return []
        if creative_mode is not None:
            entries = [e for e in entries if e.creative_mode == creative_mode]
            if not entries:
                return []
        prompt_words = set(prompt.lower().split())
        scored = []
        for entry in entries:
            sim = self._compute_similarity(prompt_words, entry.prompt)
            scored.append((sim, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for sim, entry in scored[:top_k] if sim > 0.0]

    def find_similar_semantic(
        self,
        prompt: str,
        top_k: int = 1,
        provider: Any = None,
        creative_mode: Optional[str] = None,
    ) -> List[MemoryEntry]:
        """Embedding-based retrieval; falls back to Jaccard if no embedding."""
        query_emb = embed_prompt(provider, prompt)
        if query_emb is None:
            return self.find_similar(prompt, top_k=top_k, creative_mode=creative_mode)

        entries = self.load_all()
        if not entries:
            return []
        if creative_mode is not None:
            entries = [e for e in entries if e.creative_mode == creative_mode]
            if not entries:
                return []

        scored = []
        for entry in entries:
            emb = entry.embedding
            if emb is None:
                emb = embed_prompt(provider, entry.prompt)
                if emb is not None:
                    entry.embedding = emb
            if emb is None:
                continue
            scored.append((_cosine(query_emb, emb), entry))

        if not scored:
            return self.find_similar(prompt, top_k=top_k, creative_mode=creative_mode)

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for sim, entry in scored[:top_k] if sim > 0.0]

    def _compute_similarity(self, prompt_words: set, stored_prompt: str) -> float:
        stored_words = set(stored_prompt.lower().split())
        if not prompt_words or not stored_words:
            return 0.0
        intersection = prompt_words & stored_words
        union = prompt_words | stored_words
        return len(intersection) / len(union) if union else 0.0
