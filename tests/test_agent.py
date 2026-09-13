"""PromptPlot Agent (promptplot/agent/): loop, protocol, toolbox, session.

House stub style: hand-rolled stub provider with a scripted reply queue,
no Mock/MagicMock. No LLM keys, no hardware, no matplotlib windows.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from promptplot.agent.loop import run_turns
from promptplot.agent.protocol import build_system_prompt, parse_reply
from promptplot.agent.session import AgentSession
from promptplot.agent.tools import TOOLBOX, ToolContext, dispatch, get_tool
from promptplot.config import PromptPlotConfig
from promptplot.llm.base import LLMProvider


class _StubProvider(LLMProvider):
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    @property
    def provider_name(self) -> str:
        return "stub"

    async def acomplete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if not self.replies:
            raise AssertionError("stub reply queue exhausted")
        return self.replies.pop(0)


def _ctx(tmp_path):
    session = AgentSession("testsession", base_dir=tmp_path)
    return ToolContext(config=PromptPlotConfig(), session=session)


# -- protocol ---------------------------------------------------------------


def test_parse_reply_tool_and_final():
    kind, name, args = parse_reply('{"tool": "list_generators", "args": {}}')
    assert kind == "tool" and name == "list_generators" and args == {}
    kind, text, _ = parse_reply('{"final": "done"}')
    assert kind == "final" and text == "done"


def test_parse_reply_tolerates_fences_and_garbage():
    kind, name, _ = parse_reply(
        '```json\n{"tool": "score_gcode", "args": {"gcode_path": "x"}}\n```'
    )
    assert kind == "tool" and name == "score_gcode"
    kind, msg, _ = parse_reply("I think I should call a tool now!")
    assert kind == "error"


def test_system_prompt_lists_every_tool():
    sp = build_system_prompt(TOOLBOX)
    for t in TOOLBOX:
        assert t.name in sp


# -- toolbox ----------------------------------------------------------------


def test_toolbox_schemas_wellformed():
    names = set()
    for t in TOOLBOX:
        assert t.name not in names
        names.add(t.name)
        assert t.tier in ("safe", "confirm")
        assert isinstance(t.params, dict)
        assert t.description


def test_dispatch_unknown_tool(tmp_path):
    result = asyncio.run(dispatch(_ctx(tmp_path), "not_a_tool", {}))
    assert "error" in result and "unknown tool" in result["error"]


def test_dispatch_bad_args(tmp_path):
    result = asyncio.run(dispatch(_ctx(tmp_path), "generator_schema", {"nope": 1}))
    assert "error" in result


def test_render_generator_produces_artifacts(tmp_path):
    ctx = _ctx(tmp_path)
    result = asyncio.run(
        dispatch(ctx, "render_generator", {"name": "truchet", "seed": 8, "paper": "a5"})
    )
    assert "error" not in result, result
    assert result["score"]["grade"] in "ABCDEF"
    assert result["png_path"].endswith(".png")
    renders = ctx.session.list_renders()
    assert any(p.endswith(".png") for p in renders)
    assert any(p.endswith(".gcode") for p in renders)


def test_confirm_tier_blocked_without_approval(tmp_path):
    ctx = _ctx(tmp_path)
    tool = get_tool("list_generators")
    tool_tier = tool.tier
    try:
        tool.tier = "confirm"
        result = asyncio.run(dispatch(ctx, "list_generators", {}))
        assert "error" in result and "confirmation" in result["error"]
        ctx.yes_plot = True
        result = asyncio.run(dispatch(ctx, "list_generators", {}))
        assert "generators" in result
    finally:
        tool.tier = tool_tier


# -- loop ---------------------------------------------------------------------


def test_loop_tool_then_final(tmp_path):
    ctx = _ctx(tmp_path)
    provider = _StubProvider(
        [
            '{"tool": "list_generators", "args": {}}',
            '{"final": "there are many generators"}',
        ]
    )
    answer = asyncio.run(run_turns("what generators exist?", ctx, provider, max_turns=4))
    assert answer == "there are many generators"
    roles = [m["role"] for m in ctx.session.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert "TOOL RESULT list_generators" in ctx.session.messages[2]["content"]


def test_loop_retries_malformed_then_recovers(tmp_path):
    ctx = _ctx(tmp_path)
    provider = _StubProvider(
        [
            "sure! let me call the tool",  # garbage → protocol retry
            '{"final": "ok"}',
        ]
    )
    answer = asyncio.run(run_turns("hi", ctx, provider, max_turns=4))
    assert answer == "ok"


def test_loop_gives_up_after_repeated_garbage(tmp_path):
    ctx = _ctx(tmp_path)
    provider = _StubProvider(["nope", "still nope", "words", "more words"])
    answer = asyncio.run(run_turns("hi", ctx, provider, max_turns=8))
    assert "unparseable" in answer


# -- session ------------------------------------------------------------------


def test_session_persist_and_resume(tmp_path):
    s1 = AgentSession("resume-me", base_dir=tmp_path)
    s1.add("user", "hello")
    s1.add("assistant", "hi")
    s2 = AgentSession("resume-me", base_dir=tmp_path)
    assert s2.messages == s1.messages
    report = s2.close("final words")
    assert report.exists()
    assert "final words" in report.read_text()


# -- phase B: vision, native tools, hardware gate ------------------------------


class _VisionStub(_StubProvider):
    def __init__(self, replies, critique="VERDICT: keep"):
        super().__init__(replies)
        self.critique = critique
        self.seen_images = []

    async def acomplete_multimodal(self, prompt, image_paths=None):
        self.seen_images.extend(map(str, image_paths or []))
        return self.critique


class _NativeStub(_StubProvider):
    def __init__(self, steps):
        super().__init__([])
        self.steps = list(steps)

    async def acomplete_tools(self, system, messages, tools):
        assert any(t["function"]["name"] == "render_generator" for t in tools)
        return self.steps.pop(0)


def test_critique_render_uses_vision(tmp_path):
    ctx = _ctx(tmp_path)
    png = tmp_path / "x.png"
    png.write_bytes(b"fakepng")
    ctx.provider = _VisionStub([], critique="VERDICT: tweak\nISSUES: too sparse")
    result = asyncio.run(dispatch(ctx, "critique_render", {"png_path": str(png)}))
    assert "tweak" in result["critique"]
    assert ctx.provider.seen_images == [str(png)]


def test_loop_native_fast_path(tmp_path):
    ctx = _ctx(tmp_path)
    provider = _NativeStub(
        [
            {"tool": "list_generators", "args": {}},
            {"final": "done natively"},
        ]
    )
    answer = asyncio.run(run_turns("hi", ctx, provider, max_turns=4))
    assert answer == "done natively"


def test_stream_to_plotter_requires_confirm_and_traces_first(tmp_path):
    ctx = _ctx(tmp_path)
    render = asyncio.run(
        dispatch(ctx, "render_generator", {"name": "maze", "seed": 3, "paper": "a6"})
    )
    gcode = render["gcode_path"]

    blocked = asyncio.run(dispatch(ctx, "stream_to_plotter", {"gcode_path": gcode}))
    assert "error" in blocked and "confirmation" in blocked["error"]

    ctx.yes_plot = True
    result = asyncio.run(dispatch(ctx, "stream_to_plotter", {"gcode_path": gcode}))
    assert "error" not in result, result
    assert result["streamed_ok"] > 0


def test_save_to_library_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = _ctx(tmp_path)
    g = tmp_path / "a.gcode"
    g.write_text("G0 X0 Y0")
    blocked = asyncio.run(dispatch(ctx, "save_to_library", {"gcode_path": str(g), "name": "a"}))
    assert "error" in blocked
    ctx.approve = lambda name: True
    result = asyncio.run(dispatch(ctx, "save_to_library", {"gcode_path": str(g), "name": "a"}))
    assert result["saved"].endswith("a.gcode")


# -- phase C: MCP surface -------------------------------------------------------

mcp_sdk = pytest.importorskip("mcp", reason="mcp SDK not installed")


def test_mcp_server_lists_tools():
    from promptplot.agent import mcp_server

    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"list_generators", "render_generator", "preview_image", "stream_to_plotter"} <= names
    stream = next(t for t in tools if t.name == "stream_to_plotter")
    assert stream.annotations.destructiveHint is True
    ro = next(t for t in tools if t.name == "score_gcode")
    assert ro.annotations.readOnlyHint is True


def test_mcp_stream_requires_confirm(tmp_path, monkeypatch):
    from promptplot.agent import mcp_server

    monkeypatch.setattr(mcp_server, "_ctx", _ctx(tmp_path))
    g = tmp_path / "x.gcode"
    g.write_text("G0 X0 Y0")
    result = asyncio.run(mcp_server.stream_to_plotter(str(g), port="simulate"))
    assert result["error"]["code"] == "not_confirmed"
    assert "confirm=true" in result["error"]["remediation"]

    result = asyncio.run(mcp_server.stream_to_plotter(str(g), port="simulate", confirm=True))
    assert "error" not in result
