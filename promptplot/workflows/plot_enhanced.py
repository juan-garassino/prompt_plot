"""
Plot-Enhanced G-Code Workflow

This workflow implements visual feedback loops by integrating matplotlib plot analysis
with G-code generation decisions, creating adaptive drawing logic based on real-time
plot state analysis and grid-based coordinate optimization and path planning.

Requirements addressed:
- 2.3: Visual feedback incorporated into G-code generation decisions
- 4.2: Adaptive drawing logic based on real-time plot state analysis  
- 4.3: Grid-based coordinate optimization and path planning
"""

import asyncio
import json
import time
from typing import List, Optional, Union, Dict, Any, Tuple
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    step,
    Context,
)
from colorama import Fore, Style, init

from ..core.base_workflow import BasePromptPlotWorkflow
from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy
from ..core.exceptions import WorkflowException, ValidationException
from ..llm.plot_llm import PlotEnhancedLLM, PlotContext, VisualPromptContext
from ..llm.providers import LLMProvider
from ..vision.plot_analyzer import PlotAnalyzer, PlotState, DrawingProgress
from ..plotter.visualizer import PlotterVisualizer
from ..strategies.selector import StrategySelector

# Initialize colorama for cross-platform color support
init(autoreset=True)

# Event Classes
class InitializePlotContextEvent(Event):
    """Event to initialize plot context and visualization"""
    prompt: str
    target_strategy: Optional[DrawingStrategy] = None
    grid_enabled: bool = True

class AnalyzePlotStateEvent(Event):
    """Event to analyze current plot state"""
    prompt: str
    step: int
    target_strategy: Optional[DrawingStrategy] = None

class GenerateVisualCommandEvent(Event):
    """Event to generate command with visual context"""
    prompt: str
    step: int
    plot_analysis: Dict[str, Any]
    target_strategy: Optional[DrawingStrategy] = None

class CommandValidationErrorEvent(Event):
    """Event for validation errors in command generation"""
    error: str
    issues: str
    prompt: str
    step: int
    plot_analysis: Dict[str, Any]

class ValidatedVisualCommandEvent(Event):
    """Event containing validated command with visual context"""
    command: GCodeCommand
    prompt: str
    step: int
    plot_analysis: Dict[str, Any]
    is_complete: bool

class UpdatePlotStateEvent(Event):
    """Event to update plot state after command execution"""
    command: GCodeCommand
    prompt: str
    step: int

class ContinueVisualGenerationEvent(Event):
    """Event to continue with next visual command"""
    prompt: str
    step: int

class PlotEnhancedCompleteEvent(Event):
    """Event indicating plot-enhanced generation is complete"""
    prompt: str
    commands: List[GCodeCommand]
    step_count: int
    final_plot_state: Optional[PlotState] = None

class PlotEnhancedWorkflow(BasePromptPlotWorkflow):
    """
    Plot-enhanced workflow for visual feedback-driven G-code generation
    
    This workflow integrates matplotlib plot analysis with G-code generation,
    providing adaptive drawing logic based on real-time visual feedback and
    grid-based coordinate optimization.
    
    Workflow steps:
    1. start → Initialize workflow and plot context
    2. initialize_plot_context → Set up visualization and analysis tools
    3. analyze_plot_state → Analyze current plot state and provide recommendations
    4. generate_visual_command → Generate command using visual context
    5. validate_command → Validate generated command
    6. update_plot_state → Execute command and update visualization
    7. continue_visual_generation → Loop back for next command or complete
    8. finalize_plot_program → Create final program with visual analysis
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        plot_analyzer: Optional[PlotAnalyzer] = None,
        visualizer: Optional[PlotterVisualizer] = None,
        strategy_selector: Optional[StrategySelector] = None,
        enable_grid: bool = True,
        coordinate_bounds: Optional[Tuple[float, float, float, float]] = None,
        **kwargs
    ):
        """
        Initialize plot-enhanced workflow
        
        Args:
            llm_provider: LLM provider for text generation
            plot_analyzer: Plot analyzer for visual context extraction
            visualizer: Plotter visualizer for real-time plot updates
            strategy_selector: Strategy selector for drawing optimization
            enable_grid: Whether to enable grid-based coordinate system
            coordinate_bounds: Optional coordinate bounds (x_min, x_max, y_min, y_max)
            **kwargs: Additional base workflow arguments
        """
        super().__init__(llm_provider, **kwargs)
        
        # Initialize visual components
        self.plot_analyzer = plot_analyzer or PlotAnalyzer(
            grid_resolution=1.0,
            coordinate_precision=3,
            enable_caching=True
        )
        
        self.visualizer = visualizer or PlotterVisualizer(
            figure_size=(10, 10),
            enable_grid=enable_grid,
            coordinate_bounds=coordinate_bounds
        )
        
        self.strategy_selector = strategy_selector or StrategySelector()
        
        # Initialize plot-enhanced LLM
        self.plot_llm = PlotEnhancedLLM(
            base_llm=llm_provider,
            plot_analyzer=self.plot_analyzer,
            max_plot_history=5,
            coordinate_precision=3
        )
        
        # Configuration
        self.enable_grid = enable_grid
        self.coordinate_bounds = coordinate_bounds or (-50, 50, -50, 50)
        
        # State tracking
        self._current_figure = None
        self._plot_history: List[PlotContext] = []
        
    @step
    async def start(self, ctx: Context, ev: StartEvent) -> InitializePlotContextEvent:
        """Start the workflow and initialize context"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║   Plot-Enhanced G-Code Workflow Start        ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Initializing plot-enhanced workflow{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Setting up visual feedback system with matplotlib integration{Style.RESET_ALL}")
        
        # Get parameters from event
        prompt = getattr(ev, "prompt", "draw a simple square")
        target_strategy = getattr(ev, "target_strategy", None)
        max_steps = getattr(ev, "max_steps", self.max_steps)
        
        # Initialize context using base workflow method
        await self.initialize_context(ctx, prompt, max_steps=max_steps)
        
        # Store plot-specific context
        await ctx.set("target_strategy", target_strategy)
        await ctx.set("plot_history", [])
        await ctx.set("visual_analysis_count", 0)
        
        print(f"{Fore.GREEN}├── [+] Workflow initialization complete{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Grid enabled: {self.enable_grid}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Coordinate bounds: {self.coordinate_bounds}{Style.RESET_ALL}")
        
        # Determine strategy if not provided
        if target_strategy is None:
            print(f"{Fore.CYAN}├── [*] Analyzing prompt for strategy selection{Style.RESET_ALL}")
            try:
                complexity = self.strategy_selector.analyze_prompt_complexity(prompt)
                target_strategy = self.strategy_selector.select_strategy(complexity)
                await ctx.set("target_strategy", target_strategy)
                print(f"{Fore.GREEN}│   └── Selected strategy: {target_strategy.value}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}│   └── Strategy selection failed, using AUTO: {str(e)}{Style.RESET_ALL}")
                target_strategy = DrawingStrategy.AUTO
                await ctx.set("target_strategy", target_strategy)
        
        print(f"{Fore.CYAN}└── [*] Moving to plot context initialization{Style.RESET_ALL}")
        return InitializePlotContextEvent(
            prompt=prompt,
            target_strategy=target_strategy,
            grid_enabled=self.enable_grid
        )
    
    @step
    async def initialize_plot_context(self, ctx: Context, ev: InitializePlotContextEvent) -> AnalyzePlotStateEvent:
        """Initialize plot context and visualization"""
        print(f"{Fore.CYAN}[*] ├── Initializing plot context{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Setting up matplotlib figure and coordinate system for visual feedback{Style.RESET_ALL}")
        
        try:
            # Initialize matplotlib figure
            print(f"{Fore.CYAN}├── [*] Creating matplotlib figure{Style.RESET_ALL}")
            self._current_figure = self.visualizer.create_figure()
            
            # Set up coordinate system
            if ev.grid_enabled:
                print(f"{Fore.CYAN}├── [*] Setting up grid coordinate system{Style.RESET_ALL}")
                self.visualizer.setup_grid(
                    self._current_figure,
                    bounds=self.coordinate_bounds,
                    grid_spacing=5.0
                )
            
            # Initialize plot context in LLM
            print(f"{Fore.CYAN}├── [*] Initializing visual context in LLM{Style.RESET_ALL}")
            initial_context = self.plot_llm.add_plot_context(self._current_figure)
            
            # Store initial context
            plot_history = await ctx.get("plot_history", default=[])
            plot_history.append(initial_context)
            await ctx.set("plot_history", plot_history)
            
            print(f"{Fore.GREEN}├── [+] Plot context initialized successfully{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   └── Figure size: {self._current_figure.get_size_inches()}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   └── Grid elements: {len(initial_context.plot_state.elements)}{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}├── [!] Plot context initialization failed: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── Continuing without visual context{Style.RESET_ALL}")
            await ctx.set("visual_context_available", False)
        
        print(f"{Fore.CYAN}└── [*] Moving to plot state analysis{Style.RESET_ALL}")
        return AnalyzePlotStateEvent(
            prompt=ev.prompt,
            step=1,
            target_strategy=ev.target_strategy
        )
    
    @step
    async def analyze_plot_state(self, ctx: Context, ev: AnalyzePlotStateEvent) -> GenerateVisualCommandEvent:
        """Analyze current plot state and provide recommendations"""
        print(f"{Fore.CYAN}[*] ├── Analyzing plot state for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Using computer vision to analyze current drawing state and recommend next actions{Style.RESET_ALL}")
        
        plot_analysis = {}
        
        try:
            if self._current_figure is not None:
                print(f"{Fore.CYAN}├── [*] Performing visual analysis{Style.RESET_ALL}")
                
                # Analyze current plot state
                analysis_result = await self.plot_llm.analyze_plot_state(
                    self._current_figure,
                    ev.prompt
                )
                
                plot_analysis = analysis_result
                
                # Update analysis count
                analysis_count = await ctx.get("visual_analysis_count", default=0)
                await ctx.set("visual_analysis_count", analysis_count + 1)
                
                print(f"{Fore.GREEN}├── [+] Visual analysis complete{Style.RESET_ALL}")
                print(f"{Fore.GREEN}│   └── Progress: {analysis_result.get('completion_estimate', 'Unknown')}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}│   └── Strategy: {analysis_result.get('strategy_recommendation', 'auto')}{Style.RESET_ALL}")
                
                # Log analysis summary
                if 'current_state_summary' in analysis_result:
                    print(f"{Fore.BLUE}│   └── State: {analysis_result['current_state_summary'][:60]}...{Style.RESET_ALL}")
                
            else:
                print(f"{Fore.YELLOW}├── [!] No visual context available{Style.RESET_ALL}")
                plot_analysis = {
                    "current_state_summary": "No visual context available",
                    "progress_assessment": "Unable to assess visually",
                    "next_action_recommendation": "Generate next command based on text prompt only",
                    "coordinate_suggestions": [],
                    "strategy_recommendation": ev.target_strategy.value if ev.target_strategy else "auto",
                    "completion_estimate": "Unknown"
                }
                
        except Exception as e:
            print(f"{Fore.RED}├── [!] Plot analysis failed: {str(e)}{Style.RESET_ALL}")
            plot_analysis = {
                "error": str(e),
                "current_state_summary": f"Analysis failed: {str(e)}",
                "progress_assessment": "Unable to assess due to error",
                "next_action_recommendation": "Continue with basic generation",
                "coordinate_suggestions": [],
                "strategy_recommendation": "auto",
                "completion_estimate": "Unknown"
            }
        
        print(f"{Fore.CYAN}└── [*] Moving to visual command generation{Style.RESET_ALL}")
        return GenerateVisualCommandEvent(
            prompt=ev.prompt,
            step=ev.step,
            plot_analysis=plot_analysis,
            target_strategy=ev.target_strategy
        )
    
    @step
    async def generate_visual_command(self, ctx: Context, ev: Union[GenerateVisualCommandEvent, CommandValidationErrorEvent]) -> Union[CommandValidationErrorEvent, ValidatedVisualCommandEvent]:
        """Generate command using visual context and plot analysis"""
        print(f"{Fore.CYAN}[*] ├── Generating visual command for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Using LLM with visual context to generate next G-code command{Style.RESET_ALL}")
        
        # Track retries for this specific step
        task_key = f"visual_retries_step_{ev.step}"
        
        # Check retry limits
        if not await self.check_retry_limits(ctx, ev.step, task_key):
            print(f"{Fore.RED}├── [!] Maximum retries exceeded for step {ev.step}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}│   └── Using fallback COMPLETE command{Style.RESET_ALL}")
            
            fallback_command = self.create_fallback_command()
            return ValidatedVisualCommandEvent(
                command=fallback_command,
                prompt=ev.prompt,
                step=ev.step,
                plot_analysis=ev.plot_analysis,
                is_complete=True
            )
        
        current_retries = await ctx.get(task_key, default=0)
        max_retries = await ctx.get("max_retries")
        print(f"{Fore.YELLOW}├── [*] Attempt {current_retries}/{max_retries}{Style.RESET_ALL}")
        
        try:
            # Generate command with visual context
            print(f"{Fore.CYAN}├── [*] Calling plot-enhanced LLM{Style.RESET_ALL}")
            
            figures = [self._current_figure] if self._current_figure is not None else None
            
            response_text = await self.plot_llm.generate_with_visual_context(
                prompt=ev.prompt,
                figures=figures,
                target_strategy=ev.target_strategy,
                use_multimodal=True
            )
            
            print(f"{Fore.GREEN}├── [+] Visual command generation complete{Style.RESET_ALL}")
            
            # Validate the generated command
            print(f"{Fore.CYAN}├── [*] Validating generated command{Style.RESET_ALL}")
            result = await self.validate_gcode_command(response_text)
            
            if isinstance(result, Exception):
                # Validation failed
                print(f"{Fore.RED}├── [!] Command validation failed{Style.RESET_ALL}")
                print(f"{Fore.RED}│   └── Error: {str(result)}{Style.RESET_ALL}")
                
                return CommandValidationErrorEvent(
                    error=str(result),
                    issues=response_text,
                    prompt=ev.prompt,
                    step=ev.step,
                    plot_analysis=ev.plot_analysis
                )
            
            # Validation successful
            command = result
            is_complete = command.command == "COMPLETE"
            
            print(f"{Fore.GREEN}├── [+] Command validation successful{Style.RESET_ALL}")
            print(f"{Fore.GREEN}│   └── Command: {command.to_gcode()}{Style.RESET_ALL}")
            
            if is_complete:
                print(f"{Fore.GREEN}└── [+] Reached completion command{Style.RESET_ALL}")
            
            return ValidatedVisualCommandEvent(
                command=command,
                prompt=ev.prompt,
                step=ev.step,
                plot_analysis=ev.plot_analysis,
                is_complete=is_complete
            )
            
        except Exception as e:
            print(f"{Fore.RED}├── [!] Visual command generation failed: {str(e)}{Style.RESET_ALL}")
            
            return CommandValidationErrorEvent(
                error=str(e),
                issues="Generation failed",
                prompt=ev.prompt,
                step=ev.step,
                plot_analysis=ev.plot_analysis
            )
    
    @step
    async def update_plot_state(self, ctx: Context, ev: ValidatedVisualCommandEvent) -> Union[ContinueVisualGenerationEvent, PlotEnhancedCompleteEvent]:
        """Update plot state after command execution"""
        print(f"{Fore.CYAN}[*] ├── Updating plot state for step {ev.step}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Executing command in visualization and updating plot context{Style.RESET_ALL}")
        
        # Add command to history if not COMPLETE
        if not ev.is_complete:
            print(f"{Fore.CYAN}├── [*] Adding command to program{Style.RESET_ALL}")
            await self.add_command_to_history(ctx, ev.command)
            
            # Add command to plot LLM history
            self.plot_llm.add_command_to_history(ev.command)
            
            # Execute command in visualizer
            try:
                if self._current_figure is not None:
                    print(f"{Fore.CYAN}├── [*] Executing command in visualization{Style.RESET_ALL}")
                    success = await self.visualizer.execute_command(
                        ev.command,
                        self._current_figure
                    )
                    
                    if success:
                        print(f"{Fore.GREEN}│   └── Command executed successfully{Style.RESET_ALL}")
                        
                        # Update plot context
                        updated_context = self.plot_llm.add_plot_context(self._current_figure)
                        
                        # Store updated context
                        plot_history = await ctx.get("plot_history", default=[])
                        plot_history.append(updated_context)
                        await ctx.set("plot_history", plot_history)
                        
                    else:
                        print(f"{Fore.YELLOW}│   └── Command execution failed in visualizer{Style.RESET_ALL}")
                        
            except Exception as e:
                print(f"{Fore.RED}├── [!] Plot state update failed: {str(e)}{Style.RESET_ALL}")
        
        # Check completion conditions
        print(f"{Fore.CYAN}├── [*] Checking completion conditions{Style.RESET_ALL}")
        
        commands = await ctx.get("commands", default=[])
        
        if ev.is_complete:
            print(f"{Fore.GREEN}└── [+] Program complete via COMPLETE command{Style.RESET_ALL}")
            
            # Get final plot state
            final_plot_state = None
            if self._current_figure is not None:
                try:
                    final_context = self.plot_llm.add_plot_context(self._current_figure)
                    final_plot_state = final_context.plot_state
                except Exception as e:
                    print(f"{Fore.YELLOW}    └── Failed to capture final plot state: {str(e)}{Style.RESET_ALL}")
            
            return PlotEnhancedCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step,
                final_plot_state=final_plot_state
            )
            
        elif not await self.check_step_limits(ctx, ev.step):
            max_steps = await ctx.get("max_steps")
            print(f"{Fore.YELLOW}└── [!] Program complete via max steps limit ({max_steps}){Style.RESET_ALL}")
            
            # Get final plot state
            final_plot_state = None
            if self._current_figure is not None:
                try:
                    final_context = self.plot_llm.add_plot_context(self._current_figure)
                    final_plot_state = final_context.plot_state
                except Exception as e:
                    print(f"{Fore.YELLOW}    └── Failed to capture final plot state: {str(e)}{Style.RESET_ALL}")
            
            return PlotEnhancedCompleteEvent(
                prompt=ev.prompt,
                commands=commands,
                step_count=ev.step,
                final_plot_state=final_plot_state
            )
        else:
            # Continue to next step
            next_step = ev.step + 1
            print(f"{Fore.GREEN}└── [+] Continuing to step {next_step}{Style.RESET_ALL}")
            return ContinueVisualGenerationEvent(
                prompt=ev.prompt,
                step=next_step
            )
    
    @step
    async def continue_visual_generation(self, ctx: Context, ev: ContinueVisualGenerationEvent) -> AnalyzePlotStateEvent:
        """Continue to next visual command generation"""
        print(f"{Fore.CYAN}[*] ├── Continuing visual generation (step {ev.step}){Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Preparing for next command with updated visual context{Style.RESET_ALL}")
        
        # Get current program state
        commands = await ctx.get("commands", default=[])
        target_strategy = await ctx.get("target_strategy")
        
        print(f"{Fore.CYAN}├── [*] Current program state{Style.RESET_ALL}")
        print(f"{Fore.CYAN}│   └── Commands: {len(commands)}, Strategy: {target_strategy.value if target_strategy else 'auto'}{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}└── [*] Moving to plot state analysis{Style.RESET_ALL}")
        return AnalyzePlotStateEvent(
            prompt=ev.prompt,
            step=ev.step,
            target_strategy=target_strategy
        )
    
    @step
    async def finalize_plot_program(self, ctx: Context, ev: PlotEnhancedCompleteEvent) -> StopEvent:
        """Finalize the plot-enhanced G-code program"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║   Plot-Enhanced G-Code Workflow Complete     ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[*] ├── Finalizing plot-enhanced program{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[?] │   └── Creating final program with visual analysis metadata{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}├── [+] Drawing prompt: {ev.prompt}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Commands generated: {len(ev.commands)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Steps taken: {ev.step_count}{Style.RESET_ALL}")
        
        # Get visual analysis statistics
        analysis_count = await ctx.get("visual_analysis_count", default=0)
        plot_history = await ctx.get("plot_history", default=[])
        
        print(f"{Fore.GREEN}├── [+] Visual analyses performed: {analysis_count}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├── [+] Plot states captured: {len(plot_history)}{Style.RESET_ALL}")
        
        # Create final program
        program = GCodeProgram(commands=ev.commands)
        gcode_text = program.to_gcode()
        
        # Show program preview
        print(f"{Fore.CYAN}├── [*] Program preview (first 5 commands):{Style.RESET_ALL}")
        preview_lines = min(5, len(ev.commands))
        for i in range(preview_lines):
            cmd = ev.commands[i]
            print(f"{Fore.BLUE}│       {cmd.to_gcode()}{Style.RESET_ALL}")
        
        if len(ev.commands) > preview_lines:
            print(f"{Fore.BLUE}│       ... ({len(ev.commands) - preview_lines} more commands) ...{Style.RESET_ALL}")
        
        # Save visualization if available
        visualization_path = None
        if self._current_figure is not None:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                visualization_path = f"results/visualizations/plot_enhanced_{timestamp}.png"
                self._current_figure.savefig(visualization_path, dpi=150, bbox_inches='tight')
                print(f"{Fore.GREEN}├── [+] Visualization saved: {visualization_path}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}├── [!] Failed to save visualization: {str(e)}{Style.RESET_ALL}")
        
        # Create enhanced metadata
        metadata = {
            "visual_analysis_count": analysis_count,
            "plot_states_captured": len(plot_history),
            "visualization_path": visualization_path,
            "coordinate_bounds": self.coordinate_bounds,
            "grid_enabled": self.enable_grid,
            "final_plot_elements": len(ev.final_plot_state.elements) if ev.final_plot_state else 0
        }
        
        # Update context with final data
        await ctx.set("step_count", ev.step_count)
        await ctx.set("metadata", metadata)
        
        # Create workflow result
        result_obj = await self.create_workflow_result(ctx, success=True)
        
        # Enhanced result with visual data
        result = {
            "prompt": ev.prompt,
            "commands_count": len(ev.commands),
            "gcode": gcode_text,
            "step_count": ev.step_count,
            "program": program.model_dump(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "visual_metadata": metadata,
            "plot_analysis_summary": {
                "total_analyses": analysis_count,
                "plot_states": len(plot_history),
                "final_elements": len(ev.final_plot_state.elements) if ev.final_plot_state else 0
            }
        }
        
        print(f"{Fore.GREEN}└── [+] Plot-enhanced workflow complete{Style.RESET_ALL}")
        return StopEvent(result=result)
    
    async def generate_gcode(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate G-code using plot-enhanced workflow
        
        Args:
            prompt: Drawing prompt
            **kwargs: Additional parameters
            
        Returns:
            Workflow result with visual analysis data
        """
        return await self.run(
            prompt=prompt,
            target_strategy=kwargs.get("target_strategy"),
            max_steps=kwargs.get("max_steps", self.max_steps)
        )
    
    def get_current_figure(self) -> Optional[matplotlib.figure.Figure]:
        """Get current matplotlib figure"""
        return self._current_figure
    
    def get_plot_history(self) -> List[PlotContext]:
        """Get plot context history"""
        return self._plot_history.copy()
    
    def save_context(self, output_path: str) -> None:
        """Save workflow context for analysis"""
        self.plot_llm.save_context(output_path)


async def main():
    """Main function for testing the plot-enhanced workflow"""
    from llama_index.llms.ollama import Ollama
    from llama_index.llms.azure_openai import AzureOpenAI
    from ..llm.providers import OllamaProvider, AzureOpenAIProvider
    import os

    print(f"{Fore.CYAN}[*] ├── Starting plot-enhanced G-code workflow{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[?] │   └── Testing visual feedback integration with matplotlib{Style.RESET_ALL}")
    
    # Create LLM provider
    print(f"{Fore.CYAN}├── [*] Initializing LLM provider{Style.RESET_ALL}")
    
    if all(os.environ.get(key) for key in ["GPT4_API_KEY", "GPT4_API_VERSION", "GPT4_ENDPOINT"]):
        print(f"{Fore.CYAN}│   └── Using Azure OpenAI{Style.RESET_ALL}")
        llm_provider = AzureOpenAIProvider(
            model="gpt-4o",
            deployment_name="gpt-4o-gs",
            timeout=1220
        )
    else:
        print(f"{Fore.CYAN}│   └── Using Ollama{Style.RESET_ALL}")
        llm_provider = OllamaProvider(
            model="llama3.2:3b",
            request_timeout=10000
        )
    
    try:
        # Create workflow
        print(f"{Fore.CYAN}├── [*] Creating plot-enhanced workflow{Style.RESET_ALL}")
        workflow = PlotEnhancedWorkflow(
            llm_provider=llm_provider,
            enable_grid=True,
            coordinate_bounds=(-25, 25, -25, 25),
            timeout=15000
        )
        
        # Test prompts
        test_prompts = [
            "draw a simple square",
            "draw a circle with radius 10",
            "draw a house with a triangular roof and rectangular base"
        ]
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"{Fore.CYAN}├── [*] Test {i}: {prompt}{Style.RESET_ALL}")
            
            try:
                # Run workflow
                result = await workflow.run(
                    prompt=prompt,
                    max_steps=20,
                    target_strategy=DrawingStrategy.AUTO
                )
                
                if result:
                    # Save G-code
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"results/gcode/plot_enhanced_{timestamp}_test{i}.txt"
                    
                    with open(filename, 'w') as f:
                        f.write(result.get("gcode", ""))
                    
                    print(f"{Fore.GREEN}│   └── G-code saved: {filename}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}│   └── Commands: {result.get('commands_count', 0)}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}│   └── Visual analyses: {result.get('visual_metadata', {}).get('visual_analysis_count', 0)}{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.RED}│   └── Test {i} failed: {str(e)}{Style.RESET_ALL}")
        
        # Save workflow context
        context_path = f"results/logs/plot_enhanced_context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        workflow.save_context(context_path)
        print(f"{Fore.GREEN}└── [+] Workflow context saved: {context_path}{Style.RESET_ALL}")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] └── Operation interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] └── Error: {str(e)}{Style.RESET_ALL}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())