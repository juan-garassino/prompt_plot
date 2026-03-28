"""
Drawing memory for PromptPlot v3.0

Stores successful generations with their prompts, GCode, and quality scores.
Finds similar past drawings to use as few-shot examples for new prompts.
"""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class MemoryEntry:
    """A stored drawing with its prompt, GCode, and quality score."""
    prompt: str
    gcode: str
    grade: str
    canvas_utilization: float
    draw_travel_ratio: float
    command_count: int
    timestamp: float

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
        )


class DrawingMemory:
    """Persistent memory of successful drawings for few-shot learning."""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".promptplot" / "memory"
        self.storage_path = Path(storage_path)
        self.storage_file = self.storage_path / "drawings.jsonl"

    def _ensure_dir(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, prompt: str, gcode: str, grade: str = "C",
             canvas_utilization: float = 0.0, draw_travel_ratio: float = 0.0,
             command_count: int = 0) -> MemoryEntry:
        """Save a successful drawing to memory."""
        self._ensure_dir()
        entry = MemoryEntry(
            prompt=prompt,
            gcode=gcode,
            grade=grade,
            canvas_utilization=canvas_utilization,
            draw_travel_ratio=draw_travel_ratio,
            command_count=command_count,
            timestamp=time.time(),
        )
        with open(self.storage_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def load_all(self) -> List[MemoryEntry]:
        """Load all entries from memory."""
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

    def find_similar(self, prompt: str, top_k: int = 1) -> List[MemoryEntry]:
        """Find the most similar past drawings by keyword overlap."""
        entries = self.load_all()
        if not entries:
            return []

        prompt_words = set(prompt.lower().split())
        scored = []
        for entry in entries:
            sim = self._compute_similarity(prompt_words, entry.prompt)
            scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for sim, entry in scored[:top_k] if sim > 0.0]

    def _compute_similarity(self, prompt_words: set, stored_prompt: str) -> float:
        """Jaccard similarity on tokenized words."""
        stored_words = set(stored_prompt.lower().split())
        if not prompt_words or not stored_words:
            return 0.0
        intersection = prompt_words & stored_words
        union = prompt_words | stored_words
        return len(intersection) / len(union) if union else 0.0
