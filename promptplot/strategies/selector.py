"""
Strategy selection logic for PromptPlot v2.0

This module implements intelligent analysis of drawing prompts to determine
the optimal drawing strategy (orthogonal vs non-orthogonal) based on the
complexity and geometric requirements of the requested drawing.
"""

import re
from typing import Dict, List, Optional, Type, Any
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel

from ..core.models import DrawingStrategy


class ComplexityLevel(str, Enum):
    """Enumeration of drawing complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class PromptComplexity:
    """Analysis results of prompt complexity and drawing requirements"""
    drawing_type: DrawingStrategy
    complexity_level: ComplexityLevel
    estimated_commands: int
    requires_curves: bool
    geometric_shapes_count: int
    organic_shapes_count: int
    confidence_score: float
    reasoning: str


class StrategySelector:
    """
    Intelligent strategy selector that analyzes prompts to determine
    the optimal drawing approach (orthogonal vs non-orthogonal).
    
    This class implements the core logic for Requirements 3.1 and 3.3:
    - Automatic strategy determination based on prompt analysis
    - Strategy recommendation based on drawing complexity
    """
    
    def __init__(self):
        """Initialize the strategy selector with pattern matching rules"""
        
        # Orthogonal (straight-line) indicators
        self.orthogonal_keywords = {
            'shapes': ['rectangle', 'square', 'box', 'grid', 'line', 'triangle', 
                      'diamond', 'cross', 'plus', 'frame', 'border', 'outline'],
            'patterns': ['grid', 'checkerboard', 'maze', 'lattice', 'mesh', 
                        'pattern', 'rows', 'columns', 'matrix'],
            'geometric': ['straight', 'linear', 'horizontal', 'vertical', 
                         'parallel', 'perpendicular', 'right angle', 'corner']
        }
        
        # Non-orthogonal (curved/organic) indicators  
        self.non_orthogonal_keywords = {
            'curves': ['circle', 'curve', 'arc', 'spiral', 'wave', 'sine', 
                      'smooth', 'flowing', 'rounded', 'circular', 'oval', 'ellipse'],
            'organic': ['flower', 'tree', 'leaf', 'cloud', 'mountain', 'river',
                       'face', 'portrait', 'animal', 'organic', 'natural'],
            'artistic': ['sketch', 'artistic', 'freeform', 'abstract', 'fluid',
                        'graceful', 'elegant', 'stylized', 'decorative']
        }
        
        # Complexity indicators
        self.complexity_indicators = {
            'simple': ['simple', 'basic', 'minimal', 'clean', 'single'],
            'moderate': ['detailed', 'multiple', 'several', 'complex', 'intricate'],
            'complex': ['very detailed', 'highly complex', 'elaborate', 'sophisticated',
                       'many', 'numerous', 'extensive', 'comprehensive']
        }

    def analyze_prompt_complexity(self, prompt: str) -> PromptComplexity:
        """
        Analyze a drawing prompt to determine complexity and strategy requirements.
        
        Args:
            prompt: The natural language drawing prompt to analyze
            
        Returns:
            PromptComplexity object with analysis results
            
        This method implements Requirements 3.1 and 3.3 by analyzing prompts
        to detect orthogonal vs non-orthogonal requirements and determining
        appropriate strategy recommendations.
        """
        prompt_lower = prompt.lower()
        
        # Count keyword matches for each category
        orthogonal_score = self._count_keyword_matches(prompt_lower, self.orthogonal_keywords)
        non_orthogonal_score = self._count_keyword_matches(prompt_lower, self.non_orthogonal_keywords)
        
        # Analyze geometric vs organic shape indicators
        geometric_shapes = self._count_geometric_shapes(prompt_lower)
        organic_shapes = self._count_organic_shapes(prompt_lower)
        
        # Determine complexity level
        complexity_level = self._determine_complexity_level(prompt_lower)
        
        # Estimate command count based on complexity and content
        estimated_commands = self._estimate_command_count(
            prompt_lower, complexity_level, geometric_shapes, organic_shapes
        )
        
        # Determine if curves are required
        requires_curves = self._requires_curves(prompt_lower, non_orthogonal_score)
        
        # Select strategy based on analysis
        strategy, confidence, reasoning = self._select_strategy(
            orthogonal_score, non_orthogonal_score, requires_curves, 
            geometric_shapes, organic_shapes
        )
        
        return PromptComplexity(
            drawing_type=strategy,
            complexity_level=complexity_level,
            estimated_commands=estimated_commands,
            requires_curves=requires_curves,
            geometric_shapes_count=geometric_shapes,
            organic_shapes_count=organic_shapes,
            confidence_score=confidence,
            reasoning=reasoning
        )

    def select_workflow_strategy(self, prompt: str) -> DrawingStrategy:
        """
        Select the appropriate drawing strategy for a given prompt.
        
        Args:
            prompt: The drawing prompt to analyze
            
        Returns:
            DrawingStrategy enum value (ORTHOGONAL or NON_ORTHOGONAL)
            
        This is a convenience method that returns just the strategy decision
        for use in workflow selection.
        """
        analysis = self.analyze_prompt_complexity(prompt)
        return analysis.drawing_type

    def get_strategy_recommendation(self, prompt: str) -> Dict[str, Any]:
        """
        Get a detailed strategy recommendation with reasoning.
        
        Args:
            prompt: The drawing prompt to analyze
            
        Returns:
            Dictionary containing strategy, confidence, and detailed analysis
            
        This method provides comprehensive analysis results for debugging
        and user feedback purposes.
        """
        analysis = self.analyze_prompt_complexity(prompt)
        
        return {
            'strategy': analysis.drawing_type,
            'confidence': analysis.confidence_score,
            'complexity_level': analysis.complexity_level,
            'estimated_commands': analysis.estimated_commands,
            'requires_curves': analysis.requires_curves,
            'geometric_shapes': analysis.geometric_shapes_count,
            'organic_shapes': analysis.organic_shapes_count,
            'reasoning': analysis.reasoning,
            'recommendations': self._generate_recommendations(analysis)
        }

    def _count_keyword_matches(self, prompt: str, keyword_dict: Dict[str, List[str]]) -> int:
        """Count matches for keywords in different categories"""
        total_score = 0
        for category, keywords in keyword_dict.items():
            for keyword in keywords:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = len(re.findall(pattern, prompt))
                total_score += matches
        return total_score

    def _count_geometric_shapes(self, prompt: str) -> int:
        """Count mentions of geometric shapes"""
        geometric_patterns = [
            r'\b(rectangle|square|triangle|diamond|polygon)\b',
            r'\b(line|straight line|horizontal line|vertical line)\b',
            r'\b(grid|matrix|lattice|mesh)\b',
            r'\b(box|frame|border|outline)\b'
        ]
        
        count = 0
        for pattern in geometric_patterns:
            count += len(re.findall(pattern, prompt))
        return count

    def _count_organic_shapes(self, prompt: str) -> int:
        """Count mentions of organic/curved shapes"""
        organic_patterns = [
            r'\b(circle|oval|ellipse|curve|arc|spiral)\b',
            r'\b(flower|tree|leaf|cloud|mountain|river)\b',
            r'\b(face|portrait|animal|organic|natural)\b',
            r'\b(wave|flowing|smooth|graceful)\b'
        ]
        
        count = 0
        for pattern in organic_patterns:
            count += len(re.findall(pattern, prompt))
        return count

    def _determine_complexity_level(self, prompt: str) -> ComplexityLevel:
        """Determine the complexity level of the drawing request"""
        
        # Check for explicit complexity indicators
        for level, indicators in self.complexity_indicators.items():
            for indicator in indicators:
                if indicator in prompt:
                    return ComplexityLevel(level)
        
        # Analyze prompt length and detail level
        word_count = len(prompt.split())
        detail_words = ['detailed', 'intricate', 'complex', 'elaborate', 'sophisticated']
        detail_count = sum(1 for word in detail_words if word in prompt)
        
        # Determine complexity based on heuristics
        if word_count < 10 and detail_count == 0:
            return ComplexityLevel.SIMPLE
        elif word_count < 25 and detail_count <= 1:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.COMPLEX

    def _estimate_command_count(self, prompt: str, complexity: ComplexityLevel, 
                               geometric_shapes: int, organic_shapes: int) -> int:
        """Estimate the number of G-code commands needed"""
        
        base_commands = {
            ComplexityLevel.SIMPLE: 10,
            ComplexityLevel.MODERATE: 25,
            ComplexityLevel.COMPLEX: 50
        }
        
        estimated = base_commands[complexity]
        
        # Add commands based on shape count
        estimated += geometric_shapes * 8  # Geometric shapes are simpler
        estimated += organic_shapes * 15   # Organic shapes need more commands
        
        # Adjust based on specific keywords
        multiplier_keywords = {
            'grid': 2.0,
            'pattern': 1.5,
            'detailed': 1.8,
            'intricate': 2.2,
            'multiple': 1.6
        }
        
        multiplier = 1.0
        for keyword, mult in multiplier_keywords.items():
            if keyword in prompt:
                multiplier = max(multiplier, mult)
        
        return int(estimated * multiplier)

    def _requires_curves(self, prompt: str, non_orthogonal_score: int) -> bool:
        """Determine if the drawing requires curved lines"""
        
        # Explicit curve indicators
        curve_keywords = ['curve', 'arc', 'circle', 'oval', 'spiral', 'wave', 'smooth']
        for keyword in curve_keywords:
            if keyword in prompt:
                return True
        
        # High non-orthogonal score suggests curves
        return non_orthogonal_score > 2

    def _select_strategy(self, orthogonal_score: int, non_orthogonal_score: int,
                        requires_curves: bool, geometric_shapes: int, 
                        organic_shapes: int) -> tuple[DrawingStrategy, float, str]:
        """Select the optimal strategy based on analysis scores"""
        
        # Calculate confidence based on score difference
        total_score = orthogonal_score + non_orthogonal_score
        if total_score == 0:
            # No clear indicators, default to orthogonal for simple drawings
            return DrawingStrategy.ORTHOGONAL, 0.6, "No clear indicators, defaulting to orthogonal strategy"
        
        orthogonal_ratio = orthogonal_score / total_score
        non_orthogonal_ratio = non_orthogonal_score / total_score
        
        # Decision logic
        if requires_curves or organic_shapes > geometric_shapes:
            strategy = DrawingStrategy.NON_ORTHOGONAL
            confidence = min(0.9, 0.5 + non_orthogonal_ratio)
            reasoning = f"Curves required or organic shapes dominant (organic: {organic_shapes}, geometric: {geometric_shapes})"
        elif orthogonal_score > non_orthogonal_score * 1.5:
            strategy = DrawingStrategy.ORTHOGONAL
            confidence = min(0.9, 0.5 + orthogonal_ratio)
            reasoning = f"Strong orthogonal indicators (score: {orthogonal_score} vs {non_orthogonal_score})"
        elif geometric_shapes > organic_shapes:
            strategy = DrawingStrategy.ORTHOGONAL
            confidence = min(0.8, 0.5 + orthogonal_ratio)
            reasoning = f"Geometric shapes dominant (geometric: {geometric_shapes}, organic: {organic_shapes})"
        else:
            strategy = DrawingStrategy.NON_ORTHOGONAL
            confidence = min(0.8, 0.5 + non_orthogonal_ratio)
            reasoning = f"Mixed or unclear indicators, favoring non-orthogonal for flexibility"
        
        return strategy, confidence, reasoning

    def select_strategy(self, prompt: str):
        """
        Select and return a strategy instance for the given prompt.
        
        Args:
            prompt: The drawing prompt to analyze
            
        Returns:
            Strategy instance (OrthogonalStrategy or NonOrthogonalStrategy)
        """
        from .orthogonal import OrthogonalStrategy
        from .non_orthogonal import NonOrthogonalStrategy
        
        analysis = self.analyze_prompt_complexity(prompt)
        
        if analysis.drawing_type == DrawingStrategy.ORTHOGONAL:
            return OrthogonalStrategy()
        else:
            return NonOrthogonalStrategy()

    def _generate_recommendations(self, analysis: PromptComplexity) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if analysis.confidence_score < 0.7:
            recommendations.append("Consider providing more specific geometric details in your prompt")
        
        if analysis.estimated_commands > 100:
            recommendations.append("This is a complex drawing that may take significant time to complete")
        
        if analysis.requires_curves and analysis.drawing_type == DrawingStrategy.ORTHOGONAL:
            recommendations.append("Consider simplifying curves to straight line approximations")
        
        if analysis.complexity_level == ComplexityLevel.COMPLEX:
            recommendations.append("Consider breaking this into multiple simpler drawings")
        
        if analysis.geometric_shapes_count > 5:
            recommendations.append("Multiple geometric shapes detected - orthogonal strategy will be efficient")
        
        if analysis.organic_shapes_count > 3:
            recommendations.append("Multiple organic shapes detected - non-orthogonal strategy recommended")
        
        return recommendations