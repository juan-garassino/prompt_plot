"""
Unit tests for drawing strategy selection and implementation.
"""
import pytest
from unittest.mock import Mock, patch

from promptplot.strategies.selector import StrategySelector, PromptComplexity, ComplexityLevel
from promptplot.strategies.orthogonal import OrthogonalStrategy
from promptplot.strategies.non_orthogonal import NonOrthogonalStrategy
from promptplot.core.models import GCodeCommand
from tests.utils.mocks import MockStrategySelector


class TestPromptComplexity:
    """Test PromptComplexity data class."""
    
    @pytest.mark.unit
    def test_create_complexity(self):
        """Test creating PromptComplexity object."""
        from promptplot.core.models import DrawingStrategy
        
        complexity = PromptComplexity(
            drawing_type=DrawingStrategy.NON_ORTHOGONAL,
            complexity_level=ComplexityLevel.MODERATE,
            estimated_commands=15,
            requires_curves=True,
            geometric_shapes_count=2,
            organic_shapes_count=3,
            confidence_score=0.7,
            reasoning="Test reasoning"
        )
        
        assert complexity.confidence_score == 0.7
        assert complexity.requires_curves is True
        assert complexity.estimated_commands == 15
        assert complexity.drawing_type == DrawingStrategy.NON_ORTHOGONAL
        assert complexity.complexity_level == ComplexityLevel.MODERATE
        
    @pytest.mark.unit
    def test_complexity_defaults(self):
        """Test PromptComplexity with minimum required fields."""
        from promptplot.core.models import DrawingStrategy
        
        complexity = PromptComplexity(
            drawing_type=DrawingStrategy.ORTHOGONAL,
            complexity_level=ComplexityLevel.SIMPLE,
            estimated_commands=0,
            requires_curves=False,
            geometric_shapes_count=0,
            organic_shapes_count=0,
            confidence_score=0.0,
            reasoning="Default test"
        )
        
        assert complexity.confidence_score == 0.0
        assert complexity.requires_curves is False
        assert complexity.estimated_commands == 0
        assert complexity.drawing_type == DrawingStrategy.ORTHOGONAL


class TestStrategySelector:
    """Test strategy selector functionality."""
    
    @pytest.fixture
    def selector(self):
        """Create strategy selector for testing."""
        return StrategySelector()
        
    @pytest.mark.unit
    def test_analyze_simple_prompts(self, selector):
        """Test analysis of simple geometric prompts."""
        simple_prompts = [
            "Draw a line from (0,0) to (10,10)",
            "Draw a rectangle with corners at (0,0) and (10,5)",
            "Draw a square with side length 5",
            "Draw a grid 5x5 with 1 unit spacing",
            "Draw horizontal lines at y=1, y=2, y=3"
        ]
        
        for prompt in simple_prompts:
            complexity = selector.analyze_prompt_complexity(prompt)
            
            assert complexity.confidence_score >= 0.0
            assert complexity.requires_curves is False
            from promptplot.core.models import DrawingStrategy
            assert complexity.drawing_type == DrawingStrategy.ORTHOGONAL
            assert complexity.estimated_commands > 0
            
    @pytest.mark.unit
    def test_analyze_complex_prompts(self, selector):
        """Test analysis of complex curved prompts."""
        complex_prompts = [
            "Draw a circle with center at (5,5) and radius 3",
            "Draw a sine wave from x=0 to x=10",
            "Draw a smooth curve connecting these points",
            "Draw an organic flower shape",
            "Draw a spiral starting from the center"
        ]
        
        for prompt in complex_prompts:
            complexity = selector.analyze_prompt_complexity(prompt)
            
            assert complexity.confidence_score >= 0.0
            assert complexity.requires_curves is True
            from promptplot.core.models import DrawingStrategy
            assert complexity.drawing_type == DrawingStrategy.NON_ORTHOGONAL
            
    @pytest.mark.unit
    def test_analyze_mixed_prompts(self, selector):
        """Test analysis of prompts with mixed complexity."""
        mixed_prompts = [
            "Draw a house with a triangular roof and rectangular base",
            "Draw a robot with circular head and rectangular body",
            "Draw a chart with bars and a curved trend line"
        ]
        
        for prompt in mixed_prompts:
            complexity = selector.analyze_prompt_complexity(prompt)
            
            # Mixed prompts should have reasonable confidence
            assert complexity.confidence_score >= 0.0
            assert complexity.estimated_commands > 5
            
    @pytest.mark.unit
    def test_keyword_detection(self, selector):
        """Test detection of specific keywords."""
        # Orthogonal keywords
        orthogonal_tests = [
            ("line", False),
            ("rectangle", False),
            ("square", False),
            ("grid", False),
            ("horizontal", False),
            ("vertical", False)
        ]
        
        for keyword, expected_curves in orthogonal_tests:
            prompt = f"Draw a {keyword}"
            complexity = selector.analyze_prompt_complexity(prompt)
            assert complexity.requires_curves == expected_curves
            
        # Non-orthogonal keywords
        non_orthogonal_tests = [
            ("circle", True),
            ("curve", True),
            ("spiral", True),
            ("wave", True),
            ("organic", True),
            ("smooth", True)
        ]
        
        for keyword, expected_curves in non_orthogonal_tests:
            prompt = f"Draw a {keyword}"
            complexity = selector.analyze_prompt_complexity(prompt)
            assert complexity.requires_curves == expected_curves
            
    @pytest.mark.unit
    def test_coordinate_counting(self, selector):
        """Test estimation of command count based on coordinates."""
        prompts_with_coords = [
            ("Move to (10,20)", 2),  # Simple move
            ("Draw from (0,0) to (10,10) to (20,0)", 4),  # Multiple points
            ("Connect points (1,1), (2,2), (3,3), (4,4), (5,5)", 8)  # Many points
        ]
        
        for prompt, min_expected in prompts_with_coords:
            complexity = selector.analyze_prompt_complexity(prompt)
            assert complexity.estimated_commands >= min_expected
            
    @pytest.mark.unit
    def test_select_workflow_orthogonal(self, selector):
        """Test workflow selection for orthogonal strategies."""
        from promptplot.core.models import DrawingStrategy
        
        strategy = selector.select_workflow_strategy("Draw a rectangle")
        assert strategy == DrawingStrategy.ORTHOGONAL
        
    @pytest.mark.unit
    def test_select_workflow_non_orthogonal(self, selector):
        """Test workflow selection for non-orthogonal strategies."""
        from promptplot.core.models import DrawingStrategy
        
        strategy = selector.select_workflow_strategy("Draw a circle")
        assert strategy == DrawingStrategy.NON_ORTHOGONAL
        
    @pytest.mark.unit
    def test_empty_prompt_handling(self, selector):
        """Test handling of empty or invalid prompts."""
        empty_prompts = ["", "   ", None]
        
        for prompt in empty_prompts:
            if prompt is None:
                with pytest.raises((TypeError, AttributeError)):
                    selector.analyze_prompt_complexity(prompt)
            else:
                complexity = selector.analyze_prompt_complexity(prompt)
                assert complexity.complexity_score == 0.0
                assert complexity.estimated_commands == 0


class TestOrthogonalStrategy:
    """Test orthogonal drawing strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create orthogonal strategy for testing."""
        return OrthogonalStrategy()
        
    @pytest.mark.unit
    def test_generate_line_commands(self, strategy):
        """Test generating commands for straight lines."""
        start_point = (0.0, 0.0)
        end_point = (10.0, 10.0)
        
        commands = strategy.generate_line_commands(start_point, end_point)
        
        assert len(commands) >= 2  # At least move and draw
        assert any(cmd.command == "G1" for cmd in commands)
        
        # Check coordinates
        move_cmd = next(cmd for cmd in commands if cmd.x == end_point[0])
        assert move_cmd.y == end_point[1]
        
    @pytest.mark.unit
    def test_generate_rectangle_commands(self, strategy):
        """Test generating commands for rectangles."""
        corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        
        commands = strategy.generate_rectangle_commands(corners)
        
        # Should have commands for all four sides plus pen control
        assert len(commands) >= 6
        
        # Should include pen down and pen up
        assert any(cmd.command == "M3" for cmd in commands)
        assert any(cmd.command == "M5" for cmd in commands)
        
    @pytest.mark.unit
    def test_generate_grid_commands(self, strategy):
        """Test generating commands for grid patterns."""
        grid_size = (5, 5)
        spacing = 1.0
        origin = (0.0, 0.0)
        
        commands = strategy.generate_grid_commands(grid_size, spacing, origin)
        
        # Grid should have multiple lines
        assert len(commands) > 10
        
        # Should have multiple pen up/down cycles
        pen_down_count = sum(1 for cmd in commands if cmd.command == "M3")
        pen_up_count = sum(1 for cmd in commands if cmd.command == "M5")
        
        assert pen_down_count > 1
        assert pen_up_count > 1
        
    @pytest.mark.unit
    def test_optimize_path(self, strategy):
        """Test path optimization for orthogonal shapes."""
        # Create unoptimized commands
        commands = [
            GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="G1", x=10.0, y=0.0, f=1000),
            GCodeCommand(command="M5"),
            GCodeCommand(command="G1", x=0.0, y=5.0, f=1000),  # Jump to new location
            GCodeCommand(command="M3", s=255),
            GCodeCommand(command="G1", x=10.0, y=5.0, f=1000),
            GCodeCommand(command="M5")
        ]
        
        optimized = strategy.optimize_path(commands)
        
        # Optimization should maintain or reduce command count
        assert len(optimized) <= len(commands)
        
        # Should still have essential commands
        assert any(cmd.command == "G1" for cmd in optimized)
        
    @pytest.mark.unit
    def test_calculate_bounds(self, strategy):
        """Test bounding box calculation."""
        commands = [
            GCodeCommand(command="G1", x=0.0, y=0.0, f=1000),
            GCodeCommand(command="G1", x=10.0, y=5.0, f=1000),
            GCodeCommand(command="G1", x=-5.0, y=15.0, f=1000)
        ]
        
        bounds = strategy.calculate_bounds(commands)
        
        assert bounds["min_x"] == -5.0
        assert bounds["max_x"] == 10.0
        assert bounds["min_y"] == 0.0
        assert bounds["max_y"] == 15.0
        assert bounds["width"] == 15.0
        assert bounds["height"] == 15.0


class TestNonOrthogonalStrategy:
    """Test non-orthogonal drawing strategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create non-orthogonal strategy for testing."""
        return NonOrthogonalStrategy()
        
    @pytest.mark.unit
    def test_generate_circle_commands(self, strategy):
        """Test generating commands for circles."""
        center = (5.0, 5.0)
        radius = 3.0
        
        commands = strategy.generate_circle_commands(center, radius)
        
        # Circle should have multiple segments
        assert len(commands) > 8
        
        # Should include pen control
        assert any(cmd.command == "M3" for cmd in commands)
        assert any(cmd.command == "M5" for cmd in commands)
        
        # All drawing commands should be within radius of center
        for cmd in commands:
            if cmd.command == "G1" and cmd.x is not None and cmd.y is not None:
                distance = ((cmd.x - center[0])**2 + (cmd.y - center[1])**2)**0.5
                assert distance <= radius + 0.1  # Small tolerance for approximation
                
    @pytest.mark.unit
    def test_generate_curve_commands(self, strategy):
        """Test generating commands for smooth curves."""
        control_points = [
            (0.0, 0.0),
            (5.0, 10.0),
            (10.0, 0.0),
            (15.0, 5.0)
        ]
        
        commands = strategy.generate_curve_commands(control_points)
        
        # Curve should have smooth segments
        assert len(commands) > len(control_points)
        
        # Should start and end near control points
        first_draw = next(cmd for cmd in commands if cmd.command == "G1" and cmd.x is not None)
        last_draw = None
        for cmd in reversed(commands):
            if cmd.command == "G1" and cmd.x is not None:
                last_draw = cmd
                break
                
        assert first_draw is not None
        assert last_draw is not None
        
    @pytest.mark.unit
    def test_approximate_arc(self, strategy):
        """Test arc approximation with line segments."""
        start_angle = 0.0
        end_angle = 90.0  # Quarter circle
        center = (0.0, 0.0)
        radius = 5.0
        
        commands = strategy.approximate_arc(center, radius, start_angle, end_angle)
        
        # Arc should have multiple segments
        assert len(commands) > 3
        
        # First point should be at start angle
        first_cmd = commands[0]
        expected_x = center[0] + radius * 1.0  # cos(0) = 1
        expected_y = center[1] + radius * 0.0  # sin(0) = 0
        
        assert abs(first_cmd.x - expected_x) < 0.1
        assert abs(first_cmd.y - expected_y) < 0.1
        
    @pytest.mark.unit
    def test_smooth_path(self, strategy):
        """Test path smoothing algorithm."""
        rough_points = [
            (0.0, 0.0),
            (1.0, 2.0),
            (2.0, 1.0),
            (3.0, 3.0),
            (4.0, 0.0)
        ]
        
        smooth_commands = strategy.smooth_path(rough_points)
        
        # Smoothed path should have more points than original
        assert len(smooth_commands) >= len(rough_points)
        
        # All commands should be movement commands
        for cmd in smooth_commands:
            assert cmd.command == "G1"
            assert cmd.x is not None
            assert cmd.y is not None


class TestMockStrategySelector:
    """Test mock strategy selector for testing purposes."""
    
    @pytest.mark.unit
    def test_mock_selector_basic(self):
        """Test basic mock selector functionality."""
        selector = MockStrategySelector()
        
        analysis = selector.analyze_prompt_complexity("Draw a line")
        
        assert "complexity_score" in analysis
        assert "requires_curves" in analysis
        assert "estimated_commands" in analysis
        assert "suggested_strategy" in analysis
        
    @pytest.mark.unit
    def test_mock_selector_history(self):
        """Test mock selector maintains analysis history."""
        selector = MockStrategySelector()
        
        prompts = ["Draw a line", "Draw a circle", "Draw a square"]
        
        for prompt in prompts:
            selector.analyze_prompt_complexity(prompt)
            
        assert len(selector.analysis_history) == 3
        
        for i, (prompt, analysis) in enumerate(selector.analysis_history):
            assert prompt == prompts[i]
            assert isinstance(analysis, dict)
            
    @pytest.mark.unit
    def test_mock_selector_curve_detection(self):
        """Test mock selector curve detection."""
        selector = MockStrategySelector()
        
        # Test curve detection
        curve_analysis = selector.analyze_prompt_complexity("Draw a circle")
        assert curve_analysis["requires_curves"] is True
        assert curve_analysis["suggested_strategy"] == "non_orthogonal"
        
        # Test non-curve detection
        line_analysis = selector.analyze_prompt_complexity("Draw a line")
        assert line_analysis["requires_curves"] is False
        assert line_analysis["suggested_strategy"] == "orthogonal"