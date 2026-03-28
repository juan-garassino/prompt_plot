# LLM Providers

PromptPlot uses LlamaIndex for LLM integration. Four providers are supported,
all with multimodal (vision) capability via optional packages.

## Ollama (default, local)

No API key needed. Install Ollama and pull a model:

```bash
# Install: https://ollama.ai
ollama pull llama3.2:3b

# For multimodal (vision) support
ollama pull llama3.2-vision:11b
```

```bash
promptplot generate "draw a spiral" --provider ollama --model llama3.2:3b
```

Config:

```yaml
llm:
  default_provider: ollama
  ollama_model: llama3.2:3b
  ollama_vision_model: llama3.2-vision:11b   # used for --reference
  ollama_base_url: http://localhost:11434     # default
  temperature: 0.1
```

## OpenAI

```bash
export OPENAI_API_KEY=sk-...
promptplot generate "draw a cat" --provider openai
```

Install extra:

```bash
uv pip install -e ".[openai]"

# For multimodal
uv pip install -e ".[openai,vision]"
```

Config:

```yaml
llm:
  default_provider: openai
  openai_model: gpt-4o-mini
  temperature: 0.1
```

## Azure OpenAI

```bash
export GPT4_API_KEY=...
export GPT4_ENDPOINT=https://your-resource.openai.azure.com/
export GPT4_API_VERSION=2024-02-15-preview
```

Install extra:

```bash
uv pip install -e ".[azure]"
```

Config:

```yaml
llm:
  default_provider: azure_openai
  azure_model: gpt-4o
  azure_deployment_name: gpt-4o-gs
  temperature: 0.1
```

## Google Gemini

```bash
export GOOGLE_API_KEY=...
promptplot generate "draw a tree" --provider gemini
```

Install extra:

```bash
uv pip install -e ".[gemini]"

# For multimodal
uv pip install -e ".[gemini,vision]"
```

Config:

```yaml
llm:
  default_provider: gemini
  gemini_model: models/gemini-1.5-flash
  temperature: 0.1
```

## Temperature

All providers pass `temperature` from config to the LlamaIndex constructor. Default is `0.1` (deterministic). Increase for more creative output:

```yaml
llm:
  temperature: 0.7  # more varied drawings
```

## Multimodal (vision)

All providers support `acomplete_multimodal()` for reference-image-guided generation. If the multimodal package isn't installed, it falls back to text-only silently.

```bash
# Use a reference image
promptplot generate "draw this landscape" --reference photo.jpg

# Ollama needs a vision model pulled
ollama pull llama3.2-vision:11b
```

Vision config:

```yaml
vision:
  enabled: true
  reference_image: photo.jpg
  preview_feedback: true          # render preview, feed back to LLM
  max_feedback_iterations: 1
```

## Switching providers at runtime

```bash
# CLI flag overrides config
promptplot generate "draw a star" --provider openai --model gpt-4o

# Or set in config file
promptplot --config openai_config.yaml generate "draw a star"
```

## Provider comparison

| Provider | Latency | Quality | Cost | Local | Multimodal |
|----------|---------|---------|------|-------|------------|
| Ollama | ~5-30s | Good for simple shapes | Free | Yes | Yes (vision models) |
| OpenAI | ~2-5s | Best overall | $$$ | No | Yes (GPT-4o) |
| Azure | ~2-5s | Same as OpenAI | $$$ | No | Yes |
| Gemini | ~3-8s | Good | $$ | No | Yes |
