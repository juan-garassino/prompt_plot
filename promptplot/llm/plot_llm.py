"""
Plot-Enhanced LLM Integration using LlamaIndex

This module provides LLM integration with matplotlib plot data as visual context,
implementing multi-modal prompt construction with text and plot state information,
and supporting plot coordinate data and grid-based context management.

Requirements addressed:
- 2.1: LlamaIndex with image blocks for visual content analysis
- 2.2: Visual feedback from plot snapshots for drawing decisions  
- 4.1: Visual analysis results incorporated into G-code generation
"""

import asyncio
import base64
import io
import json
import logging
import time
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.figure
import numpy as np
from llama_index.core.base.llms.types import ChatMessage, ImageBlock, TextBlock

from .providers import LLMProvider, LLMProviderError
from .templates import PromptTemplateManager, get_template_manager
from .plot_context import PlotContextManager, PlotContextConfig, ValidationLevel
from ..vision.plot_analyzer import PlotAnalyzer, PlotState, DrawingProgress, GridInfo
from ..core.models import GCodeCommand, GCodeProgram, DrawingStrategy


@dataclass
class PlotContext:
    """Context information from matplotlib plot analysis"""
    plot_state: PlotState
    drawing_progress: Optional[DrawingProgress] = None
    grid_coordinates: Optional[List[Tuple[int, int]]] = None
    visual_features: Dict[str, Any] = field(default_factory=dict)
    coordinate_bounds: Optional[Dict[str, float]] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class VisualPromptContext:
    """Complete context for visual-enhanced prompting"""
    text_prompt: str
    plot_contexts: List[PlotContext] = field(default_factory=list)
    command_history: List[GCodeCommand] = field(default_factory=list)
    target_strategy: Optional[DrawingStrategy] = None
    grid_reference: Optional[GridInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlotEnhancedLLM:
    """
    LLM with computer vision integration using LlamaIndex patterns
    
    Provides multi-modal prompt construction combining text prompts with
    matplotlib plot data as visual context for intelligent G-code generation.
    """
    
    def __init__(
        self,
        base_llm: LLMProvider,
        plot_analyzer: Optional[PlotAnalyzer] = None,
        template_manager: Optional[PromptTemplateManager] = None,
        plot_context_manager: Optional[PlotContextManager] = None,
        max_plot_history: int = 5,
        coordinate_precision: int = 3
    ):
        """
        Initialize plot-enhanced LLM
        
        Args:
            base_llm: Base LLM provider for text generation
            plot_analyzer: Plot analyzer for visual context extraction
            template_manager: Template manager for prompt formatting
            plot_context_manager: Plot context manager for comprehensive state management
            max_plot_history: Maximum number of plot states to maintain in context
            coordinate_precision: Decimal precision for coordinate calculations
        """
        self.base_llm = base_llm
        self.plot_analyzer = plot_analyzer or PlotAnalyzer()
        self.template_manager = template_manager or get_template_manager()
        self.max_plot_history = max_plot_history
        self.coordinate_precision = coordinate_precision
        
        # Context management
        self.plot_context_manager = plot_context_manager
        self._plot_history: List[PlotContext] = []
        self._command_history: List[GCodeCommand] = []
        
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Register plot-enhanced templates
        self._register_plot_templates()
    
    def _register_plot_templates(self) -> None:
        """Register plot-enhanced prompt templates"""
        from .templates import PromptTemplate
        
        # Plot-enhanced G-code generation template
        plot_gcode_template = '''
Generate G-code commands for a pen plotter using both text prompt and visual plot context.

Text Prompt: {prompt}

Visual Context:
{plot_context}

Grid Reference:
{grid_info}

Command History:
{history}

Rules:
1. Use the visual context to understand current drawing state and progress
2. Consider grid coordinates for precise positioning: {grid_coordinates}
3. Adapt drawing strategy based on visual analysis: {drawing_strategy}
4. Use coordinate bounds from visual analysis: {coordinate_bounds}
5. Generate commands that build upon existing plot elements
6. Use G0 for rapid movements, G1 for drawing lines
7. Use M3/M5 for pen down/up with appropriate timing
8. Ensure coordinates align with grid system when available

Current Drawing Progress: {progress_info}

Return a JSON object with the next G-code command:
{{"command": "G1", "x": 10.0, "y": 20.0, "f": 2000}}

If drawing is complete, return:
{{"command": "COMPLETE"}}

Generate only the JSON, no additional text.
'''
        
        try:
            self.template_manager.register_template(PromptTemplate(
                name="plot_enhanced_gcode",
                template=plot_gcode_template.strip(),
                required_parameters={
                    "prompt", "plot_context", "grid_info", "history", 
                    "grid_coordinates", "drawing_strategy", "coordinate_bounds", 
                    "progress_info"
                },
                description="Generate G-code with visual plot context"
            ))
        except ValueError:
            # Template already exists
            pass
        
        # Plot analysis template
        plot_analysis_template = '''
Analyze the current matplotlib plot state and provide drawing recommendations.

Plot Elements Detected:
{plot_elements}

Grid Information:
{grid_info}

Drawing Progress:
{progress_info}

Target Drawing Intent: {prompt}

Provide analysis in JSON format:
{{
    "current_state_summary": "description of current plot state",
    "progress_assessment": "assessment of drawing progress",
    "next_action_recommendation": "recommended next drawing action",
    "coordinate_suggestions": [
        {{"x": 10.0, "y": 20.0, "reason": "explanation"}}
    ],
    "strategy_recommendation": "orthogonal|non_orthogonal",
    "completion_estimate": "percentage or description"
}}
'''
        
        try:
            self.template_manager.register_template(PromptTemplate(
                name="plot_analysis",
                template=plot_analysis_template.strip(),
                required_parameters={
                    "plot_elements", "grid_info", "progress_info", "prompt"
                },
                description="Analyze plot state and provide recommendations"
            ))
        except ValueError:
            # Template already exists
            pass
    
    def add_plot_context(self, figure: matplotlib.figure.Figure, 
                        target_gcode: Optional[GCodeProgram] = None) -> PlotContext:
        """
        Add matplotlib figure as visual context
        
        Args:
            figure: Matplotlib figure to analyze
            target_gcode: Optional target G-code for progress analysis
            
        Returns:
            Plot context extracted from figure
        """
        # Capture plot state
        plot_state = self.plot_analyzer.capture_plot_state(figure, include_grid_analysis=True)
        
        # Analyze drawing progress
        drawing_progress = None
        if target_gcode:
            drawing_progress = self.plot_analyzer.analyze_drawing_progress(
                plot_state, target_gcode
            )
        
        # Extract grid coordinates for key plot elements
        grid_coordinates = []
        if plot_state.grid_info:
            for element in plot_state.elements:
                for coord in element.coordinates:
                    grid_coord = self.plot_analyzer.get_grid_coordinates(plot_state, coord)
                    if grid_coord:
                        grid_coordinates.append(grid_coord)
        
        # Calculate coordinate bounds
        coordinate_bounds = plot_state.bounds
        
        # Extract visual features
        visual_features = {
            "element_count": len(plot_state.elements),
            "element_types": [elem.element_type.value for elem in plot_state.elements],
            "has_grid": plot_state.grid_info is not None,
            "figure_size": plot_state.figure_size,
            "drawing_area": coordinate_bounds
        }
        
        # Create plot context
        plot_context = PlotContext(
            plot_state=plot_state,
            drawing_progress=drawing_progress,
            grid_coordinates=grid_coordinates,
            visual_features=visual_features,
            coordinate_bounds=coordinate_bounds
        )
        
        # Add to history
        self._plot_history.append(plot_context)
        
        # Maintain history limit
        if len(self._plot_history) > self.max_plot_history:
            self._plot_history.pop(0)
        
        self.logger.info(f"Added plot context with {len(plot_state.elements)} elements")
        return plot_context
    
    def add_command_to_history(self, command: GCodeCommand) -> None:
        """Add G-code command to history for context"""
        self._command_history.append(command)
        
        # Maintain reasonable history size
        if len(self._command_history) > 50:
            self._command_history.pop(0)
    
    def _figure_to_base64(self, figure: matplotlib.figure.Figure) -> str:
        """Convert matplotlib figure to base64 encoded image"""
        buffer = io.BytesIO()
        figure.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_data = buffer.getvalue()
        buffer.close()
        
        return base64.b64encode(image_data).decode('utf-8')
    
    def _create_plot_context_description(self, plot_context: PlotContext) -> str:
        """Create textual description of plot context"""
        plot_state = plot_context.plot_state
        
        description_parts = [
            f"Plot Elements: {len(plot_state.elements)} total",
            f"Element Types: {', '.join(set(elem.element_type.value for elem in plot_state.elements))}"
        ]
        
        if plot_state.grid_info:
            grid = plot_state.grid_info
            description_parts.extend([
                f"Grid System: X({grid.x_min:.2f} to {grid.x_max:.2f}), Y({grid.y_min:.2f} to {grid.y_max:.2f})",
                f"Grid Steps: X={grid.x_step}, Y={grid.y_step}" if grid.x_step and grid.y_step else "Grid Steps: Variable"
            ])
        
        if plot_context.drawing_progress:
            progress = plot_context.drawing_progress
            description_parts.extend([
                f"Drawing Progress: {progress.progress_percentage:.1f}% complete",
                f"Elements: {progress.completed_elements}/{progress.total_elements}"
            ])
            
            if progress.current_position:
                x, y = progress.current_position
                description_parts.append(f"Current Position: ({x:.{self.coordinate_precision}f}, {y:.{self.coordinate_precision}f})")
        
        if plot_context.coordinate_bounds:
            bounds = plot_context.coordinate_bounds
            description_parts.append(
                f"Coordinate Bounds: X({bounds.get('min_x', 'N/A')} to {bounds.get('max_x', 'N/A')}), "
                f"Y({bounds.get('min_y', 'N/A')} to {bounds.get('max_y', 'N/A')})"
            )
        
        return "\n".join(description_parts)
    
    def _format_grid_coordinates(self, grid_coordinates: List[Tuple[int, int]]) -> str:
        """Format grid coordinates for prompt context"""
        if not grid_coordinates:
            return "No grid coordinates available"
        
        # Limit to most recent/relevant coordinates
        recent_coords = grid_coordinates[-10:] if len(grid_coordinates) > 10 else grid_coordinates
        coord_strs = [f"({x}, {y})" for x, y in recent_coords]
        
        return f"Recent grid positions: {', '.join(coord_strs)}"
    
    def _format_command_history(self, commands: List[GCodeCommand], max_commands: int = 10) -> str:
        """Format command history for prompt context"""
        if not commands:
            return "No previous commands"
        
        recent_commands = commands[-max_commands:] if len(commands) > max_commands else commands
        command_strs = []
        
        for i, cmd in enumerate(recent_commands, 1):
            cmd_str = f"{i}. {cmd.to_gcode()}"
            if cmd.strategy_type:
                cmd_str += f" (strategy: {cmd.strategy_type.value})"
            command_strs.append(cmd_str)
        
        return "\n".join(command_strs)
    
    async def generate_with_visual_context(
        self,
        prompt: str,
        figures: Optional[List[matplotlib.figure.Figure]] = None,
        target_strategy: Optional[DrawingStrategy] = None,
        use_multimodal: bool = True
    ) -> str:
        """
        Generate G-code using LlamaIndex ChatMessage with ImageBlock
        
        Args:
            prompt: Text prompt for drawing generation
            figures: Optional matplotlib figures for visual context
            target_strategy: Optional target drawing strategy
            use_multimodal: Whether to use multi-modal prompts with images
            
        Returns:
            Generated G-code command as JSON string
        """
        try:
            # Process figures if provided
            plot_contexts = []
            if figures:
                for figure in figures:
                    plot_context = self.add_plot_context(figure)
                    plot_contexts.append(plot_context)
            else:
                # Use existing plot history
                plot_contexts = self._plot_history[-3:] if self._plot_history else []
            
            # Create visual prompt context
            visual_context = VisualPromptContext(
                text_prompt=prompt,
                plot_contexts=plot_contexts,
                command_history=self._command_history.copy(),
                target_strategy=target_strategy,
                grid_reference=plot_contexts[0].plot_state.grid_info if plot_contexts else None
            )
            
            if use_multimodal and figures and hasattr(self.base_llm.llm, 'chat'):
                # Use multi-modal approach with LlamaIndex ChatMessage
                return await self._generate_multimodal(visual_context, figures)
            else:
                # Use text-only approach with plot descriptions
                return await self._generate_text_only(visual_context)
                
        except Exception as e:
            self.logger.error(f"Error in visual context generation: {str(e)}")
            raise LLMProviderError(
                f"Visual context generation failed: {str(e)}",
                self.base_llm.provider_name,
                {"prompt": prompt, "figures_count": len(figures) if figures else 0}
            )
    
    async def _generate_multimodal(
        self,
        visual_context: VisualPromptContext,
        figures: List[matplotlib.figure.Figure]
    ) -> str:
        """Generate using multi-modal LlamaIndex ChatMessage with ImageBlock"""
        
        # Build text context
        text_blocks = [TextBlock(text=visual_context.text_prompt)]
        
        # Add plot context descriptions
        if visual_context.plot_contexts:
            context_descriptions = []
            for i, plot_context in enumerate(visual_context.plot_contexts):
                desc = self._create_plot_context_description(plot_context)
                context_descriptions.append(f"Plot Context {i+1}:\n{desc}")
            
            plot_context_text = "\n\n".join(context_descriptions)
            text_blocks.append(TextBlock(text=f"\nVisual Context:\n{plot_context_text}"))
        
        # Add command history
        if visual_context.command_history:
            history_text = self._format_command_history(visual_context.command_history)
            text_blocks.append(TextBlock(text=f"\nCommand History:\n{history_text}"))
        
        # Add grid information
        if visual_context.grid_reference:
            grid = visual_context.grid_reference
            grid_text = (
                f"Grid Reference: X({grid.x_min} to {grid.x_max}, step={grid.x_step}), "
                f"Y({grid.y_min} to {grid.y_max}, step={grid.y_step}), Origin={grid.origin}"
            )
            text_blocks.append(TextBlock(text=f"\n{grid_text}"))
        
        # Add image blocks from figures
        for figure in figures:
            try:
                # Convert figure to base64 image
                image_b64 = self._figure_to_base64(figure)
                image_url = f"data:image/png;base64,{image_b64}"
                text_blocks.append(ImageBlock(url=image_url))
            except Exception as e:
                self.logger.warning(f"Failed to convert figure to image: {str(e)}")
        
        # Add generation instructions
        instructions = TextBlock(text="""
Generate the next G-code command based on the text prompt and visual context.
Consider the current plot state, drawing progress, and grid alignment.
Return only a JSON object with the command, no additional text.
""")
        text_blocks.append(instructions)
        
        # Create ChatMessage with mixed content
        message = ChatMessage(role="user", blocks=text_blocks)
        
        # Generate response using chat interface
        try:
            if hasattr(self.base_llm.llm, 'achat'):
                response = await self.base_llm.llm.achat(messages=[message])
                return response.message.content
            else:
                # Fallback to sync chat
                response = self.base_llm.llm.chat(messages=[message])
                return response.message.content
        except Exception as e:
            self.logger.warning(f"Multi-modal generation failed, falling back to text-only: {str(e)}")
            return await self._generate_text_only(visual_context)
    
    async def _generate_text_only(self, visual_context: VisualPromptContext) -> str:
        """Generate using text-only approach with plot descriptions"""
        
        # Prepare template parameters
        template_params = {
            "prompt": visual_context.text_prompt,
            "history": self._format_command_history(visual_context.command_history),
            "drawing_strategy": visual_context.target_strategy.value if visual_context.target_strategy else "auto",
        }
        
        # Add plot context information
        if visual_context.plot_contexts:
            latest_context = visual_context.plot_contexts[-1]
            template_params.update({
                "plot_context": self._create_plot_context_description(latest_context),
                "grid_coordinates": self._format_grid_coordinates(latest_context.grid_coordinates or []),
                "coordinate_bounds": json.dumps(latest_context.coordinate_bounds or {}, indent=2)
            })
            
            if latest_context.drawing_progress:
                progress = latest_context.drawing_progress
                progress_info = (
                    f"Progress: {progress.progress_percentage:.1f}% complete, "
                    f"{progress.completed_elements}/{progress.total_elements} elements"
                )
                if progress.current_position:
                    x, y = progress.current_position
                    progress_info += f", Current position: ({x:.{self.coordinate_precision}f}, {y:.{self.coordinate_precision}f})"
                template_params["progress_info"] = progress_info
            else:
                template_params["progress_info"] = "No progress information available"
        else:
            template_params.update({
                "plot_context": "No visual context available",
                "grid_coordinates": "No grid coordinates available",
                "coordinate_bounds": "{}",
                "progress_info": "No progress information available"
            })
        
        # Add grid information
        if visual_context.grid_reference:
            grid = visual_context.grid_reference
            grid_info = (
                f"Grid bounds: X({grid.x_min} to {grid.x_max}), Y({grid.y_min} to {grid.y_max})\n"
                f"Grid steps: X={grid.x_step}, Y={grid.y_step}\n"
                f"Origin: {grid.origin}"
            )
            template_params["grid_info"] = grid_info
        else:
            template_params["grid_info"] = "No grid information available"
        
        # Format prompt using template
        try:
            formatted_prompt = self.template_manager.format_template(
                "plot_enhanced_gcode", 
                **template_params
            )
        except KeyError:
            # Fallback to basic template if plot-enhanced template not available
            formatted_prompt = self.template_manager.format_template(
                "next_command",
                prompt=visual_context.text_prompt,
                history=template_params["history"]
            )
        
        # Generate response
        return await self.base_llm.acomplete(formatted_prompt)
    
    async def analyze_plot_state(self, 
                                figure: matplotlib.figure.Figure,
                                target_prompt: str) -> Dict[str, Any]:
        """
        Analyze plot state and provide recommendations
        
        Args:
            figure: Matplotlib figure to analyze
            target_prompt: Target drawing intent
            
        Returns:
            Analysis results with recommendations
        """
        # Add plot context
        plot_context = self.add_plot_context(figure)
        
        # Prepare analysis parameters
        plot_elements_desc = []
        for elem in plot_context.plot_state.elements:
            elem_desc = f"{elem.element_type.value}: {len(elem.coordinates)} points"
            if elem.properties:
                key_props = {k: v for k, v in elem.properties.items() 
                           if k in ['color', 'linewidth', 'marker']}
                if key_props:
                    elem_desc += f" ({key_props})"
            plot_elements_desc.append(elem_desc)
        
        template_params = {
            "plot_elements": "\n".join(plot_elements_desc) if plot_elements_desc else "No elements detected",
            "grid_info": (
                f"Grid: X({plot_context.plot_state.grid_info.x_min} to {plot_context.plot_state.grid_info.x_max}), "
                f"Y({plot_context.plot_state.grid_info.y_min} to {plot_context.plot_state.grid_info.y_max})"
                if plot_context.plot_state.grid_info else "No grid information"
            ),
            "progress_info": (
                f"{plot_context.drawing_progress.progress_percentage:.1f}% complete"
                if plot_context.drawing_progress else "No progress information"
            ),
            "prompt": target_prompt
        }
        
        # Generate analysis
        try:
            formatted_prompt = self.template_manager.format_template(
                "plot_analysis",
                **template_params
            )
            
            response = await self.base_llm.acomplete(formatted_prompt)
            
            # Try to parse JSON response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Return structured fallback
                return {
                    "current_state_summary": f"Plot with {len(plot_context.plot_state.elements)} elements",
                    "progress_assessment": template_params["progress_info"],
                    "next_action_recommendation": "Continue with next drawing command",
                    "coordinate_suggestions": [],
                    "strategy_recommendation": "auto",
                    "completion_estimate": "Unknown",
                    "raw_response": response
                }
                
        except Exception as e:
            self.logger.error(f"Plot analysis failed: {str(e)}")
            return {
                "error": str(e),
                "current_state_summary": f"Analysis failed: {str(e)}",
                "progress_assessment": "Unable to assess",
                "next_action_recommendation": "Manual intervention required",
                "coordinate_suggestions": [],
                "strategy_recommendation": "auto",
                "completion_estimate": "Unknown"
            }
    
    def get_plot_history(self) -> List[PlotContext]:
        """Get current plot context history"""
        return self._plot_history.copy()
    
    def get_command_history(self) -> List[GCodeCommand]:
        """Get current command history"""
        return self._command_history.copy()
    
    def clear_context(self) -> None:
        """Clear all context history"""
        self._plot_history.clear()
        self._command_history.clear()
        self.logger.info("Context history cleared")
    
    async def initialize_context_manager(
        self,
        figure: Optional[matplotlib.figure.Figure] = None,
        coordinate_bounds: Optional[Tuple[float, float, float, float]] = None,
        grid_enabled: bool = True,
        validation_level: ValidationLevel = ValidationLevel.BASIC
    ) -> bool:
        """
        Initialize integrated plot context manager
        
        Args:
            figure: Optional matplotlib figure to use
            coordinate_bounds: Optional coordinate bounds (x_min, x_max, y_min, y_max)
            grid_enabled: Whether to enable grid system
            validation_level: Level of plot state validation
            
        Returns:
            True if initialization successful
        """
        if self.plot_context_manager is None:
            # Create context manager with configuration
            config = PlotContextConfig(
                max_history_size=self.max_plot_history * 2,
                validation_level=validation_level,
                coordinate_precision=self.coordinate_precision,
                enable_auto_recovery=True,
                progress_tracking_enabled=True
            )
            
            self.plot_context_manager = PlotContextManager(
                config=config,
                plot_analyzer=self.plot_analyzer
            )
        
        # Initialize the context manager
        success = await self.plot_context_manager.initialize(
            figure=figure,
            coordinate_bounds=coordinate_bounds,
            grid_enabled=grid_enabled
        )
        
        if success:
            self.logger.info("Plot context manager initialized successfully")
        else:
            self.logger.error("Failed to initialize plot context manager")
        
        return success
    
    async def add_command_with_context(self, command: GCodeCommand) -> bool:
        """
        Add command using integrated context management
        
        Args:
            command: G-code command to add
            
        Returns:
            True if command added successfully
        """
        # Add to local history
        self.add_command_to_history(command)
        
        # Add to context manager if available
        if self.plot_context_manager:
            return await self.plot_context_manager.add_command(command)
        
        return True
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get comprehensive context summary"""
        summary = {
            "local_context": {
                "plot_history_count": len(self._plot_history),
                "command_history_count": len(self._command_history)
            }
        }
        
        if self.plot_context_manager:
            summary["context_manager"] = self.plot_context_manager.get_context_summary()
        
        return summary
    
    def save_context(self, output_path: str) -> None:
        """
        Save current context to file for debugging/analysis
        
        Args:
            output_path: Path to save context data
        """
        context_data = {
            "timestamp": time.time(),
            "plot_history_count": len(self._plot_history),
            "command_history_count": len(self._command_history),
            "command_history": [cmd.model_dump() for cmd in self._command_history],
            "plot_contexts": []
        }
        
        # Save plot context metadata (not full plot states due to size)
        for i, plot_context in enumerate(self._plot_history):
            context_summary = {
                "index": i,
                "timestamp": plot_context.timestamp,
                "element_count": len(plot_context.plot_state.elements),
                "visual_features": plot_context.visual_features,
                "coordinate_bounds": plot_context.coordinate_bounds,
                "has_grid": plot_context.plot_state.grid_info is not None,
                "drawing_progress": (
                    plot_context.drawing_progress.model_dump() 
                    if plot_context.drawing_progress else None
                )
            }
            context_data["plot_contexts"].append(context_summary)
        
        # Add context manager data if available
        if self.plot_context_manager:
            context_data["context_manager_summary"] = self.plot_context_manager.get_context_summary()
        
        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(context_data, f, indent=2, default=str)
        
        self.logger.info(f"Context saved to {output_path}")
        
        # Also save context manager data if available
        if self.plot_context_manager:
            context_manager_path = str(output_file).replace('.json', '_context_manager.json')
            asyncio.create_task(self.plot_context_manager.save_context(context_manager_path))