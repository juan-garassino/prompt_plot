"""LiveDrawWorkflow — real-time LLM → plotter streaming, one command at a time.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

from typing import Optional, List, Dict, Any, Callable, Awaitable


from ..engine import (
    DrawingSession,
    Phase,
    PenState,
)
from ..models import (
    GCodeCommand,
    GCodeProgram,
)
from ..config import get_config, PromptPlotConfig
from ..llm import (
    LLMProvider,
    get_llm_provider,
    build_next_command_prompt,
)
from ..postprocess import validate_single_command
from ..plotter import BasePlotter

from ._shared import (
    _validate_output,
)


# ===== sliced body (LiveDrawWorkflow) =====
class LiveDrawWorkflow:
    """Real-time workflow: LLM generates one command → validate → send to plotter → repeat.

    The pen moves while the LLM is still thinking about the next command.
    No global stroke optimization (can't reorder what's already drawn),
    but per-command bounds clamping and pen safety are applied live.
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        config: Optional[PromptPlotConfig] = None,
        plotter: Optional[BasePlotter] = None,
        max_steps: int = 80,
        on_step: Optional[Callable[[int, int, str, bool, List[str]], Awaitable[None]]] = None,
        session: Optional[DrawingSession] = None,
    ):
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.plotter = plotter
        self.max_steps = max_steps
        self.on_step = on_step
        self.session = session

    async def run(self, prompt: str) -> Dict[str, Any]:
        """Execute the live draw loop."""
        commands_sent: List[GCodeCommand] = []
        all_commands: List[GCodeCommand] = []
        sent_count = 0
        error_count = 0
        skipped = 0
        pen_state = PenState()

        if self.session:
            self.session.prompt = prompt
            self.session.mode = "live"
            self.session.set_phase(Phase.STREAMING)

        # Start with pen up
        if self.plotter:
            startup = GCodeCommand(command="M5")
            gcode = startup.to_gcode()
            await self.plotter.send_command(gcode)
            all_commands.append(startup)
            sent_count += 1

        for step_num in range(1, self.max_steps + 1):
            # Build history from what we've actually sent
            if commands_sent:
                history = "\n".join(
                    f"Step {i+1}: {c.to_gcode()}" for i, c in enumerate(commands_sent)
                )
            else:
                history = "No previous commands"

            # Ask LLM for the next command
            llm_prompt = build_next_command_prompt(
                prompt,
                history,
                self.config.paper,
                self.config.pen,
            )
            try:
                response = await self.llm.acomplete(llm_prompt)
            except Exception as e:
                if self.on_step:
                    await self.on_step(step_num, self.max_steps, f"LLM error: {e}", False, [])
                if self.session:
                    self.session.log_command(step_num, f"LLM error: {e}", "err")
                error_count += 1
                continue

            try:
                result = _validate_output(response)
            except Exception as parse_err:
                result = parse_err

            if isinstance(result, Exception):
                if self.on_step:
                    await self.on_step(
                        step_num, self.max_steps, f"parse error", False, [str(result)]
                    )
                if self.session:
                    self.session.log_command(step_num, "parse error", "skip")
                skipped += 1
                continue

            if not isinstance(result, GCodeCommand):
                # Got a full program instead of single command — skip
                if self.on_step:
                    await self.on_step(step_num, self.max_steps, "unexpected format", False, [])
                if self.session:
                    self.session.log_command(step_num, "unexpected format", "skip")
                skipped += 1
                continue

            # Check for completion signal
            if result.command == "COMPLETE":
                if self.on_step:
                    await self.on_step(step_num, self.max_steps, "COMPLETE", True, [])
                if self.session:
                    self.session.log_command(step_num, "COMPLETE", "DONE")
                break

            # Per-command validation: bounds clamping + pen safety
            fixed_cmd, warnings, prefix_cmds = validate_single_command(
                result,
                self.config.paper,
                pen_state,
            )

            # Send prefix commands (pen safety fixes) to plotter
            if self.plotter:
                for pcmd in prefix_cmds:
                    gcode = pcmd.to_gcode()
                    ok = await self.plotter.send_command(gcode)
                    all_commands.append(pcmd)
                    if pcmd.command == "M3":
                        pen_state.set_down()
                    elif pcmd.command == "M5":
                        pen_state.set_up()
                    if ok:
                        sent_count += 1
                    else:
                        error_count += 1

            # Send the actual command to plotter
            gcode_str = fixed_cmd.to_gcode()
            ok = True
            if self.plotter:
                ok = await self.plotter.send_command(gcode_str)

            if ok:
                sent_count += 1
                commands_sent.append(fixed_cmd)
                all_commands.append(fixed_cmd)
                # Track pen state
                if fixed_cmd.command == "M3":
                    pen_state.set_down()
                elif fixed_cmd.command == "M5":
                    pen_state.set_up()
            else:
                error_count += 1

            if self.on_step:
                await self.on_step(step_num, self.max_steps, gcode_str, ok, warnings)
            if self.session:
                status = "ok" if ok else "err"
                self.session.log_command(step_num, gcode_str, status, warnings)

        # End with pen up + home
        if self.plotter:
            for end_cmd in [
                GCodeCommand(command="M5"),
                GCodeCommand(command="G0", x=0, y=0),
            ]:
                gcode = end_cmd.to_gcode()
                await self.plotter.send_command(gcode)
                all_commands.append(end_cmd)
                sent_count += 1

        program = GCodeProgram(commands=all_commands)

        if self.session:
            self.session.set_phase(Phase.DONE)

        return {
            "prompt": prompt,
            "commands": all_commands,
            "program": program.model_dump(),
            "gcode": program.to_gcode(),
            "sent_count": sent_count,
            "error_count": error_count,
            "skipped_count": skipped,
            "success": error_count == 0,
        }
