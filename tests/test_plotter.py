"""Tests for promptplot/plotter.py — SimulatedPlotter, Dispatcher, BasePlotter."""

import pytest
import asyncio
from promptplot.plotter import (
    SimulatedPlotter, BasePlotter, Dispatcher, PlotterStatus,
)
from promptplot.models import GCodeCommand, GCodeProgram


class TestPlotterStatus:
    def test_defaults(self):
        status = PlotterStatus()
        assert status.is_busy is False
        assert status.current_command is None
        assert status.last_error is None


class TestSimulatedPlotter:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        p = SimulatedPlotter()
        assert not p.is_connected
        await p.connect()
        assert p.is_connected
        await p.disconnect()
        assert not p.is_connected

    @pytest.mark.asyncio
    async def test_send_command(self):
        p = SimulatedPlotter(command_delay=0)
        await p.connect()
        ok = await p.send_command("G1 X10 Y10 F2000")
        assert ok is True
        assert "G1 X10 Y10 F2000" in p.collected
        await p.disconnect()

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        p = SimulatedPlotter(command_delay=0)
        ok = await p.send_command("G1 X10 Y10 F2000")
        assert ok is False

    @pytest.mark.asyncio
    async def test_get_history(self):
        p = SimulatedPlotter(command_delay=0)
        await p.connect()
        await p.send_command("M5")
        await p.send_command("G0 X10 Y10")
        await p.send_command("M3 S1000")
        assert len(p.collected) == 3
        await p.disconnect()

    @pytest.mark.asyncio
    async def test_pen_state_tracking(self):
        p = SimulatedPlotter(command_delay=0)
        await p.connect()
        assert p.pen_down is False
        await p.send_command("M3 S1000")
        assert p.pen_down is True
        await p.send_command("M5")
        assert p.pen_down is False
        await p.disconnect()

    @pytest.mark.asyncio
    async def test_position_tracking(self):
        p = SimulatedPlotter(command_delay=0)
        await p.connect()
        await p.send_command("G0 X50 Y100")
        assert p.position == (50.0, 100.0)
        await p.disconnect()

    @pytest.mark.asyncio
    async def test_lines_collected(self):
        p = SimulatedPlotter(command_delay=0)
        await p.connect()
        await p.send_command("M3 S1000")
        await p.send_command("G1 X50 Y50 F2000")
        assert len(p.lines) == 1
        x0, y0, x1, y1, is_draw = p.lines[0]
        assert x1 == 50.0 and y1 == 50.0
        assert is_draw is True
        await p.disconnect()

    @pytest.mark.asyncio
    async def test_stream_program(self):
        p = SimulatedPlotter(command_delay=0)
        cmds = [
            GCodeCommand(command="M5"),
            GCodeCommand(command="G0", x=10, y=10),
            GCodeCommand(command="M3", s=1000),
            GCodeCommand(command="G1", x=50, y=50, f=2000),
            GCodeCommand(command="M5"),
        ]
        prog = GCodeProgram(commands=cmds)
        async with p:
            success, errors = await p.stream_program(prog)
        assert success == 5
        assert errors == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        p = SimulatedPlotter(command_delay=0)
        async with p:
            assert p.is_connected
        assert not p.is_connected


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_add_and_get_command(self):
        d = Dispatcher(max_buffer_size=5, command_delay=0)
        ok = await d.add_command("G0 X10 Y10")
        assert ok is True
        cmd = await d.get_next_command()
        assert cmd == "G0 X10 Y10"

    @pytest.mark.asyncio
    async def test_buffer_full(self):
        d = Dispatcher(max_buffer_size=2, command_delay=0)
        await d.add_command("cmd1")
        await d.add_command("cmd2")
        assert d.is_buffer_full()

    @pytest.mark.asyncio
    async def test_empty_queue_returns_none(self):
        d = Dispatcher()
        cmd = await d.get_next_command()
        assert cmd is None

    def test_stop(self):
        d = Dispatcher()
        d._active = True
        d.stop()
        assert d._active is False


class TestBasePlotter:
    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BasePlotter()
