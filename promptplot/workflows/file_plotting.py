"""
File plotting workflow for direct execution of various file formats

This workflow handles the conversion and plotting of files without LLM generation,
supporting G-code, SVG, and other formats with automatic format detection.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Union, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ..core.models import GCodeProgram, WorkflowResult
from ..core.exceptions import PromptPlotException
from ..converters import (
    GCodeLoader, SVGConverter, DXFConverter, HPGLConverter, 
    JSONConverter, ImageConverter, FileFormatDetector, SupportedFormat
)
from ..plotter.base import BasePlotter
from ..config import get_config


class PlottingMode(str, Enum):
    """File plotting modes"""
    PREVIEW = "preview"
    VALIDATE = "validate"
    EXECUTE = "execute"
    BATCH = "batch"


@dataclass
class PlottingParameters:
    """Parameters for file plotting"""
    speed: Optional[int] = None  # Feed rate override
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)  # X, Y, Z scaling
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # X, Y, Z offset
    rotation: float = 0.0  # Rotation in degrees
    optimize: bool = True  # Enable optimization
    pen_up_command: str = "M5"
    pen_down_command: str = "M3"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata"""
        return {
            'speed': self.speed,
            'scale': self.scale,
            'offset': self.offset,
            'rotation': self.rotation,
            'optimize': self.optimize,
            'pen_up_command': self.pen_up_command,
            'pen_down_command': self.pen_down_command
        }


@dataclass
class FileInfo:
    """Information about a file to be plotted"""
    filepath: Path
    format: SupportedFormat
    size_bytes: int
    supported: bool
    converter_class: Optional[str] = None
    estimated_commands: Optional[int] = None
    estimated_time: Optional[float] = None  # in seconds
    bounds: Optional[Dict[str, float]] = None


class FilePlottingError(PromptPlotException):
    """Exception raised during file plotting operations"""
    pass


class FilePlottingWorkflow:
    """
    Unified workflow for plotting various file formats
    """
    
    def __init__(self, plotter: Optional[BasePlotter] = None):
        """
        Initialize file plotting workflow with configuration integration
        
        Args:
            plotter: Plotter instance for execution (optional for preview/validation)
        """
        # Get configuration
        self.config = get_config()
        
        # Use provided plotter or create from config
        if plotter is None:
            from ..plotter import SerialPlotter, SimulatedPlotter
            plotter_config = self.config.plotter
            if plotter_config.default_type == "serial":
                plotter = SerialPlotter(
                    port=plotter_config.serial_port,
                    baud_rate=plotter_config.serial_baud_rate
                )
            else:  # simulated
                plotter = SimulatedPlotter(
                    port="SIMULATED",
                    visualize=True
                )
        
        self.plotter = plotter
        self.file_detector = FileFormatDetector()
        self.gcode_loader = GCodeLoader()
        self.svg_converter = SVGConverter()
        self.dxf_converter = DXFConverter()
        self.hpgl_converter = HPGLConverter()
        self.json_converter = JSONConverter()
        self.image_converter = ImageConverter()
        
    async def plot_file(
        self, 
        filepath: Union[str, Path], 
        mode: PlottingMode = PlottingMode.EXECUTE,
        parameters: Optional[PlottingParameters] = None
    ) -> WorkflowResult:
        """
        Plot a single file
        
        Args:
            filepath: Path to file to plot
            mode: Plotting mode (preview, validate, execute)
            parameters: Plotting parameters
            
        Returns:
            WorkflowResult with execution details
        """
        filepath = Path(filepath)
        parameters = parameters or PlottingParameters()
        
        # Analyze file
        file_info = await self._analyze_file(filepath)
        
        if not file_info.supported:
            raise FilePlottingError(f"Unsupported file format: {file_info.format}")
            
        # Convert to G-code program
        program = await self._convert_file(filepath, file_info, parameters)
        
        # Execute based on mode
        if mode == PlottingMode.PREVIEW:
            return await self._preview_program(program, file_info, parameters)
        elif mode == PlottingMode.VALIDATE:
            return await self._validate_program(program, file_info, parameters)
        elif mode == PlottingMode.EXECUTE:
            return await self._execute_program(program, file_info, parameters)
        else:
            raise FilePlottingError(f"Unknown plotting mode: {mode}")
            
    async def plot_files_batch(
        self,
        filepaths: List[Union[str, Path]],
        mode: PlottingMode = PlottingMode.EXECUTE,
        parameters: Optional[PlottingParameters] = None
    ) -> List[WorkflowResult]:
        """
        Plot multiple files in batch
        
        Args:
            filepaths: List of file paths to plot
            mode: Plotting mode
            parameters: Plotting parameters
            
        Returns:
            List of WorkflowResult objects
        """
        results = []
        parameters = parameters or PlottingParameters()
        
        for filepath in filepaths:
            try:
                result = await self.plot_file(filepath, mode, parameters)
                results.append(result)
            except Exception as e:
                # Create error result for failed files
                error_result = WorkflowResult(
                    success=False,
                    prompt=f"File: {filepath}",
                    commands_count=0,
                    gcode="",
                    timestamp=self._get_timestamp(),
                    error_message=str(e),
                    metadata={'filepath': str(filepath), 'batch_mode': True}
                )
                results.append(error_result)
                
        return results
        
    async def _analyze_file(self, filepath: Path) -> FileInfo:
        """Analyze a file and determine its properties"""
        if not filepath.exists():
            raise FilePlottingError(f"File not found: {filepath}")
            
        # Detect format
        file_format = self.file_detector.detect_format(filepath)
        file_info_dict = self.file_detector.get_file_info(filepath)
        
        # Create file info
        file_info = FileInfo(
            filepath=filepath,
            format=file_format,
            size_bytes=file_info_dict['size_bytes'],
            supported=file_info_dict['supported'],
            converter_class=file_info_dict['converter_class']
        )
        
        # Estimate properties for supported formats
        if file_info.supported:
            try:
                if file_format == SupportedFormat.GCODE:
                    # Quick analysis of G-code file
                    program, gcode_info = self.gcode_loader.load_file(filepath)
                    file_info.estimated_commands = len(program.commands)
                    file_info.bounds = program.get_bounds()
                    file_info.estimated_time = self._estimate_plotting_time(program)
                    
                elif file_format == SupportedFormat.SVG:
                    # Quick analysis of SVG file
                    program = self.svg_converter.convert_file(filepath)
                    file_info.estimated_commands = len(program.commands)
                    file_info.bounds = program.get_bounds()
                    file_info.estimated_time = self._estimate_plotting_time(program)
                    
                elif file_format == SupportedFormat.DXF:
                    # Quick analysis of DXF file
                    program = self.dxf_converter.convert_file(filepath)
                    file_info.estimated_commands = len(program.commands)
                    file_info.bounds = program.get_bounds()
                    file_info.estimated_time = self._estimate_plotting_time(program)
                    
                elif file_format == SupportedFormat.HPGL:
                    # Quick analysis of HPGL file
                    program = self.hpgl_converter.convert_file(filepath)
                    file_info.estimated_commands = len(program.commands)
                    file_info.bounds = program.get_bounds()
                    file_info.estimated_time = self._estimate_plotting_time(program)
                    
                elif file_format == SupportedFormat.JSON:
                    # Quick analysis of JSON file
                    program = self.json_converter.convert_file(filepath)
                    file_info.estimated_commands = len(program.commands)
                    file_info.bounds = program.get_bounds()
                    file_info.estimated_time = self._estimate_plotting_time(program)
                    
            except Exception as e:
                # If analysis fails, file is probably not supported
                file_info.supported = False
                
        return file_info
        
    async def _convert_file(
        self, 
        filepath: Path, 
        file_info: FileInfo, 
        parameters: PlottingParameters
    ) -> GCodeProgram:
        """Convert file to G-code program"""
        
        if file_info.format == SupportedFormat.GCODE:
            # Load G-code file
            program, _ = self.gcode_loader.load_file(filepath)
            
        elif file_info.format == SupportedFormat.SVG:
            # Convert SVG to G-code
            converter = SVGConverter(
                feed_rate=parameters.speed or 1000,
                pen_up_command=parameters.pen_up_command,
                pen_down_command=parameters.pen_down_command
            )
            program = converter.convert_file(filepath)
            
        elif file_info.format == SupportedFormat.DXF:
            # Convert DXF to G-code
            converter = DXFConverter(
                feed_rate=parameters.speed or 1000,
                pen_up_command=parameters.pen_up_command,
                pen_down_command=parameters.pen_down_command
            )
            program = converter.convert_file(filepath)
            
        elif file_info.format == SupportedFormat.HPGL:
            # Convert HPGL to G-code
            converter = HPGLConverter(
                feed_rate=parameters.speed or 1000,
                pen_up_command=parameters.pen_up_command,
                pen_down_command=parameters.pen_down_command
            )
            program = converter.convert_file(filepath)
            
        elif file_info.format == SupportedFormat.JSON:
            # Convert JSON to G-code
            converter = JSONConverter(
                feed_rate=parameters.speed or 1000,
                pen_up_command=parameters.pen_up_command,
                pen_down_command=parameters.pen_down_command
            )
            program = converter.convert_file(filepath)
            
        elif file_info.format == SupportedFormat.IMAGE:
            # Convert Image to G-code
            converter = ImageConverter(
                feed_rate=parameters.speed or 1000,
                pen_up_command=parameters.pen_up_command,
                pen_down_command=parameters.pen_down_command
            )
            program = converter.convert_file(filepath)
            
        else:
            raise FilePlottingError(f"No converter available for format: {file_info.format}")
            
        # Apply transformations if specified
        if (parameters.scale != (1.0, 1.0, 1.0) or 
            parameters.offset != (0.0, 0.0, 0.0) or 
            parameters.rotation != 0.0):
            
            from ..converters.gcode_loader import GCodeProcessor
            processor = GCodeProcessor()
            program = processor.transform_coordinates(
                program,
                scale=parameters.scale,
                offset=parameters.offset,
                rotation=parameters.rotation
            )
            
        # Apply optimization if enabled
        if parameters.optimize:
            if file_info.format == SupportedFormat.SVG:
                program = self.svg_converter.optimize_pen_movements(program)
            else:
                from ..converters.gcode_loader import GCodeProcessor
                processor = GCodeProcessor()
                program = processor.optimize_program(program)
                
        return program
        
    async def _preview_program(
        self, 
        program: GCodeProgram, 
        file_info: FileInfo, 
        parameters: PlottingParameters
    ) -> WorkflowResult:
        """Generate preview of the program without executing"""
        
        # Calculate statistics
        movement_commands = program.get_movement_commands()
        drawing_commands = program.get_drawing_commands()
        bounds = program.get_bounds()
        
        # Create preview metadata
        preview_metadata = {
            'mode': 'preview',
            'source_file': str(file_info.filepath),
            'file_format': file_info.format,
            'file_size_bytes': file_info.size_bytes,
            'total_commands': len(program.commands),
            'movement_commands': len(movement_commands),
            'drawing_commands': len(drawing_commands),
            'bounds': bounds,
            'estimated_time_seconds': self._estimate_plotting_time(program),
            'parameters': parameters.to_dict()
        }
        
        return WorkflowResult(
            success=True,
            prompt=f"Preview of {file_info.filepath.name}",
            commands_count=len(program.commands),
            gcode=program.to_gcode(),
            program=program,
            timestamp=self._get_timestamp(),
            metadata=preview_metadata
        )
        
    async def _validate_program(
        self, 
        program: GCodeProgram, 
        file_info: FileInfo, 
        parameters: PlottingParameters
    ) -> WorkflowResult:
        """Validate the program for safety and correctness"""
        
        validation_errors = []
        warnings = []
        
        # Check bounds
        bounds = program.get_bounds()
        if bounds:
            # Check for reasonable bounds (customize these limits as needed)
            max_x = bounds.get('max_x', 0)
            max_y = bounds.get('max_y', 0)
            min_x = bounds.get('min_x', 0)
            min_y = bounds.get('min_y', 0)
            
            if max_x > 300 or max_y > 300:  # 300mm limit
                warnings.append(f"Large drawing area: {max_x:.1f}x{max_y:.1f}mm")
                
            if min_x < 0 or min_y < 0:
                validation_errors.append(f"Negative coordinates: min_x={min_x:.1f}, min_y={min_y:.1f}")
                
        # Check for valid command sequence
        pen_commands = program.get_pen_commands()
        if not pen_commands:
            warnings.append("No pen control commands found")
            
        # Check for excessive commands
        if len(program.commands) > 10000:
            warnings.append(f"Large number of commands: {len(program.commands)}")
            
        # Create validation metadata
        validation_metadata = {
            'mode': 'validation',
            'source_file': str(file_info.filepath),
            'validation_errors': validation_errors,
            'warnings': warnings,
            'bounds': bounds,
            'command_counts': program.count_by_command_type(),
            'parameters': parameters.to_dict()
        }
        
        success = len(validation_errors) == 0
        error_message = None if success else "; ".join(validation_errors)
        
        return WorkflowResult(
            success=success,
            prompt=f"Validation of {file_info.filepath.name}",
            commands_count=len(program.commands),
            gcode=program.to_gcode(),
            program=program,
            timestamp=self._get_timestamp(),
            error_message=error_message,
            metadata=validation_metadata
        )
        
    async def _execute_program(
        self, 
        program: GCodeProgram, 
        file_info: FileInfo, 
        parameters: PlottingParameters
    ) -> WorkflowResult:
        """Execute the program on the plotter"""
        
        if not self.plotter:
            raise FilePlottingError("No plotter configured for execution")
            
        # First validate the program
        validation_result = await self._validate_program(program, file_info, parameters)
        if not validation_result.success:
            return validation_result
            
        # Execute commands
        executed_commands = 0
        execution_errors = []
        
        try:
            async with self.plotter:
                for i, command in enumerate(program.commands):
                    try:
                        gcode_str = command.to_gcode()
                        success = await self.plotter.send_command(gcode_str)
                        
                        if success:
                            executed_commands += 1
                        else:
                            execution_errors.append(f"Command {i+1} failed: {gcode_str}")
                            
                        # Add small delay between commands
                        await asyncio.sleep(0.01)
                        
                    except Exception as e:
                        execution_errors.append(f"Command {i+1} error: {e}")
                        
        except Exception as e:
            execution_errors.append(f"Plotter connection error: {e}")
            
        # Create execution metadata
        execution_metadata = {
            'mode': 'execution',
            'source_file': str(file_info.filepath),
            'executed_commands': executed_commands,
            'total_commands': len(program.commands),
            'execution_errors': execution_errors,
            'success_rate': executed_commands / len(program.commands) if program.commands else 0,
            'parameters': parameters.to_dict()
        }
        
        success = len(execution_errors) == 0
        error_message = None if success else f"{len(execution_errors)} execution errors"
        
        return WorkflowResult(
            success=success,
            prompt=f"Execution of {file_info.filepath.name}",
            commands_count=executed_commands,
            gcode=program.to_gcode(),
            program=program,
            timestamp=self._get_timestamp(),
            error_message=error_message,
            metadata=execution_metadata
        )
        
    def _estimate_plotting_time(self, program: GCodeProgram) -> float:
        """Estimate plotting time in seconds"""
        # Simple estimation based on command count and movement distance
        drawing_commands = program.get_drawing_commands()
        movement_commands = program.get_movement_commands()
        
        # Estimate based on typical feed rates and distances
        estimated_time = 0.0
        
        # Time for drawing commands (slower)
        estimated_time += len(drawing_commands) * 0.1  # 0.1 seconds per drawing command
        
        # Time for movement commands (faster)
        estimated_time += len(movement_commands) * 0.05  # 0.05 seconds per movement
        
        # Add pen up/down time
        pen_commands = program.get_pen_commands()
        estimated_time += len(pen_commands) * 0.2  # 0.2 seconds per pen command
        
        return estimated_time
        
    def _get_timestamp(self) -> str:
        """Get current timestamp string"""
        from datetime import datetime
        return datetime.now().isoformat()
        
    def get_supported_formats(self) -> List[SupportedFormat]:
        """Get list of supported file formats"""
        return [
            SupportedFormat.GCODE,
            SupportedFormat.SVG,
            SupportedFormat.DXF,
            SupportedFormat.HPGL,
            SupportedFormat.JSON,
            SupportedFormat.IMAGE
        ]
        
    def get_file_info(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """Get information about a file without full analysis"""
        return self.file_detector.get_file_info(Path(filepath))  
  
    async def validate_file(self, filepath: Union[str, Path], file_format: Optional[SupportedFormat] = None):
        """Validate a file for plotting
        
        Args:
            filepath: Path to file to validate
            file_format: Optional file format (auto-detected if None)
            
        Returns:
            ValidationResult with validation status and details
        """
        from ..utils.validation import ValidationResult, validate_file, validate_gcode_program
        
        file_path = Path(filepath)
        
        # Basic file validation
        file_result = validate_file(file_path)
        if not file_result.is_valid:
            return file_result
        
        # Detect format if not provided
        if file_format is None:
            file_format = self.file_detector.detect_format(file_path)
        
        result = ValidationResult(True, [], [], [])
        result.metadata = {}
        
        try:
            # Format-specific validation
            if file_format == SupportedFormat.GCODE:
                # Validate G-code content
                program, _ = self.gcode_loader.load_file(file_path)
                gcode_result = validate_gcode_program(program.commands)
                result = result.merge(gcode_result)
                
                # Add metadata
                result.metadata = {
                    'format': file_format.value,
                    'commands': len(program.commands),
                    'bounds': program.get_bounds() if hasattr(program, 'get_bounds') else None,
                    'estimated_time': self._estimate_plotting_time(program)
                }
                
            elif file_format == SupportedFormat.SVG:
                # Validate SVG content
                try:
                    program = self.svg_converter.convert_file(file_path)
                    result.add_suggestion("SVG file converted successfully")
                    result.metadata = {
                        'format': file_format.value,
                        'commands': len(program.commands),
                        'estimated_time': self._estimate_plotting_time(program)
                    }
                except Exception as e:
                    result.add_error(f"SVG conversion failed: {e}")
                    
            elif file_format == SupportedFormat.DXF:
                # Validate DXF content
                try:
                    program = self.dxf_converter.convert_file(file_path)
                    result.add_suggestion("DXF file converted successfully")
                    result.metadata = {
                        'format': file_format.value,
                        'commands': len(program.commands),
                        'estimated_time': self._estimate_plotting_time(program)
                    }
                except Exception as e:
                    result.add_error(f"DXF conversion failed: {e}")
                    
            elif file_format == SupportedFormat.JSON:
                # Validate JSON G-code content
                from ..utils.validation import validate_json_gcode
                content = file_path.read_text()
                json_result = validate_json_gcode(content)
                result = result.merge(json_result)
                
                if result.is_valid:
                    result.metadata = {
                        'format': file_format.value,
                        'content_type': 'json_gcode'
                    }
                    
            elif file_format == SupportedFormat.UNKNOWN:
                result.add_error("Unknown or unsupported file format")
                
            else:
                result.add_warning(f"Limited validation for format: {file_format.value}")
                result.metadata = {'format': file_format.value}
                
        except Exception as e:
            result.add_error(f"Validation error: {e}")
        
        return result