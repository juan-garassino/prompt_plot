"""
Checkpoint manager for resumable drawings in PromptPlot v3.0

Saves/loads drawing state so interrupted drawings can be resumed.
Checkpoints are stored as JSON files in ~/.promptplot/checkpoints/.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict

_log = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint files for resumable drawings."""

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        if checkpoint_dir is None:
            checkpoint_dir = Path.home() / ".promptplot" / "checkpoints"
        self.checkpoint_dir = checkpoint_dir

    def _checkpoint_id(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def _ensure_dir(self):
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: dict) -> Path:
        """Save a checkpoint. data must contain 'prompt'."""
        self._ensure_dir()
        prompt = data.get("prompt", "")
        cid = self._checkpoint_id(prompt)
        path = self.checkpoint_dir / f"{cid}.json"
        path.write_text(json.dumps(data, indent=2))
        _log.info("Checkpoint saved: %s", path)
        return path

    def load(self, prompt: str) -> Optional[dict]:
        """Load a checkpoint for the given prompt. Returns None if not found."""
        cid = self._checkpoint_id(prompt)
        path = self.checkpoint_dir / f"{cid}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            _log.warning("Failed to load checkpoint %s: %s", path, e)
            return None

    def delete(self, prompt: str) -> None:
        """Delete a checkpoint for the given prompt."""
        cid = self._checkpoint_id(prompt)
        path = self.checkpoint_dir / f"{cid}.json"
        if path.exists():
            path.unlink()
            _log.info("Checkpoint deleted: %s", path)

    def list_checkpoints(self) -> List[Dict]:
        """List all saved checkpoints with summary info."""
        if not self.checkpoint_dir.exists():
            return []
        results = []
        for path in sorted(self.checkpoint_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                results.append({
                    "file": str(path),
                    "prompt": data.get("prompt", ""),
                    "command_index": data.get("command_index", 0),
                    "sent": data.get("sent", 0),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return results
