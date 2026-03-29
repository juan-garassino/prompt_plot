"""Tests for plotter connection state machine."""

import pytest
import asyncio

from promptplot.plotter import (
    ConnectionState, ConnectionStateError, PlotterStateMachine,
    SimulatedPlotter, VALID_CONNECTION_TRANSITIONS,
)


class TestPlotterStateMachine:
    def test_initial_disconnected(self):
        sm = PlotterStateMachine()
        assert sm.state == ConnectionState.DISCONNECTED
        assert not sm.is_connected
        assert not sm.can_send

    def test_connect_transitions(self):
        sm = PlotterStateMachine()
        sm.transition(ConnectionState.CONNECTING)
        assert sm.state == ConnectionState.CONNECTING
        sm.transition(ConnectionState.IDLE)
        assert sm.state == ConnectionState.IDLE
        assert sm.is_connected
        assert sm.can_send

    def test_invalid_transition_raises(self):
        sm = PlotterStateMachine()
        with pytest.raises(ConnectionStateError) as exc_info:
            sm.transition(ConnectionState.STREAMING)
        assert exc_info.value.current == ConnectionState.DISCONNECTED
        assert exc_info.value.target == ConnectionState.STREAMING

    def test_streaming_to_alarm(self):
        sm = PlotterStateMachine()
        sm.transition(ConnectionState.CONNECTING)
        sm.transition(ConnectionState.IDLE)
        sm.transition(ConnectionState.STREAMING)
        sm.transition(ConnectionState.ALARM)
        assert sm.state == ConnectionState.ALARM
        assert not sm.can_send

    def test_recovery_to_idle(self):
        sm = PlotterStateMachine()
        sm.transition(ConnectionState.CONNECTING)
        sm.transition(ConnectionState.IDLE)
        sm.transition(ConnectionState.STREAMING)
        sm.transition(ConnectionState.ALARM)
        sm.transition(ConnectionState.RECOVERY)
        sm.transition(ConnectionState.IDLE)
        assert sm.state == ConnectionState.IDLE

    def test_pause_resume(self):
        sm = PlotterStateMachine()
        sm.transition(ConnectionState.CONNECTING)
        sm.transition(ConnectionState.IDLE)
        sm.transition(ConnectionState.STREAMING)
        sm.transition(ConnectionState.PAUSED)
        assert sm.state == ConnectionState.PAUSED
        assert sm.is_connected
        assert not sm.can_send
        sm.transition(ConnectionState.STREAMING)
        assert sm.can_send

    def test_on_change_listener(self):
        sm = PlotterStateMachine()
        changes = []
        sm.on_change(lambda old, new: changes.append((old, new)))
        sm.transition(ConnectionState.CONNECTING)
        sm.transition(ConnectionState.IDLE)
        assert len(changes) == 2
        assert changes[0] == (ConnectionState.DISCONNECTED, ConnectionState.CONNECTING)
        assert changes[1] == (ConnectionState.CONNECTING, ConnectionState.IDLE)

    def test_can_send_states(self):
        """Only IDLE and STREAMING allow sending commands."""
        sm = PlotterStateMachine()
        assert not sm.can_send  # DISCONNECTED
        sm.transition(ConnectionState.CONNECTING)
        assert not sm.can_send  # CONNECTING
        sm.transition(ConnectionState.IDLE)
        assert sm.can_send  # IDLE
        sm.transition(ConnectionState.STREAMING)
        assert sm.can_send  # STREAMING

    def test_is_connected_states(self):
        """IDLE, STREAMING, PAUSED, RECOVERY are connected."""
        sm = PlotterStateMachine()
        assert not sm.is_connected
        sm.transition(ConnectionState.CONNECTING)
        assert not sm.is_connected
        sm.transition(ConnectionState.IDLE)
        assert sm.is_connected


class TestSimulatedPlotterConnectionState:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        p = SimulatedPlotter(command_delay=0)
        assert p.connection_state == ConnectionState.DISCONNECTED
        assert not p.is_connected

        await p.connect()
        assert p.connection_state == ConnectionState.IDLE
        assert p.is_connected

        ok = await p.send_command("M5")
        assert ok

        await p.disconnect()
        assert p.connection_state == ConnectionState.DISCONNECTED
        assert not p.is_connected

    @pytest.mark.asyncio
    async def test_backward_compat_active(self):
        p = SimulatedPlotter(command_delay=0)
        assert not p._active
        await p.connect()
        assert p._active
        await p.disconnect()
        assert not p._active
