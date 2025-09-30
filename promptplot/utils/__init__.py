"""
Utility components for PromptPlot v2.0.

This module provides logging, validation, file operations, mathematical
calculations, and SVG path processing utilities.
"""

# Import logging utilities
from .logging import (
    get_logger,
    set_log_level,
    add_log_file,
    configure_logging,
    log_workflow_start,
    log_workflow_complete,
    log_plotter_command,
    log_llm_request,
    log_error,
    LogLevel,
    LogFormat
)

# Import validation utilities
from .validation import (
    validate_gcode_command,
    validate_gcode_program,
    validate_coordinates,
    validate_file,
    validate_json_gcode,
    is_valid_gcode_command,
    sanitize_coordinate,
    sanitize_integer_parameter,
    ValidationResult,
    ValidationLevel,
    CoordinateValidator,
    GCodeValidator,
    FileValidator,
    ConfigValidator
)

# Import file helpers
from .file_helpers import (
    detect_file_type,
    ensure_directory,
    safe_filename,
    generate_timestamp_filename,
    read_file_safe,
    write_file_safe,
    copy_file_safe,
    move_file_safe,
    delete_file_safe,
    get_file_info,
    calculate_file_hash,
    find_files,
    cleanup_temp_files,
    archive_old_files,
    batch_rename_files,
    FileType,
    FileOperation
)

# Import math helpers
from .math_helpers import (
    Point2D,
    Point3D,
    BoundingBox,
    calculate_distance,
    calculate_path_length,
    calculate_bounding_box,
    rotate_point,
    scale_point,
    translate_point,
    transform_path,
    interpolate_points,
    simplify_path,
    optimize_path_order,
    calculate_curve_points,
    calculate_circle_points,
    fit_circle_to_points,
    calculate_angle,
    normalize_angle,
    degrees_to_radians,
    radians_to_degrees,
    CoordinateSystem,
    DistanceMetric
)

# Import path helpers
from .path_helpers import (
    parse_svg_path,
    svg_path_to_coordinates,
    extract_paths_from_svg_content,
    calculate_path_bounds,
    PathCommand,
    PathSegment,
    ParsedPath,
    SVGPathParser,
    PathOptimizer
)

__all__ = [
    # Logging utilities
    'get_logger',
    'set_log_level',
    'add_log_file',
    'configure_logging',
    'log_workflow_start',
    'log_workflow_complete',
    'log_plotter_command',
    'log_llm_request',
    'log_error',
    'LogLevel',
    'LogFormat',
    
    # Validation utilities
    'validate_gcode_command',
    'validate_gcode_program',
    'validate_coordinates',
    'validate_file',
    'validate_json_gcode',
    'is_valid_gcode_command',
    'sanitize_coordinate',
    'sanitize_integer_parameter',
    'ValidationResult',
    'ValidationLevel',
    'CoordinateValidator',
    'GCodeValidator',
    'FileValidator',
    'ConfigValidator',
    
    # File helpers
    'detect_file_type',
    'ensure_directory',
    'safe_filename',
    'generate_timestamp_filename',
    'read_file_safe',
    'write_file_safe',
    'copy_file_safe',
    'move_file_safe',
    'delete_file_safe',
    'get_file_info',
    'calculate_file_hash',
    'find_files',
    'cleanup_temp_files',
    'archive_old_files',
    'batch_rename_files',
    'FileType',
    'FileOperation',
    
    # Math helpers
    'Point2D',
    'Point3D',
    'BoundingBox',
    'calculate_distance',
    'calculate_path_length',
    'calculate_bounding_box',
    'rotate_point',
    'scale_point',
    'translate_point',
    'transform_path',
    'interpolate_points',
    'simplify_path',
    'optimize_path_order',
    'calculate_curve_points',
    'calculate_circle_points',
    'fit_circle_to_points',
    'calculate_angle',
    'normalize_angle',
    'degrees_to_radians',
    'radians_to_degrees',
    'CoordinateSystem',
    'DistanceMetric',
    
    # Path helpers
    'parse_svg_path',
    'svg_path_to_coordinates',
    'extract_paths_from_svg_content',
    'calculate_path_bounds',
    'PathCommand',
    'PathSegment',
    'ParsedPath',
    'SVGPathParser',
    'PathOptimizer'
]