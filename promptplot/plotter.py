"""
Plotter hardware abstraction for PromptPlot v3.0

Merged from:
- PromptPlot plotter/base.py: BasePlotter ABC
- PromptPlot plotter/serial_plotter.py: SerialPlotter (serial_asyncio, heartbeat)
- PromptPlot plotter/simulated.py: SimulatedPlotter (testing without hardware)
- drawStream async_controller.py: Dispatcher (bounded deque backpressure)
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple, Any, Callable, Awaitable

from .models import GCodeCommand, GCodeProgram
from .config import SerialConfig
from .engine import PenState


# ---------------------------------------------------------------------------
# Plotter Status
# ---------------------------------------------------------------------------

@dataclass
class PlotterStatus:
    is_busy: bool = False
    current_command: Optional[str] = None
    last_response: Optional[str] = None
    queue_size: int = 0
    last_update: float = field(default_factory=time.time)
    last_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Connection State Machine
# ---------------------------------------------------------------------------

class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    ALARM = "alarm"
    RECOVERY = "recovery"


VALID_CONNECTION_TRANSITIONS = {
    ConnectionState.DISCONNECTED: {ConnectionState.CONNECTING},
    ConnectionState.CONNECTING: {ConnectionState.IDLE, ConnectionState.DISCONNECTED},
    ConnectionState.IDLE: {ConnectionState.STREAMING, ConnectionState.DISCONNECTED},
    ConnectionState.STREAMING: {ConnectionState.IDLE, ConnectionState.PAUSED, ConnectionState.ALARM, ConnectionState.DISCONNECTED},
    ConnectionState.PAUSED: {ConnectionState.STREAMING, ConnectionState.IDLE, ConnectionState.DISCONNECTED},
    ConnectionState.ALARM: {ConnectionState.RECOVERY, ConnectionState.DISCONNECTED},
    ConnectionState.RECOVERY: {ConnectionState.IDLE, ConnectionState.DISCONNECTED, ConnectionState.ALARM},
}


class ConnectionStateError(Exception):
    """Raised when an invalid connection state transition is attempted."""

    def __init__(self, current: ConnectionState, target: ConnectionState):
        self.current = current
        self.target = target
        valid = VALID_CONNECTION_TRANSITIONS.get(current, set())
        super().__init__(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Valid targets: {', '.join(s.value for s in valid)}"
        )


class PlotterStateMachine:
    """Manages plotter connection state with validated transitions."""

    def __init__(self, initial: ConnectionState = ConnectionState.DISCONNECTED):
        self._state: ConnectionState = initial
        self._on_change_callbacks: List[Callable] = []

    @property
    def state(self) -> ConnectionState:
        return self._state

    def transition(self, new_state: ConnectionState) -> None:
        if new_state not in VALID_CONNECTION_TRANSITIONS.get(self._state, set()):
            raise ConnectionStateError(self._state, new_state)
        old = self._state
        self._state = new_state
        for cb in self._on_change_callbacks:
            cb(old, new_state)

    def on_change(self, callback: Callable) -> None:
        self._on_change_callbacks.append(callback)

    @property
    def is_connected(self) -> bool:
        return self._state in (
            ConnectionState.IDLE, ConnectionState.STREAMING,
            ConnectionState.PAUSED, ConnectionState.RECOVERY,
        )

    @property
    def can_send(self) -> bool:
        return self._state in (ConnectionState.IDLE, ConnectionState.STREAMING)


# ---------------------------------------------------------------------------
# Dispatcher — bounded deque backpressure (from drawStream)
# ---------------------------------------------------------------------------

class Dispatcher:
    """Command queue with bounded backpressure for serial streaming."""

    def __init__(self, max_buffer_size: int = 5, command_delay: float = 0.1):
        self.command_queue: deque = deque(maxlen=max_buffer_size)
        self.max_buffer_size = max_buffer_size
        self.command_delay = command_delay
        self._active = False

    def is_buffer_full(self) -> bool:
        return len(self.command_queue) >= self.max_buffer_size

    async def add_command(self, command: str) -> bool:
        if self.is_buffer_full():
            await asyncio.sleep(self.command_delay)
            if self.is_buffer_full():
                return False
        self.command_queue.append(command)
        return True

    async def get_next_command(self) -> Optional[str]:
        if self.command_queue:
            return self.command_queue.popleft()
        return None

    def stop(self):
        self._active = False


# ---------------------------------------------------------------------------
# BasePlotter ABC
# ---------------------------------------------------------------------------

class BasePlotter(ABC):
    """Abstract base for all plotter implementations."""

    def __init__(self, port: str = "SIMULATED", max_retries: int = 3):
        self.port = port
        self.max_retries = max_retries
        self._connection = PlotterStateMachine()
        self.logger = logging.getLogger(f"{self.__class__.__name__}({port})")
        self.command_history: List[str] = []
        self.status = PlotterStatus()

    @property
    def _active(self) -> bool:
        return self._connection.is_connected

    @_active.setter
    def _active(self, value: bool):
        # Backward compatibility — used by subclasses during connect/disconnect
        # Actual transitions are handled by the state machine methods
        pass

    @abstractmethod
    async def connect(self) -> bool:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def send_command(self, command: str) -> bool:
        ...

    async def stream_program(
        self,
        program: GCodeProgram,
        on_command: Optional[Callable[[int, int, str, bool], Awaitable[None]]] = None,
        start_index: int = 0,
    ) -> Tuple[int, int]:
        """Stream an entire program, returning (success_count, error_count).

        Args:
            program: The GCode program to stream.
            on_command: Optional async callback(index, total, gcode_str, success)
                        called after each command is sent.
            start_index: Skip commands before this index (for checkpoint resume).
        """
        success = 0
        errors = 0
        total = len(program.commands)
        for i, cmd in enumerate(program.commands):
            if i < start_index:
                continue
            gcode = cmd.to_gcode()
            if gcode == "COMPLETE":
                continue
            ok = await self.send_command(gcode)
            if ok:
                success += 1
            else:
                errors += 1
            if on_command is not None:
                await on_command(i, total, gcode, ok)
        return success, errors

    @property
    def is_connected(self) -> bool:
        return self._connection.is_connected

    @property
    def connection_state(self) -> ConnectionState:
        return self._connection.state

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self.disconnect()
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")


# ---------------------------------------------------------------------------
# SerialPlotter
# ---------------------------------------------------------------------------

class SerialPlotter(BasePlotter):
    """Real hardware plotter via serial port with Dispatcher backpressure."""

    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 5.0,
                 max_retries: int = 3, enable_heartbeat: bool = True,
                 heartbeat_interval: float = 30.0):
        super().__init__(port, max_retries)
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.enable_heartbeat = enable_heartbeat
        self.heartbeat_interval = heartbeat_interval
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._dispatcher = Dispatcher()

    async def connect(self) -> bool:
        try:
            from serial_asyncio import open_serial_connection
        except ImportError:
            raise RuntimeError("pyserial-asyncio required: pip install pyserial-asyncio")

        self._connection.transition(ConnectionState.CONNECTING)
        self.logger.info(f"Connecting to {self.port} at {self.baud_rate} baud...")
        try:
            self.reader, self.writer = await asyncio.wait_for(
                open_serial_connection(url=self.port, baudrate=self.baud_rate),
                timeout=self.timeout,
            )
        except Exception:
            self._connection.transition(ConnectionState.DISCONNECTED)
            raise

        # Wake-up sequence
        await asyncio.sleep(2.0)
        if self.writer:
            self.writer.write(b"\r\n\r\n")
            await self.writer.drain()
            await asyncio.sleep(2.0)

        # Flush startup messages
        if self.reader:
            try:
                await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        self._connection.transition(ConnectionState.IDLE)

        if self.enable_heartbeat:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

        self.logger.info(f"Connected to {self.port}")
        return True

    async def disconnect(self) -> None:
        if self._connection.state == ConnectionState.DISCONNECTED:
            return
        self._shutdown_event.set()
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            try:
                await asyncio.wait_for(self.writer.wait_closed(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
        self.reader = None
        self.writer = None
        self._connection.transition(ConnectionState.DISCONNECTED)
        self.logger.info("Disconnected")

    async def send_command(self, command: str) -> bool:
        if not self._connection.can_send or not self.writer:
            return False
        try:
            self.status.is_busy = True
            self.status.current_command = command
            self.writer.write(f"{command}\n".encode("utf-8"))
            await self.writer.drain()
            self.command_history.append(command)

            response = await self._read_response()
            self.status.last_response = response
            self.status.is_busy = False

            # ALARM detection
            if response is not None:
                lower = response.lower()
                if "alarm" in lower or "error:" in lower:
                    self.status.last_error = response
                    if self._connection.state == ConnectionState.STREAMING:
                        self._connection.transition(ConnectionState.ALARM)
                    return False

            return response is not None and "ok" in response.lower()
        except Exception as e:
            self.logger.error(f"Error sending '{command}': {e}")
            self.status.is_busy = False
            return False

    async def stream_program(
        self,
        program: GCodeProgram,
        on_command: Optional[Callable[[int, int, str, bool], Awaitable[None]]] = None,
        start_index: int = 0,
    ) -> Tuple[int, int]:
        """Stream with backpressure via Dispatcher."""
        success = 0
        errors = 0
        sent_idx = 0
        total = len(program.commands)
        self._dispatcher._active = True
        self._connection.transition(ConnectionState.STREAMING)

        for i, cmd in enumerate(program.commands):
            if i < start_index:
                continue
            gcode = cmd.to_gcode()
            if gcode == "COMPLETE":
                continue
            # Wait for buffer space
            while not await self._dispatcher.add_command(gcode):
                await asyncio.sleep(self._dispatcher.command_delay)
            # Send from queue
            queued = await self._dispatcher.get_next_command()
            if queued:
                ok = await self.send_command(queued)
                if ok:
                    success += 1
                else:
                    errors += 1
                if on_command is not None:
                    await on_command(sent_idx, total, queued, ok)
                sent_idx += 1

        # Drain remaining
        while True:
            queued = await self._dispatcher.get_next_command()
            if queued is None:
                break
            ok = await self.send_command(queued)
            if ok:
                success += 1
            else:
                errors += 1
            if on_command is not None:
                await on_command(sent_idx, total, queued, ok)
            sent_idx += 1

        self._dispatcher._active = False
        if self._connection.state == ConnectionState.STREAMING:
            self._connection.transition(ConnectionState.IDLE)
        return success, errors

    async def recover(self) -> bool:
        """Attempt to recover from ALARM state."""
        if self._connection.state != ConnectionState.ALARM:
            return False
        self._connection.transition(ConnectionState.RECOVERY)
        try:
            if self.writer:
                # Soft reset
                self.writer.write(b"$X\n")
                await self.writer.drain()
                response = await self._read_response()
                # Home
                self.writer.write(b"$H\n")
                await self.writer.drain()
                response = await self._read_response()
            self._connection.transition(ConnectionState.IDLE)
            return True
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            self._connection.transition(ConnectionState.ALARM)
            return False

    async def pause(self) -> bool:
        """Pause streaming (send feed hold)."""
        if self._connection.state != ConnectionState.STREAMING:
            return False
        if self.writer:
            self.writer.write(b"!")
            await self.writer.drain()
        self._connection.transition(ConnectionState.PAUSED)
        return True

    async def resume(self) -> bool:
        """Resume streaming (send cycle resume)."""
        if self._connection.state != ConnectionState.PAUSED:
            return False
        if self.writer:
            self.writer.write(b"~")
            await self.writer.drain()
        self._connection.transition(ConnectionState.STREAMING)
        return True

    async def _read_response(self) -> Optional[str]:
        if not self.reader:
            return None
        try:
            data = await asyncio.wait_for(self.reader.readline(), timeout=self.timeout)
            return data.decode("utf-8").strip() if data else None
        except asyncio.TimeoutError:
            return None

    async def _heartbeat_monitor(self) -> None:
        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=self.heartbeat_interval
                    )
                    break
                except asyncio.TimeoutError:
                    if self._active and self.writer:
                        self.writer.write(b"?\n")
                        await self.writer.drain()
                        await self._read_response()
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# SimulatedPlotter
# ---------------------------------------------------------------------------

class SimulatedPlotter(BasePlotter):
    """Simulated plotter for testing without hardware."""

    def __init__(self, port: str = "SIMULATED", command_delay: float = 0.01,
                 collect_commands: bool = True):
        super().__init__(port)
        self.command_delay = command_delay
        self.collect_commands = collect_commands
        self.collected: List[str] = []
        self.pen_state = PenState()
        self.position = (0.0, 0.0)
        self.lines: List[Tuple[float, float, float, float, bool]] = []

    @property
    def pen_down(self) -> bool:
        return self.pen_state.is_down

    @pen_down.setter
    def pen_down(self, value: bool):
        if value:
            self.pen_state.set_down()
        else:
            self.pen_state.set_up()

    async def connect(self) -> bool:
        self._connection.transition(ConnectionState.CONNECTING)
        self._connection.transition(ConnectionState.IDLE)
        return True

    async def disconnect(self) -> None:
        if self._connection.state != ConnectionState.DISCONNECTED:
            self._connection.transition(ConnectionState.DISCONNECTED)

    async def send_command(self, command: str) -> bool:
        if not self._connection.can_send:
            return False
        if self.collect_commands:
            self.collected.append(command)
        self._process(command)
        if self.command_delay > 0:
            await asyncio.sleep(self.command_delay)
        # Simulate G4 dwell
        parts = command.split()
        if parts and parts[0] == "G4":
            for p in parts[1:]:
                if p.startswith("P"):
                    try:
                        ms = int(p[1:])
                        await asyncio.sleep(ms / 1000.0 * 0.01)  # 1% of real time
                    except ValueError:
                        pass
        return True

    def _process(self, command: str):
        parts = command.split()
        if not parts:
            return
        cmd = parts[0].upper()
        params = {}
        for p in parts[1:]:
            if len(p) >= 2 and p[0].upper() in "XYZFSP":
                try:
                    params[p[0].upper()] = float(p[1:])
                except ValueError:
                    pass

        if cmd in ("G0", "G1"):
            old = self.position
            new_x = params.get("X", old[0])
            new_y = params.get("Y", old[1])
            is_drawing = self.pen_state.is_down and cmd == "G1"
            self.lines.append((old[0], old[1], new_x, new_y, is_drawing))
            self.position = (new_x, new_y)
        elif cmd == "M3":
            self.pen_state.set_down()
        elif cmd == "M5":
            self.pen_state.set_up()
