"""Studio design loop: stub-provider round-trip (no keys, no network).

House stub style (no Mock/MagicMock): a fake provider with a scripted reply
queue, recording calls on self.calls.
"""

import json

import pytest

from promptplot.studio.loop import run_design_loop


class _StubProvider:
    provider_name = "stub"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def acomplete(self, prompt):
        self.calls.append(("text", prompt[:80]))
        return self.replies.pop(0)

    async def acomplete_multimodal(self, prompt, image_paths=None):
        self.calls.append(("vision", [str(p) for p in (image_paths or [])]))
        return self.replies.pop(0)


DESIGN = json.dumps(
    {
        "concept": "truchet as a calm field",
        "payload": {"panels": [{"generator": "truchet", "seed": 8, "params": {}}], "title": "T"},
    }
)
CRITIQUE = json.dumps(
    {
        "scores": {
            "hierarchy": 8, "grid_alignment": 9, "tension_asymmetry": 8,
            "negative_space": 8, "pen_craft": 9, "concept_legibility": 8,
            "depth_dimensionality": 8,
        },
        "verdict": "pass",
        "top_fixes": [],
        "one_line": "clean",
    }
)
SYNTH = json.dumps({"done": True, "instruction": ""})


async def test_params_mode_one_round(tmp_path):
    provider = _StubProvider([DESIGN, CRITIQUE, SYNTH])
    res = await run_design_loop(
        "cnn", provider, mode="params", rounds=3, out_dir=tmp_path / "cnn"
    )
    assert len(res.rounds) == 1  # passed + done on round 1
    r = res.rounds[0]
    assert r.verdict == "pass"
    assert r.render_path is not None and r.render_path.exists()
    assert (tmp_path / "cnn" / "rounds" / "r01" / "payload.json").exists()
    assert (tmp_path / "cnn" / "rounds" / "r01" / "critique.json").exists()
    assert (tmp_path / "cnn" / "final" / "PROPOSAL.md").exists()
    # vision critic got the render
    kinds = [k for k, _ in provider.calls]
    assert kinds == ["text", "vision", "text"]


async def test_bad_designer_json_recovers(tmp_path):
    provider = _StubProvider(["not json at all", DESIGN, CRITIQUE, SYNTH])
    res = await run_design_loop(
        "cnn", provider, mode="params", rounds=2, out_dir=tmp_path / "cnn2"
    )
    assert len(res.rounds) == 2
    assert res.rounds[0].verdict == "fail"
    assert res.rounds[1].verdict == "pass"


async def test_render_failure_feeds_back(tmp_path):
    bad = json.dumps({"concept": "x", "payload": {"panels": [{"generator": "no_such_piece", "seed": 1}]}})
    provider = _StubProvider([bad, DESIGN, CRITIQUE, SYNTH])
    res = await run_design_loop(
        "cnn", provider, mode="params", rounds=2, out_dir=tmp_path / "cnn3"
    )
    assert res.rounds[0].verdict == "fail"
    assert "render failed" in res.rounds[0].instruction
    assert res.rounds[1].verdict == "pass"
