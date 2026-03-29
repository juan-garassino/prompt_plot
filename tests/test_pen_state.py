"""Tests for PenState first-class pen tracker."""

import pytest

from promptplot.engine import PenState, PenStateError


class TestPenState:
    def test_initial_state_is_up(self):
        ps = PenState()
        assert ps.is_up
        assert not ps.is_down
        assert ps.state == "up"

    def test_m3_transitions_to_down(self):
        ps = PenState()
        ps.process("M3 S1000")
        assert ps.is_down

    def test_m5_transitions_to_up(self):
        ps = PenState(initial="down")
        ps.process("M5")
        assert ps.is_up

    def test_g0_while_down_raises(self):
        ps = PenState(initial="down")
        with pytest.raises(PenStateError) as exc_info:
            ps.process("G0 X10 Y20")
        assert exc_info.value.current_state == "down"
        assert "G0" in exc_info.value.attempted_command

    def test_g1_while_up_raises(self):
        ps = PenState()
        with pytest.raises(PenStateError) as exc_info:
            ps.process("G1 X10 Y20 F2000")
        assert exc_info.value.current_state == "up"

    def test_process_safe_returns_false(self):
        ps = PenState()
        assert ps.process_safe("G1 X10 Y20") is False
        # State should NOT have changed
        assert ps.is_up

    def test_process_safe_returns_true(self):
        ps = PenState()
        assert ps.process_safe("M3 S1000") is True
        assert ps.is_down

    def test_m5_idempotent(self):
        ps = PenState()
        ps.process("M5")
        assert ps.is_up
        ps.process("M5")
        assert ps.is_up

    def test_m3_idempotent(self):
        ps = PenState(initial="down")
        ps.process("M3 S1000")
        assert ps.is_down

    def test_unknown_command_no_change(self):
        ps = PenState()
        ps.process("G4 P500")
        assert ps.is_up

    def test_reset(self):
        ps = PenState(initial="down")
        assert ps.is_down
        ps.reset()
        assert ps.is_up

    def test_snapshot_and_restore(self):
        ps = PenState()
        ps.process("M3 S1000")
        snap = ps.snapshot()
        assert snap == {"state": "down"}

        restored = PenState.from_snapshot(snap)
        assert restored.is_down

    def test_set_up_bypasses_validation(self):
        ps = PenState(initial="down")
        ps.set_up()
        assert ps.is_up

    def test_set_down_bypasses_validation(self):
        ps = PenState()
        ps.set_down()
        assert ps.is_down

    def test_invalid_initial_raises(self):
        with pytest.raises(ValueError):
            PenState(initial="sideways")

    def test_g0_while_up_ok(self):
        ps = PenState()
        ps.process("G0 X50 Y50")
        assert ps.is_up  # no state change

    def test_g1_while_down_ok(self):
        ps = PenState(initial="down")
        ps.process("G1 X50 Y50 F2000")
        assert ps.is_down  # no state change
