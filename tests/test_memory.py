"""Tests for promptplot/memory.py — DrawingMemory."""

import pytest
from pathlib import Path
from promptplot.memory import DrawingMemory, MemoryEntry


@pytest.fixture
def memory(tmp_path):
    return DrawingMemory(storage_path=tmp_path / "memory")


class TestDrawingMemory:
    def test_save_creates_file(self, memory):
        memory.save("draw a cat", "M5\nG0 X10 Y10\nM3 S1000\nG1 X50 Y50 F2000\nM5", grade="B")
        assert memory.storage_file.exists()

    def test_save_and_load(self, memory):
        memory.save("draw a cat", "GCODE1", grade="A")
        memory.save("draw a dog", "GCODE2", grade="B")
        entries = memory.load_all()
        assert len(entries) == 2
        assert entries[0].prompt == "draw a cat"
        assert entries[1].prompt == "draw a dog"

    def test_find_similar_exact(self, memory):
        memory.save("draw a cat", "GCODE_CAT", grade="A")
        memory.save("draw a house", "GCODE_HOUSE", grade="B")
        results = memory.find_similar("draw a cat")
        assert len(results) == 1
        assert results[0].prompt == "draw a cat"

    def test_find_similar_partial(self, memory):
        memory.save("draw a kitten", "GCODE_KITTEN", grade="A")
        results = memory.find_similar("draw a cat")
        # "draw" and "a" overlap
        assert len(results) >= 1
        assert results[0].prompt == "draw a kitten"

    def test_find_similar_empty_memory(self, memory):
        results = memory.find_similar("draw a cat")
        assert results == []

    def test_load_empty(self, memory):
        entries = memory.load_all()
        assert entries == []

    def test_memory_entry_roundtrip(self):
        entry = MemoryEntry(
            prompt="test", gcode="G0 X0 Y0", grade="A",
            canvas_utilization=0.5, draw_travel_ratio=2.0,
            command_count=10, timestamp=1234567890.0,
        )
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.prompt == entry.prompt
        assert restored.grade == entry.grade

    def test_save_with_metrics(self, memory):
        memory.save(
            "draw a spiral", "GCODE", grade="A",
            canvas_utilization=0.7, draw_travel_ratio=3.5, command_count=50,
        )
        entries = memory.load_all()
        assert entries[0].canvas_utilization == 0.7
        assert entries[0].command_count == 50
