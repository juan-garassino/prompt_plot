"""
Unit tests for file conversion utilities (SVG, G-code, DXF, etc.).
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import json

from promptplot.converters.svg_converter import SVGConverter
from promptplot.converters.gcode_loader import GCodeLoader
from promptplot.converters.dxf_converter import DXFConverter
from promptplot.converters.json_converter import JSONConverter
from promptplot.converters.file_detector import FileDetector
from promptplot.core.models import GCodeCommand, GCodeProgram
from promptplot.core.exceptions import ConversionException
from tests.fixtures.sample_files import (
    get_sample_svg, get_sample_gcode, get_sample_dxf, get_sample_json,
    get_invalid_svg, get_invalid_gcode, get_invalid_dxf
)


class TestFileDetector:
    """Test file format detection."""
    
    @pytest.mark.unit
    def test_detect_by_extension(self):
        """Test file format detection by extension."""
        test_cases = [
            ("test.svg", "svg"),
            ("drawing.gcode", "gcode"),
            ("model.dxf", "dxf"),
            ("data.json", "json"),
            ("plot.hpgl", "hpgl"),
            ("file.nc", "gcode"),  # Alternative G-code extension
            ("unknown.xyz", None)
        ]
        
        detector = FileDetector()
        
        for filename, expected in test_cases:
            result = detector.detect_format(Path(filename))
            assert result == expected
            
    @pytest.mark.unit
    def test_detect_by_content(self, temp_dir):
        """Test file format detection by content."""
        # Create test files with content
        svg_file = temp_dir / "test.txt"  # Wrong extension
        svg_file.write_text(get_sample_svg())
        
        gcode_file = temp_dir / "test.txt"  # Wrong extension
        gcode_file.write_text(get_sample_gcode())
        
        detector = FileDetector()
        
        # Should detect SVG by content despite wrong extension
        assert detector.detect_format(svg_file, check_content=True) == "svg"
        
    @pytest.mark.unit
    def test_supported_formats(self):
        """Test getting list of supported formats."""
        detector = FileDetector()
        formats = detector.get_supported_formats()
        
        expected_formats = ["svg", "gcode", "dxf", "json", "hpgl"]
        for fmt in expected_formats:
            assert fmt in formats
            
    @pytest.mark.unit
    def test_is_supported_format(self):
        """Test checking if format is supported."""
        detector = FileDetector()
        
        assert detector.is_supported("svg") is True
        assert detector.is_supported("gcode") is True
        assert detector.is_supported("unknown") is False


class TestSVGConverter:
    """Test SVG to G-code conversion."""
    
    @pytest.fixture
    def converter(self):
        """Create SVG converter for testing."""
        return SVGConverter()
        
    @pytest.mark.unit
    def test_converter_initialization(self, converter):
        """Test SVG converter initialization."""
        assert converter.resolution > 0
        assert converter.feed_rate > 0
        
    @pytest.mark.unit
    def test_parse_valid_svg(self, converter, temp_dir):
        """Test parsing valid SVG content."""
        svg_file = temp_dir / "test.svg"
        svg_file.write_text(get_sample_svg())
        
        elements = converter.parse_svg(svg_file)
        
        assert len(elements) > 0
        # Should find rectangles, circles, lines, etc.
        element_types = [elem["type"] for elem in elements]
        assert "rect" in element_types
        assert "circle" in element_types
        assert "line" in element_types
        
    @pytest.mark.unit
    def test_parse_invalid_svg(self, converter, temp_dir):
        """Test parsing invalid SVG content."""
        svg_file = temp_dir / "invalid.svg"
        svg_file.write_text(get_invalid_svg())
        
        with pytest.raises(ConversionException):
            converter.parse_svg(svg_file)
            
    @pytest.mark.unit
    def test_convert_rectangle(self, converter):
        """Test converting SVG rectangle to G-code."""
        rect_element = {
            "type": "rect",
            "x": 10.0,
            "y": 10.0,
            "width": 30.0,
            "height": 20.0
        }
        
        commands = converter.convert_element(rect_element)
        
        assert len(commands) > 4  # At least 4 corners plus pen control
        
        # Should include pen down and up
        assert any(cmd.command == "M3" for cmd in commands)
        assert any(cmd.command == "M5" for cmd in commands)
        
        # Should have movement commands for all corners
        move_commands = [cmd for cmd in commands if cmd.command == "G1"]
        assert len(move_commands) >= 4
        
    @pytest.mark.unit
    def test_convert_circle(self, converter):
        """Test converting SVG circle to G-code."""
        circle_element = {
            "type": "circle",
            "cx": 50.0,
            "cy": 25.0,
            "r": 10.0
        }
        
        commands = converter.convert_element(circle_element)
        
        assert len(commands) > 8  # Circle approximated with multiple segments
        
        # All drawing commands should be within circle bounds
        for cmd in commands:
            if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
                distance = ((cmd.x - 50.0)**2 + (cmd.y - 25.0)**2)**0.5
                assert distance <= 10.5  # Radius plus small tolerance
                
    @pytest.mark.unit
    def test_convert_line(self, converter):
        """Test converting SVG line to G-code."""
        line_element = {
            "type": "line",
            "x1": 10.0,
            "y1": 50.0,
            "x2": 90.0,
            "y2": 50.0
        }
        
        commands = converter.convert_element(line_element)
        
        assert len(commands) >= 3  # Move, pen down, draw, pen up
        
        # Should start at (10, 50) and end at (90, 50)
        move_commands = [cmd for cmd in commands if cmd.command == "G1"]
        assert len(move_commands) >= 2
        
    @pytest.mark.unit
    def test_convert_path(self, converter):
        """Test converting SVG path to G-code."""
        path_element = {
            "type": "path",
            "d": "M 20 70 Q 50 60 80 70"  # Quadratic curve
        }
        
        commands = converter.convert_element(path_element)
        
        assert len(commands) > 5  # Curve approximated with multiple segments
        
    @pytest.mark.unit
    def test_full_svg_conversion(self, converter, temp_dir):
        """Test complete SVG file conversion."""
        svg_file = temp_dir / "test.svg"
        svg_file.write_text(get_sample_svg())
        
        program = converter.convert_file(svg_file)
        
        assert isinstance(program, GCodeProgram)
        assert len(program.commands) > 10
        
        # Should start with homing
        assert program.commands[0].command == "G28"
        
        # Should end with homing
        assert program.commands[-1].command == "G28"
        
    @pytest.mark.unit
    def test_svg_scaling(self, converter):
        """Test SVG coordinate scaling."""
        original_scale = converter.scale_factor
        converter.scale_factor = 2.0
        
        rect_element = {
            "type": "rect",
            "x": 10.0,
            "y": 10.0,
            "width": 20.0,
            "height": 20.0
        }
        
        commands = converter.convert_element(rect_element)
        
        # Coordinates should be scaled
        move_commands = [cmd for cmd in commands if cmd.command == "G1" and cmd.x is not None]
        max_x = max(cmd.x for cmd in move_commands)
        max_y = max(cmd.y for cmd in move_commands)
        
        assert max_x >= 60.0  # (10 + 20) * 2
        assert max_y >= 60.0  # (10 + 20) * 2


class TestGCodeLoader:
    """Test G-code file loading and parsing."""
    
    @pytest.fixture
    def loader(self):
        """Create G-code loader for testing."""
        return GCodeLoader()
        
    @pytest.mark.unit
    def test_parse_valid_gcode(self, loader, temp_dir):
        """Test parsing valid G-code file."""
        gcode_file = temp_dir / "test.gcode"
        gcode_file.write_text(get_sample_gcode())
        
        program = loader.load_file(gcode_file)
        
        assert isinstance(program, GCodeProgram)
        assert len(program.commands) > 10
        
        # Should have various command types
        command_types = set(cmd.command for cmd in program.commands)
        assert "G28" in command_types  # Homing
        assert "G1" in command_types   # Linear move
        assert "M3" in command_types   # Pen down
        assert "M5" in command_types   # Pen up
        
    @pytest.mark.unit
    def test_parse_invalid_gcode(self, loader, temp_dir):
        """Test parsing invalid G-code file."""
        gcode_file = temp_dir / "invalid.gcode"
        gcode_file.write_text(get_invalid_gcode())
        
        with pytest.raises(ConversionException):
            loader.load_file(gcode_file)
            
    @pytest.mark.unit
    def test_parse_gcode_line(self, loader):
        """Test parsing individual G-code lines."""
        test_lines = [
            ("G28", {"command": "G28"}),
            ("G1 X10 Y20 F1000", {"command": "G1", "x": 10.0, "y": 20.0, "f": 1000}),
            ("M3 S255", {"command": "M3", "s": 255}),
            ("; This is a comment", None),  # Comments should be ignored
            ("", None),  # Empty lines should be ignored
        ]
        
        for line, expected in test_lines:
            result = loader.parse_line(line)
            
            if expected is None:
                assert result is None
            else:
                assert result is not None
                for key, value in expected.items():
                    assert getattr(result, key) == value
                    
    @pytest.mark.unit
    def test_gcode_validation(self, loader):
        """Test G-code command validation during loading."""
        valid_commands = [
            "G28",
            "G1 X10 Y20 F1000",
            "M3 S255",
            "M5"
        ]
        
        invalid_commands = [
            "INVALID_COMMAND",
            "G1 X Y20",  # Missing X value
            "M3 S",      # Missing S value
        ]
        
        # Valid commands should parse successfully
        for cmd in valid_commands:
            result = loader.parse_line(cmd)
            assert result is not None
            
        # Invalid commands should be handled gracefully or raise errors
        for cmd in invalid_commands:
            with pytest.raises((ConversionException, ValueError)):
                loader.parse_line(cmd)


class TestDXFConverter:
    """Test DXF to G-code conversion."""
    
    @pytest.fixture
    def converter(self):
        """Create DXF converter for testing."""
        return DXFConverter()
        
    @pytest.mark.unit
    def test_parse_valid_dxf(self, converter, temp_dir):
        """Test parsing valid DXF file."""
        dxf_file = temp_dir / "test.dxf"
        dxf_file.write_text(get_sample_dxf())
        
        entities = converter.parse_dxf(dxf_file)
        
        assert len(entities) > 0
        
        # Should find lines and circles
        entity_types = [entity["type"] for entity in entities]
        assert "LINE" in entity_types
        assert "CIRCLE" in entity_types
        
    @pytest.mark.unit
    def test_convert_dxf_line(self, converter):
        """Test converting DXF line entity."""
        line_entity = {
            "type": "LINE",
            "start": (10.0, 10.0),
            "end": (40.0, 30.0)
        }
        
        commands = converter.convert_entity(line_entity)
        
        assert len(commands) >= 3  # Move, pen down, draw, pen up
        
        # Should include movement to start and end points
        move_commands = [cmd for cmd in commands if cmd.command == "G1"]
        assert any(cmd.x == 10.0 and cmd.y == 10.0 for cmd in move_commands)
        assert any(cmd.x == 40.0 and cmd.y == 30.0 for cmd in move_commands)
        
    @pytest.mark.unit
    def test_convert_dxf_circle(self, converter):
        """Test converting DXF circle entity."""
        circle_entity = {
            "type": "CIRCLE",
            "center": (70.0, 25.0),
            "radius": 10.0
        }
        
        commands = converter.convert_entity(circle_entity)
        
        assert len(commands) > 8  # Circle with multiple segments
        
        # All points should be within circle bounds
        for cmd in commands:
            if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
                distance = ((cmd.x - 70.0)**2 + (cmd.y - 25.0)**2)**0.5
                assert distance <= 10.5  # Radius plus tolerance
                
    @pytest.mark.unit
    def test_full_dxf_conversion(self, converter, temp_dir):
        """Test complete DXF file conversion."""
        dxf_file = temp_dir / "test.dxf"
        dxf_file.write_text(get_sample_dxf())
        
        program = converter.convert_file(dxf_file)
        
        assert isinstance(program, GCodeProgram)
        assert len(program.commands) > 5


class TestJSONConverter:
    """Test JSON G-code format conversion."""
    
    @pytest.fixture
    def converter(self):
        """Create JSON converter for testing."""
        return JSONConverter()
        
    @pytest.mark.unit
    def test_parse_valid_json(self, converter, temp_dir):
        """Test parsing valid JSON G-code file."""
        json_file = temp_dir / "test.json"
        json_file.write_text(get_sample_json())
        
        program = converter.load_file(json_file)
        
        assert isinstance(program, GCodeProgram)
        assert len(program.commands) > 0
        
        # Should have metadata
        assert "title" in program.metadata
        assert program.metadata["title"] == "Test Drawing"
        
    @pytest.mark.unit
    def test_convert_to_json(self, converter, sample_gcode_program, temp_dir):
        """Test converting G-code program to JSON."""
        json_file = temp_dir / "output.json"
        
        converter.save_file(sample_gcode_program, json_file)
        
        # Verify file was created and is valid JSON
        assert json_file.exists()
        
        with open(json_file) as f:
            data = json.load(f)
            
        assert "commands" in data
        assert "metadata" in data
        assert len(data["commands"]) == len(sample_gcode_program.commands)
        
    @pytest.mark.unit
    def test_json_roundtrip(self, converter, sample_gcode_program, temp_dir):
        """Test JSON save/load roundtrip."""
        json_file = temp_dir / "roundtrip.json"
        
        # Save program to JSON
        converter.save_file(sample_gcode_program, json_file)
        
        # Load program from JSON
        loaded_program = converter.load_file(json_file)
        
        # Should be equivalent
        assert len(loaded_program.commands) == len(sample_gcode_program.commands)
        for orig, loaded in zip(sample_gcode_program.commands, loaded_program.commands):
            assert orig.command == loaded.command
            assert orig.x == loaded.x
            assert orig.y == loaded.y


class TestFileConversionIntegration:
    """Test file conversion integration scenarios."""
    
    @pytest.mark.unit
    def test_detect_and_convert_workflow(self, temp_dir):
        """Test complete detect and convert workflow."""
        # Create test files
        svg_file = temp_dir / "test.svg"
        svg_file.write_text(get_sample_svg())
        
        gcode_file = temp_dir / "test.gcode"
        gcode_file.write_text(get_sample_gcode())
        
        # Detect formats
        detector = FileDetector()
        assert detector.detect_format(svg_file) == "svg"
        assert detector.detect_format(gcode_file) == "gcode"
        
        # Convert files
        svg_converter = SVGConverter()
        svg_program = svg_converter.convert_file(svg_file)
        assert isinstance(svg_program, GCodeProgram)
        
        gcode_loader = GCodeLoader()
        gcode_program = gcode_loader.load_file(gcode_file)
        assert isinstance(gcode_program, GCodeProgram)
        
    @pytest.mark.unit
    def test_conversion_error_handling(self, temp_dir):
        """Test error handling in file conversion."""
        # Non-existent file
        missing_file = temp_dir / "missing.svg"
        
        converter = SVGConverter()
        with pytest.raises(ConversionException):
            converter.convert_file(missing_file)
            
        # Invalid file content
        invalid_file = temp_dir / "invalid.svg"
        invalid_file.write_text("Not valid SVG content")
        
        with pytest.raises(ConversionException):
            converter.convert_file(invalid_file)
            
    @pytest.mark.unit
    def test_batch_conversion(self, temp_dir):
        """Test converting multiple files."""
        # Create multiple test files
        files = []
        for i in range(3):
            svg_file = temp_dir / f"test_{i}.svg"
            svg_file.write_text(get_sample_svg())
            files.append(svg_file)
            
        converter = SVGConverter()
        programs = []
        
        for file in files:
            program = converter.convert_file(file)
            programs.append(program)
            
        assert len(programs) == 3
        for program in programs:
            assert isinstance(program, GCodeProgram)
            assert len(program.commands) > 0