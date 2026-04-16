---
name: setup
description: "Interactive project setup wizard. From a clean codebase, guide the user through environment selection, provider configuration, dependency installation, config generation, validation, and dashboard launch. Prefer Conda when available, use the rag-mcp Conda environment for this repository, and only fall back to .venv when Conda is unavailable. If the user selects an unimplemented provider, scaffold it following the plugin architecture. Auto-diagnose and fix startup failures with up to 3 retry rounds."
---

# Setup

Interactive wizard: configure providers -> select environment -> install deps -> generate config -> launch dashboard -> auto-fix issues.

---

## Pipeline

```text
Preflight -> Select Environment -> Ask User -> Generate Config -> Install Deps -> Validate -> Launch -> Usage Guide
```

> Auto-fix loop: if any step fails, diagnose -> fix -> retry (up to 3 rounds).

---

## Step 1: Preflight Checks

Verify prerequisites before asking the user anything.

### 1.1 Check Python Version

```powershell
python --version          # Require >=3.10
```

If Python < 3.10, stop and tell the user to install a supported version.

### 1.2 Select Python Environment (Prefer Conda)

Do **not** create `.venv` first. Always check whether `conda` is available before touching `.venv`.

Environment policy for this repository:
- Prefer Conda when available.
- Default Conda environment name for this repo: `rag-mcp`
- If `rag-mcp` already exists, use it directly.
- If Conda exists but `rag-mcp` does not, create `rag-mcp` and use it.
- Only fall back to `.venv` when Conda is unavailable.

#### Option A: Conda is available (preferred)

```powershell
# Step 1: Check whether conda exists
conda --version

# Step 2: List environments and look for rag-mcp
conda env list

# Step 3a: If rag-mcp exists, verify it
conda run -n rag-mcp python --version

# Step 3b: If rag-mcp does NOT exist, create it first
conda create -n rag-mcp python=3.11 -y

# Step 4: Verify pip is available inside rag-mcp
conda run -n rag-mcp python -m pip --version
```

Notes:
- Prefer `conda run -n rag-mcp ...` for non-interactive automation instead of relying on `conda activate`.
- All remaining `python` / `pip` commands in this skill must be executed inside the selected environment.
- If the user explicitly names another Conda environment, follow the user's choice.

#### Option B: Conda is unavailable (fallback to `.venv`)

Check if `.venv` already exists. If it does, activate it and verify pip. If it does not exist, create it and then activate it.

**Important:** Use `--without-pip` to avoid the slow `ensurepip` step that can hang on Windows, then bootstrap pip manually with `ensurepip` after activation.

```powershell
# Step 1: Check if .venv exists
Test-Path ".venv"

# Step 2: If .venv does NOT exist, create it
python -m venv .venv --without-pip

# Step 3: Activate the virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Step 4: Bootstrap pip inside the venv (only needed after --without-pip)
python -m ensurepip --upgrade

# Step 5: Verify
pip --version
```

If `.venv` already exists, only run activation and verification.

### 1.3 Optional Service Checks

Before installation or launch, verify any local services required by the current config:
- Docker Desktop / Docker Engine if the project depends on Dockerized services
- Ollama if LLM or embedding provider is `ollama`
- Any local vector DB or external endpoint explicitly configured in `config/settings.yaml`

For Ollama:

```powershell
curl http://localhost:11434/api/tags
```

---

## Step 2: Ask User for Configuration

Use the available question-asking tool when needed. Ask in small batches. If a valid `config/settings.yaml` already exists, prefer reusing it and only ask about missing or risky fields.

### Batch 1: Core Providers

Ask these together when configuration is missing or the user wants a fresh setup:

1. **LLM Provider**
   - Options: `OpenAI`, `Azure OpenAI`, `DeepSeek`, `Ollama (local)`, `Qwen (Alibaba Cloud)`, `Gemini (Google)`
   - Recommended: `OpenAI`
   - Built-in: OpenAI, Azure, DeepSeek, Ollama

2. **Embedding Provider**
   - Options: `OpenAI`, `Azure OpenAI`, `Ollama (local)`, `Qwen (Alibaba Cloud)`, `Gemini (Google)`
   - Recommended: match the LLM provider when possible
   - Built-in: OpenAI, Azure, Ollama

3. **Vision**
   - Options: `Yes`, `No`
   - Recommended: `Yes`

4. **Rerank**
   - Options: `No (fastest)`, `Cross-Encoder (local model)`, `LLM-based`
   - Recommended: `No (fastest)`
   - Note: local cross-encoder support may need extra dependency installation and validation.

### Batch 2: Credentials

Refer to [references/provider_profiles.md](references/provider_profiles.md) for required fields per provider.

If OpenAI selected:
- Ask for OpenAI API Key
- Ask for LLM model, default `gpt-4o`
- Ask for embedding model, default `text-embedding-ada-002`

If Azure OpenAI selected:
- Ask for Azure API Key
- Ask for Azure endpoint URL
- Ask for LLM deployment name, default `gpt-4o`
- Ask for embedding deployment name, default `text-embedding-ada-002`

If DeepSeek selected:
- Ask for DeepSeek API Key
- Ask for embedding provider separately because DeepSeek has no embeddings

If Ollama selected:
- Ask for Ollama base URL, default `http://localhost:11434`
- Ask for LLM model name, default `llama3`
- Ask for embedding model name, default `nomic-embed-text`
- Verify Ollama is running before continuing

If Qwen selected:
- Ask for Qwen API Key
- Ask for LLM model, default `qwen-turbo`
- Ask for embedding model, default `text-embedding-v3`
- Use base URL `https://dashscope.aliyuncs.com/compatible-mode/v1`

If Gemini selected:
- Ask for Gemini API Key
- Ask for LLM model, default `gemini-2.0-flash`
- Ask for embedding model, default `text-embedding-004`
- Use base URL `https://generativelanguage.googleapis.com/v1beta/openai/`

### Batch 3: Vision Credentials

`vision_llm` is independent from the main `llm` section. Do not assume it shares credentials.

Ask:
1. Which provider should be used for vision/image captioning?
2. Whether vision can reuse the same credentials if it matches the main LLM provider
3. If not reused, ask for separate API key / endpoint / model

Recommended models:
- OpenAI: `gpt-4o`
- Azure: `gpt-4o`
- Ollama: `llava`
- Qwen: `qwen-vl-max`
- Gemini: `gemini-2.0-flash`

DeepSeek does not provide a built-in vision model in this project, so choose another provider for `vision_llm`.

---

## Step 2.5: Scaffold Unimplemented Providers

If the user selected a provider that is not yet built in, scaffold it before generating config.

Refer to [references/new_provider_guide.md](references/new_provider_guide.md).

Summary:
1. Create `src/libs/llm/{name}_llm.py` extending `BaseLLM`
2. Create `src/libs/embedding/{name}_embedding.py` extending `BaseEmbedding` if needed
3. Create `src/libs/llm/{name}_vision_llm.py` extending `BaseVisionLLM` if needed
4. Register the new classes in package `__init__.py` files
5. Add `base_url` fields to settings models if the provider needs custom endpoints
6. Install provider SDK if needed
7. Update provider reference docs

Many providers are OpenAI-compatible and can subclass existing OpenAI implementations with a different base URL and auth handling.

---

## Step 3: Generate Config

Read the template from [references/settings_template.yaml](references/settings_template.yaml) and fill values based on user answers or the existing config.

Key rules:
- Look up embedding `dimensions` from [references/provider_profiles.md](references/provider_profiles.md)
- For Ollama, set `base_url` and leave API-key and Azure-specific fields empty
- For OpenAI, leave Azure-specific fields empty
- If vision is disabled, set `vision_llm.enabled: false`
- For rerank, set `enabled`, `provider`, and `model` correctly

Write the final config to `config/settings.yaml`.

Also ensure required directories exist:

```powershell
python -c "from pathlib import Path; [Path(d).mkdir(parents=True, exist_ok=True) for d in ['data/db/chroma', 'data/images/default', 'logs', 'config/prompts']]"
```

---

## Step 4: Install Dependencies

Run installation inside the environment selected in Step 1.2.

```powershell
pip install -e ".[dev]"
```

If specific providers or features need extra packages:
- Cross-Encoder rerank: `pip install sentence-transformers`
- Streamlit dashboard: `pip install streamlit`
- OpenAI family providers: `pip install openai`

Verify critical imports:

```powershell
python -c "import chromadb; import mcp; import yaml; print('Core deps OK')"
python -c "import streamlit; print('Streamlit OK')"
python -c "import openai; print('OpenAI SDK OK')"
```

---

## Step 5: Validate Configuration

Run validation inside the environment selected in Step 1.2.

```powershell
python -c "from src.core.settings import load_settings; s = load_settings(); print(f'Config OK: LLM={s.llm.provider}/{s.llm.model}, Embed={s.embedding.provider}/{s.embedding.model}')"
```

If this fails, enter the auto-fix loop.

### Auto-Fix Loop (up to 3 rounds)

```text
Round 0..2:
  Read error message
  Diagnose root cause
  Fix config/settings.yaml or install the missing dependency
  Re-validate
  If pass -> continue to Step 6
  If fail -> next round
```

Common fixes:
- Missing required field -> add it to `config/settings.yaml`
- `ModuleNotFoundError` -> install the missing package in the selected environment
- `Connection refused` for Ollama -> tell the user to start Ollama
- Wrong `dimensions` -> correct it using provider reference data

If all 3 rounds fail, report the diagnosis clearly and stop for user input.

---

## Step 6: Launch Dashboard

Run the dashboard inside the environment selected in Step 1.2.

```powershell
python scripts/start_dashboard.py --port 8501
```

Run it as a background process. Then verify health:

```powershell
python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://localhost:8501/_stcore/health')
    print('Dashboard is running!' if r.status == 200 else f'Status: {r.status}')
except Exception as e:
    print(f'Dashboard not yet ready: {e}')
"
```

If startup fails, use the same auto-fix loop:
- inspect the background error output
- install missing dependencies
- resolve import or port conflicts
- retry launch

---

## Step 7: Usage Guide

After successful launch, present a concise completion message in the user's language.

Suggested template:

```text
Setup Complete!

Dashboard: http://localhost:8501

Quick Start:
  1. Ingest documents:  python scripts/ingest.py <path-to-pdf-or-folder>
  2. Query:             python scripts/query.py "your question here"
  3. Dashboard:         python scripts/start_dashboard.py
  4. MCP Server:        python main.py

Configuration: config/settings.yaml
Logs:          logs/traces.jsonl

Provider: {provider} / Model: {model}
Environment: {environment}
```

If the user communicates in Chinese, answer in Chinese.
