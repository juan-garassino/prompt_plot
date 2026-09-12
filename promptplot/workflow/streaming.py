"""StreamingGCodeWorkflow — one command at a time → validate → send to plotter.

Split out of the former monolithic workflow.py during the v3.1 reorg.
"""

from typing import Optional, List
from datetime import datetime


from ..engine import (
    Workflow,
)
from ..models import (
    GCodeCommand,
    GCodeProgram,
    WorkflowResult,
)
from ..config import get_config, PromptPlotConfig
from ..llm import (
    LLMProvider,
    get_llm_provider,
    build_next_command_prompt,
)
from ..postprocess import run_pipeline

from ._shared import (
    logger,
    _validate_output,
)


# ===== sliced body (StreamingGCodeWorkflow) =====
class StreamingGCodeWorkflow(Workflow):
    """Generate GCode one command at a time and optionally stream to plotter."""

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        config: Optional[PromptPlotConfig] = None,
        max_steps: int = 50,
        **kwargs,
    ):
        kwargs.setdefault("timeout", 10000)
        super().__init__(**kwargs)
        self.config = config or get_config()
        self.llm = llm or get_llm_provider(self.config.llm)
        self.max_steps = max_steps

    async def generate_gcode(self, prompt: str) -> WorkflowResult:
        """Run streaming generation (not using workflow events for simplicity)."""
        commands: List[GCodeCommand] = []
        logger.stream_start("Streaming G-Code Generation", prompt, self.max_steps)

        for step_num in range(self.max_steps):
            history = (
                "\n".join(f"Step {i+1}: {c.to_gcode()}" for i, c in enumerate(commands))
                if commands
                else "No previous commands"
            )

            llm_prompt = build_next_command_prompt(
                prompt, history, self.config.paper, self.config.pen
            )
            response = await self.llm.acomplete(llm_prompt)
            result = _validate_output(response)

            if isinstance(result, Exception):
                logger.stream_command(step_num + 1, f"ERROR: {result}", "error")
                continue

            if isinstance(result, GCodeCommand):
                if result.command == "COMPLETE":
                    logger.stream_command(step_num + 1, "COMPLETE", "success")
                    break
                commands.append(result)
                logger.stream_command(step_num + 1, result.to_gcode(), "success")

        if not commands:
            return WorkflowResult(
                success=False,
                prompt=prompt,
                commands_count=0,
                gcode="",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message="No commands generated",
            )

        program = GCodeProgram(commands=commands)
        optimized = run_pipeline(program, self.config)

        return WorkflowResult(
            success=True,
            prompt=prompt,
            commands_count=len(optimized.commands),
            gcode=optimized.to_gcode(),
            program=optimized,
            step_count=len(commands),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
