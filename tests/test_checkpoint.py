"""Tests for CheckpointManager and DrawingSession checkpoint/restore."""

import pytest
from pathlib import Path

from promptplot.checkpoint import CheckpointManager
from promptplot.engine import DrawingSession, PenState, Phase
from promptplot.config import PromptPlotConfig


class TestCheckpointManager:
    def test_save_and_load(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        data = {"prompt": "draw a circle", "command_index": 42, "sent": 10}
        path = mgr.save(data)
        assert path.exists()

        loaded = mgr.load("draw a circle")
        assert loaded is not None
        assert loaded["command_index"] == 42
        assert loaded["sent"] == 10

    def test_load_nonexistent_returns_none(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        assert mgr.load("nonexistent prompt") is None

    def test_delete(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        mgr.save({"prompt": "test", "data": 123})
        assert mgr.load("test") is not None
        mgr.delete("test")
        assert mgr.load("test") is None

    def test_list_checkpoints(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        mgr.save({"prompt": "circle", "command_index": 10, "sent": 5})
        mgr.save({"prompt": "square", "command_index": 20, "sent": 15})
        checkpoints = mgr.list_checkpoints()
        assert len(checkpoints) == 2
        prompts = {c["prompt"] for c in checkpoints}
        assert "circle" in prompts
        assert "square" in prompts

    def test_list_empty(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        assert mgr.list_checkpoints() == []

    def test_checkpoint_id_stability(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        id1 = mgr._checkpoint_id("draw a circle")
        id2 = mgr._checkpoint_id("draw a circle")
        assert id1 == id2
        assert len(id1) == 16

    def test_overwrite_checkpoint(self, tmp_path):
        mgr = CheckpointManager(checkpoint_dir=tmp_path)
        mgr.save({"prompt": "test", "command_index": 5})
        mgr.save({"prompt": "test", "command_index": 15})
        loaded = mgr.load("test")
        assert loaded["command_index"] == 15


class TestDrawingSessionCheckpoint:
    def test_session_checkpoint(self):
        session = DrawingSession(PromptPlotConfig())
        session.prompt = "spiral"
        session.mode = "batch"
        session.set_phase(Phase.GENERATING)
        session.sent = 42

        pen_state = PenState(initial="down")
        cp = session.checkpoint(25, pen_state, (100.0, 50.0))

        assert cp["prompt"] == "spiral"
        assert cp["command_index"] == 25
        assert cp["pen_state"] == {"state": "down"}
        assert cp["position"] == [100.0, 50.0]
        assert cp["sent"] == 42

    def test_session_restore(self):
        session = DrawingSession(PromptPlotConfig())
        data = {
            "prompt": "spiral",
            "mode": "batch",
            "phase": "streaming",
            "command_index": 25,
            "pen_state": {"state": "down"},
            "position": [100.0, 50.0],
            "sent": 42,
            "errors": 2,
            "skipped": 1,
            "elapsed": 5.5,
            "grade": "B",
        }
        info = session.restore_checkpoint(data)
        assert session.prompt == "spiral"
        assert session.sent == 42
        assert session.errors == 2
        assert session.phase == "streaming"
        assert info["command_index"] == 25
        assert info["pen_state"].is_down
        assert info["position"] == (100.0, 50.0)
