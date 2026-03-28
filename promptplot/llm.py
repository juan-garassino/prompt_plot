"""
LLM providers for PromptPlot v3.0

Unified LLM abstraction using LlamaIndex. Supports OpenAI, Azure OpenAI,
Gemini, and Ollama. Includes config-aware prompt builders for GCode generation.
"""

import os
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Dict, List

from llama_index.llms.ollama import Ollama
from llama_index.core.llms import CompletionResponse

try:
    from llama_index.llms.azure_openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    AzureOpenAI = None

try:
    from llama_index.llms.openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    from llama_index.llms.gemini import Gemini
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    Gemini = None

# Multimodal imports (optional)
try:
    from llama_index.multi_modal_llms.openai import OpenAIMultiModal
    OPENAI_MULTIMODAL_AVAILABLE = True
except ImportError:
    OPENAI_MULTIMODAL_AVAILABLE = False

try:
    from llama_index.multi_modal_llms.gemini import GeminiMultiModal
    GEMINI_MULTIMODAL_AVAILABLE = True
except ImportError:
    GEMINI_MULTIMODAL_AVAILABLE = False

try:
    from llama_index.multi_modal_llms.ollama import OllamaMultiModal
    OLLAMA_MULTIMODAL_AVAILABLE = True
except ImportError:
    OLLAMA_MULTIMODAL_AVAILABLE = False

try:
    from llama_index.multi_modal_llms.azure_openai import AzureOpenAIMultiModal
    AZURE_MULTIMODAL_AVAILABLE = True
except ImportError:
    AZURE_MULTIMODAL_AVAILABLE = False

from .config import LLMConfig, PaperConfig, PenConfig


class LLMProviderError(Exception):
    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        super().__init__(message)


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, timeout: int = 30, temperature: float = 0.1):
        self.timeout = timeout
        self.temperature = temperature
        self._llm = None

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def _create_llm_instance(self) -> Any: ...

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = self._create_llm_instance()
        return self._llm

    async def acomplete(self, prompt: str) -> str:
        response = await asyncio.wait_for(
            self.llm.acomplete(prompt), timeout=self.timeout
        )
        return response.text if isinstance(response, CompletionResponse) else str(response)

    def complete(self, prompt: str) -> str:
        response = self.llm.complete(prompt)
        return response.text if isinstance(response, CompletionResponse) else str(response)

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        """Complete with optional image inputs. Falls back to text-only by default."""
        return await self.acomplete(prompt)


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o", deployment_name: str = "gpt-4o-gs",
                 api_key: Optional[str] = None, api_version: Optional[str] = None,
                 azure_endpoint: Optional[str] = None, timeout: int = 1220,
                 temperature: float = 0.1):
        super().__init__(timeout, temperature)
        self.model = model
        self.deployment_name = deployment_name
        self.api_key = api_key or os.environ.get("GPT4_API_KEY")
        self.api_version = api_version or os.environ.get("GPT4_API_VERSION")
        self.azure_endpoint = azure_endpoint or os.environ.get("GPT4_ENDPOINT")
        if not all([self.api_key, self.api_version, self.azure_endpoint]):
            raise LLMProviderError("Missing Azure OpenAI config", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    def _create_llm_instance(self):
        if not AZURE_AVAILABLE:
            raise LLMProviderError("pip install llama-index-llms-azure-openai", self.provider_name)
        return AzureOpenAI(
            model=self.model, deployment_name=self.deployment_name,
            api_key=self.api_key, api_version=self.api_version,
            azure_endpoint=self.azure_endpoint, timeout=self.timeout,
            temperature=self.temperature,
        )

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not AZURE_MULTIMODAL_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            from llama_index.core.schema import ImageDocument
            mm_llm = AzureOpenAIMultiModal(
                model=self.model, deployment_name=self.deployment_name,
                api_key=self.api_key, api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
                temperature=self.temperature,
            )
            image_docs = [ImageDocument(image_path=str(p)) for p in image_paths]
            response = await asyncio.wait_for(
                mm_llm.acomplete(prompt, image_documents=image_docs),
                timeout=self.timeout,
            )
            return response.text if hasattr(response, "text") else str(response)
        except Exception:
            return await self.acomplete(prompt)


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.2:3b", request_timeout: int = 10000,
                 base_url: Optional[str] = None, temperature: float = 0.1,
                 vision_model: str = "llama3.2-vision:11b"):
        super().__init__(timeout=request_timeout // 1000, temperature=temperature)
        self.model = model
        self.request_timeout = request_timeout
        self.base_url = base_url
        self.vision_model = vision_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _create_llm_instance(self):
        kwargs = {
            "model": self.model,
            "request_timeout": self.request_timeout,
            "temperature": self.temperature,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return Ollama(**kwargs)

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not OLLAMA_MULTIMODAL_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            from llama_index.core.schema import ImageDocument
            kwargs = {"model": self.vision_model, "request_timeout": self.request_timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            mm_llm = OllamaMultiModal(**kwargs)
            image_docs = [ImageDocument(image_path=str(p)) for p in image_paths]
            response = await asyncio.wait_for(
                mm_llm.acomplete(prompt, image_documents=image_docs),
                timeout=self.timeout,
            )
            return response.text if hasattr(response, "text") else str(response)
        except Exception:
            return await self.acomplete(prompt)


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None,
                 timeout: int = 120, temperature: float = 0.1):
        super().__init__(timeout, temperature)
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing OPENAI_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "openai"

    def _create_llm_instance(self):
        if not OPENAI_AVAILABLE:
            raise LLMProviderError("pip install llama-index-llms-openai", self.provider_name)
        return OpenAI(
            model=self.model, api_key=self.api_key,
            timeout=self.timeout, temperature=self.temperature,
        )

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not OPENAI_MULTIMODAL_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            from llama_index.core.schema import ImageDocument
            mm_llm = OpenAIMultiModal(
                model=self.model, api_key=self.api_key,
                temperature=self.temperature,
            )
            image_docs = [ImageDocument(image_path=str(p)) for p in image_paths]
            response = await asyncio.wait_for(
                mm_llm.acomplete(prompt, image_documents=image_docs),
                timeout=self.timeout,
            )
            return response.text if hasattr(response, "text") else str(response)
        except Exception:
            return await self.acomplete(prompt)


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "models/gemini-1.5-flash",
                 api_key: Optional[str] = None, timeout: int = 120,
                 temperature: float = 0.1):
        super().__init__(timeout, temperature)
        self.model = model
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise LLMProviderError("Missing GOOGLE_API_KEY", self.provider_name)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _create_llm_instance(self):
        if not GEMINI_AVAILABLE:
            raise LLMProviderError("pip install llama-index-llms-gemini", self.provider_name)
        return Gemini(
            model=self.model, api_key=self.api_key,
            temperature=self.temperature,
        )

    async def acomplete_multimodal(
        self, prompt: str, image_paths: Optional[List[Path]] = None
    ) -> str:
        if not image_paths or not GEMINI_MULTIMODAL_AVAILABLE:
            return await self.acomplete(prompt)
        try:
            from llama_index.core.schema import ImageDocument
            mm_llm = GeminiMultiModal(
                model=self.model, api_key=self.api_key,
                temperature=self.temperature,
            )
            image_docs = [ImageDocument(image_path=str(p)) for p in image_paths]
            response = await asyncio.wait_for(
                mm_llm.acomplete(prompt, image_documents=image_docs),
                timeout=self.timeout,
            )
            return response.text if hasattr(response, "text") else str(response)
        except Exception:
            return await self.acomplete(prompt)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "azure_openai": AzureOpenAIProvider,
    "ollama": OllamaProvider,
}


def create_llm_provider(provider_type: str, **kwargs) -> LLMProvider:
    if provider_type not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_type}. Options: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[provider_type](**kwargs)


def get_llm_provider(llm_config: LLMConfig) -> LLMProvider:
    p = llm_config.default_provider
    temp = llm_config.temperature
    if p == "azure_openai":
        return AzureOpenAIProvider(
            model=llm_config.azure_model, deployment_name=llm_config.azure_deployment_name,
            api_key=llm_config.azure_api_key, api_version=llm_config.azure_api_version,
            azure_endpoint=llm_config.azure_endpoint, timeout=llm_config.azure_timeout,
            temperature=temp,
        )
    elif p == "ollama":
        return OllamaProvider(
            model=llm_config.ollama_model, request_timeout=llm_config.ollama_timeout,
            base_url=llm_config.ollama_base_url, temperature=temp,
            vision_model=llm_config.ollama_vision_model,
        )
    elif p == "openai":
        return OpenAIProvider(
            model=llm_config.openai_model, api_key=llm_config.openai_api_key,
            timeout=llm_config.openai_timeout, temperature=temp,
        )
    elif p == "gemini":
        return GeminiProvider(
            model=llm_config.gemini_model, api_key=llm_config.gemini_api_key,
            timeout=llm_config.gemini_timeout, temperature=temp,
        )
    raise ValueError(f"Unknown provider: {p}")


# ---------------------------------------------------------------------------
# Few-shot examples (Phase D)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = {
    "geometric": {
        "description": "A square with cross-hatching",
        "commands": [
            {"command": "M5"},
            {"command": "G0", "x": 40, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 160, "y": 40, "f": 2000},
            {"command": "G1", "x": 160, "y": 160, "f": 2000},
            {"command": "G1", "x": 40, "y": 160, "f": 2000},
            {"command": "G1", "x": 40, "y": 40, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 60, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 60, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 140, "y": 40},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 140, "y": 160, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ],
    },
    "organic": {
        "description": "A flower with curved petals using short G1 segments",
        "commands": [
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 120},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 105, "y": 135, "f": 2000},
            {"command": "G1", "x": 108, "y": 150, "f": 2000},
            {"command": "G1", "x": 105, "y": 165, "f": 2000},
            {"command": "G1", "x": 100, "y": 175, "f": 2000},
            {"command": "G1", "x": 95, "y": 165, "f": 2000},
            {"command": "G1", "x": 92, "y": 150, "f": 2000},
            {"command": "G1", "x": 95, "y": 135, "f": 2000},
            {"command": "G1", "x": 100, "y": 120, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 100, "y": 175},
            {"command": "M3", "s": 1000},
            {"command": "G1", "x": 100, "y": 250, "f": 2000},
            {"command": "M5"},
            {"command": "G0", "x": 0, "y": 0},
        ],
    },
}

# Keywords that select geometric vs organic examples
_GEOMETRIC_KEYWORDS = {"square", "rectangle", "triangle", "grid", "line", "hexagon", "polygon",
                       "geometric", "pattern", "maze", "box", "diamond"}
_ORGANIC_KEYWORDS = {"flower", "tree", "leaf", "face", "animal", "cat", "dog", "bird", "fish",
                     "wave", "cloud", "mountain", "organic", "sketch", "portrait"}


def _select_example(user_prompt: str) -> Optional[str]:
    """Select a relevant few-shot example based on keywords in the prompt."""
    words = set(user_prompt.lower().split())
    if words & _ORGANIC_KEYWORDS:
        return "organic"
    if words & _GEOMETRIC_KEYWORDS:
        return "geometric"
    return None


# ---------------------------------------------------------------------------
# Style presets (Phase D)
# ---------------------------------------------------------------------------

STYLE_PRESETS = {
    "artistic": """ARTISTIC GUIDELINES:
- Use the full canvas. Fill 60-80% of the drawable area.
- For organic shapes, use many short G1 segments to approximate curves (at least 8-12 points per curve).
- Vary stroke density: denser lines for detail/shadows, sparser for highlights.
- Connect strokes where possible -- continuous lines look better on paper.
- Compose with visual balance -- don't cluster everything in one corner.
- Add detail: texture lines, hatching, varied directions.""",

    "precise": """STYLE: PRECISE
- Use clean, exact geometry with sharp corners.
- Straight lines should be perfectly straight (single G1 per segment).
- Maintain consistent spacing between parallel lines.
- Symmetry matters -- mirror coordinates accurately.""",

    "sketch": """STYLE: SKETCH
- Use overlapping, slightly offset strokes for a hand-drawn feel.
- Lines don't need to connect perfectly -- small gaps add character.
- Draw outlines with 2-3 slightly varied passes for a loose, expressive look.
- Vary line weight by drawing some strokes twice.""",

    "minimal": """STYLE: MINIMAL
- Use as few strokes as possible to convey the subject.
- Embrace negative space -- leave large areas of the canvas empty.
- Every line should be intentional and essential.
- Prefer continuous single-stroke drawings where possible.""",
}


# ---------------------------------------------------------------------------
# Config-aware prompt builders (Phase A)
# ---------------------------------------------------------------------------

def build_gcode_prompt(
    user_prompt: str,
    paper: PaperConfig,
    pen: PenConfig,
    style: str = "artistic",
) -> str:
    """Build a GCode generation prompt using actual config values."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    s_val = pen.pen_down_s_value
    f_val = pen.feed_rate

    # Scale example coordinates to ~20% and ~80% of drawable area
    ex_lo_x = round(x0 + w * 0.2, 1)
    ex_lo_y = round(y0 + h * 0.2, 1)
    ex_hi_x = round(x0 + w * 0.8, 1)
    ex_hi_y = round(y0 + h * 0.8, 1)

    orientation = "landscape" if paper.width > paper.height else "portrait"
    orientation_tip = (
        "The canvas is wider than tall -- compose horizontally."
        if orientation == "landscape"
        else "The canvas is taller than wide -- compose vertically or use the height."
    )

    style_block = STYLE_PRESETS.get(style, STYLE_PRESETS["artistic"])

    # Optionally include a few-shot example
    example_key = _select_example(user_prompt)
    few_shot_block = ""
    if example_key and example_key in FEW_SHOT_EXAMPLES:
        import json
        ex = FEW_SHOT_EXAMPLES[example_key]
        few_shot_block = f"""
REFERENCE EXAMPLE ({ex['description']}):
{json.dumps({"commands": ex["commands"]}, indent=2)}

Use a similar structure but adapt to the actual prompt and canvas dimensions below.
"""

    prompt = f"""Create G-code for a pen plotter. Prompt: {user_prompt}

CANVAS: The drawable area is {w:.0f}mm x {h:.0f}mm.
  Minimum coordinates: X={x0:.1f}, Y={y0:.1f}
  Maximum coordinates: X={x1:.1f}, Y={y1:.1f}
  Center: X={cx:.1f}, Y={cy:.1f}
All X coordinates MUST be between {x0:.1f} and {x1:.1f}.
All Y coordinates MUST be between {y0:.1f} and {y1:.1f}.
{orientation_tip}

COMMANDS (only these are allowed):
  G0 Xnn Ynn   - Rapid move (pen must be UP). Used to reposition without drawing.
  G1 Xnn Ynn Fnnnn - Draw a line to (X,Y) at feed rate F (use F{f_val}). Pen must be DOWN.
  M3 S{s_val}      - Put pen DOWN (start drawing).
  M5           - Lift pen UP (stop drawing).

PEN CONTROL RULES (critical):
  1. ALWAYS start with M5 (pen up).
  2. Before every G0 rapid move, ensure pen is UP (M5).
  3. Before drawing with G1, ensure pen is DOWN (M3 S{s_val}).
  4. The sequence for each stroke is: M5 -> G0 (move to start) -> M3 S{s_val} -> G1 ... G1 (draw) -> M5
  5. ALWAYS end with: M5 then G0 X0 Y0 (pen up, return home).
{few_shot_block}
{style_block}

Return a JSON with "commands" list. Example:
{{
    "commands": [
        {{"command": "M5"}},
        {{"command": "G0", "x": {ex_lo_x}, "y": {ex_lo_y}}},
        {{"command": "M3", "s": {s_val}}},
        {{"command": "G1", "x": {ex_hi_x}, "y": {ex_lo_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_hi_x}, "y": {ex_hi_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_lo_x}, "y": {ex_hi_y}, "f": {f_val}}},
        {{"command": "G1", "x": {ex_lo_x}, "y": {ex_lo_y}, "f": {f_val}}},
        {{"command": "M5"}},
        {{"command": "G0", "x": 0, "y": 0}}
    ]
}}

Write just the JSON, no other text.
"""
    return prompt


def build_reflection_prompt(
    wrong_answer: str,
    error: str,
    paper: PaperConfig,
) -> str:
    """Build a reflection prompt that includes valid coordinate ranges."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    return f"""Your previous response had validation errors and could not be processed correctly.

Previous response: {wrong_answer}

Error details: {error}

VALID COORDINATE RANGES:
  X must be between {x0:.1f} and {x1:.1f}
  Y must be between {y0:.1f} and {y1:.1f}

Please reflect on these errors and produce a valid response that strictly follows the required JSON format.
Make sure to:
1. Use proper JSON syntax with correct quotes, commas, and brackets
2. Include all required fields
3. Follow the schema definition precisely
4. Use valid commands (starting with G or M)
5. Use the right data types (numbers for coordinates, strings for command names)
6. Keep ALL coordinates within the valid ranges above

Return ONLY the corrected JSON with no additional text, code blocks, or explanations.
"""


def build_next_command_prompt(
    user_prompt: str,
    history: str,
    paper: PaperConfig,
    pen: PenConfig,
) -> str:
    """Build the streaming next-command prompt with real config values."""
    x0, y0, x1, y1 = paper.get_drawable_area()
    w, h = paper.get_drawable_dimensions()
    s_val = pen.pen_down_s_value
    f_val = pen.feed_rate

    return f"""Generate the NEXT single G-code command for a pen plotter based on this prompt: {user_prompt}

Previous commands:
{history}

CANVAS: {w:.0f}mm x {h:.0f}mm. All X coordinates MUST be between {x0:.1f} and {x1:.1f}. All Y coordinates MUST be between {y0:.1f} and {y1:.1f}.

Rules:
1. Use G0 for rapid movements (pen must be UP first via M5)
2. Use G1 for drawing lines with feed rate f={f_val} (pen must be DOWN first via M3 S{s_val})
3. M3 S{s_val} = pen DOWN, M5 = pen UP
4. Use only commands: G0, G1, M3, M5
5. All coordinates (x, y) should be float numbers within the canvas bounds
6. Stroke sequence: M5 -> G0 (reposition) -> M3 S{s_val} -> G1 (draw) -> M5
7. Always end with M5 then G0 X0 Y0

Return ONLY ONE command as JSON: {{"command": "G1", "x": 10.0, "y": 20.0, "f": {f_val}}}
If the drawing is complete, return: {{"command": "COMPLETE"}}
"""


# Keep old templates as aliases for backward compatibility
GCODE_PROGRAM_TEMPLATE = """
Create G-code for a pen plotter. Prompt: {prompt}

CANVAS: The drawing area is 100mm x 100mm.
All X coordinates MUST be between 0 and 100.
All Y coordinates MUST be between 0 and 100.
Center your drawing around X=50, Y=50 for best results.

COMMANDS (only these are allowed):
  G0 Xnn Ynn   - Rapid move (pen must be UP). Used to reposition without drawing.
  G1 Xnn Ynn Fnnnn - Draw a line to (X,Y) at feed rate F (use F2000). Pen must be DOWN.
  M3 S100      - Put pen DOWN (start drawing).
  M5           - Lift pen UP (stop drawing).

PEN CONTROL RULES (critical):
  1. ALWAYS start with M5 (pen up).
  2. Before every G0 rapid move, ensure pen is UP (M5).
  3. Before drawing with G1, ensure pen is DOWN (M3 S100).
  4. The sequence for each stroke is: M5 -> G0 (move to start) -> M3 S100 -> G1 ... G1 (draw) -> M5
  5. ALWAYS end with: M5 then G0 X0 Y0 (pen up, return home).

Return a JSON with "commands" list. Example:
{{
    "commands": [
        {{"command": "M5"}},
        {{"command": "G0", "x": 20, "y": 20}},
        {{"command": "M3", "s": 100}},
        {{"command": "G1", "x": 80, "y": 20, "f": 2000}},
        {{"command": "G1", "x": 80, "y": 80, "f": 2000}},
        {{"command": "G1", "x": 20, "y": 80, "f": 2000}},
        {{"command": "G1", "x": 20, "y": 20, "f": 2000}},
        {{"command": "M5"}},
        {{"command": "G0", "x": 0, "y": 0}}
    ]
}}

Write just the JSON, no other text.
"""

REFLECTION_PROMPT = """
Your previous response had validation errors and could not be processed correctly.

Previous response: {wrong_answer}

Error details: {error}

Please reflect on these errors and produce a valid response that strictly follows the required JSON format.
Make sure to:
1. Use proper JSON syntax with correct quotes, commas, and brackets
2. Include all required fields
3. Follow the schema definition precisely
4. Use valid commands (starting with G or M)
5. Use the right data types (numbers for coordinates, strings for command names)

Return ONLY the corrected JSON with no additional text, code blocks, or explanations.
"""
