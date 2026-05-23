# My AI Coding Agent

An interactive AI coding agent that can create and edit multi-file Python projects from natural language prompts. Supports multiple LLM providers — bring your own API key.

## Features

- **Multi-provider** — choose between Google Gemini or Azure OpenAI; credentials are saved locally so you only enter them once
- **Interactive REPL** — have a back-and-forth conversation to build and refine your project
- **Multi-file project support** — the agent creates properly structured Python projects, not just single scripts
- **New or existing projects** — start fresh or load an existing project (the agent reads it first to get up to speed)
- **Python best practices** — automatically scaffolds `pyproject.toml`, `README.md`, `.gitignore`, and a `uv` virtual environment
- **Self-verifying** — the agent runs the project after creating it, catches errors, and fixes them before handing back to you
- **Tool use** — the agent can list files, read files, write files, and run shell commands autonomously
- **Live display** — spinner shows elapsed time and the current tool being called; token usage printed after each turn
- **Guardrails** — path confinement, sensitive file protection, dangerous command blocking, destructive command confirmation, prompt injection detection, file size limits, token budget, and session turn cap

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An API key for at least one supported provider (see below)

## Supported providers

| Provider | What you need |
|----------|--------------|
| [Google Gemini](https://aistudio.google.com/apikey) | API key from Google AI Studio |
| [Azure OpenAI](https://portal.azure.com) | API key, endpoint URL, and deployment name |

## Setup

```bash
# Clone the repo
git clone git@github.com:RC-Jay/my-ai-coding-agent.git
cd my-ai-coding-agent

# Create virtual environment and install dependencies
uv venv
uv pip install -e .
```

No `.env` file needed — API keys are entered on first run and stored locally in a SQLite database (`data/config.db`).

## Usage

```bash
uv run main.py
```

On first run you'll be guided through setup:

```
AI Code Agent — type 'exit' to quit
────────────────────────────���───────────

Working directory (leave blank to use .../projects):
New or existing project? [n/e]: n
Project name: my-todo-app
Working directory set to: .../projects/my-todo-app

Select provider:
  1. Gemini  (last used)
  2. Azure OpenAI
Choice [1]:

Select model:
  1. gemini-2.5-flash  (last used)
  2. gemini-2.5-pro
Choice [1]:

You: Build a CLI todo app with add, list, and delete commands
Agent: ...
You: Add a priority field to tasks
Agent: ...
You: exit
```

On subsequent runs, provider, model, and credentials are pre-filled from the local database.

### Options

| Flag | Description |
|------|-------------|
| `--verbose` | Print each tool call and token usage per turn |

## Project structure

```
my-ai-coding-agent/
├── main.py                      # Entry point — CLI args, wires modules, runs REPL
├── agent/
│   ├── __init__.py
│   ├── loop.py                  # Provider-agnostic agent loop with iteration guard
│   ├── tools.py                 # Tool factory: create_tools(project_dir)
│   ├── guardrails.py            # All guard logic (path, commands, files, injection)
│   ├── audit.py                 # Append-only JSON audit log (data/audit.log)
│   ├── budget.py                # Session token budget tracker
│   ├── display.py               # Live terminal display (rich spinner + elapsed time)
│   ├── prompts.py               # System instruction / best practices prompt
│   ├── storage.py               # SQLite-backed credential store
│   ├── setup/
│   │   ├── __init__.py          # Facade: exports setup_project, setup_provider
│   │   ├── project.py           # Working dir + new/existing project selection
│   │   └── provider.py          # Provider/model/credential prompts and registry
│   └── providers/
│       ├── __init__.py          # create_provider() factory
│       ├── base.py              # BaseProvider ABC + ProviderResponse / ToolCall types
│       ├── gemini.py            # Google Gemini implementation
│       ├── azure_openai.py      # Azure OpenAI implementation
│       └── utils.py             # Python function → OpenAI tool schema conversion
├── pyproject.toml
└── uv.lock
```

## Guardrails

| Guardrail | Trigger | Behaviour |
|-----------|---------|-----------|
| **Path confinement** | File op outside project dir | Blocked, audit logged |
| **Sensitive files** | `.env`, `*.pem`, `*.key`, `id_rsa`, etc. | Blocked, audit logged |
| **Prompt injection** | File content contains adversarial instructions | File returned with warning appended |
| **File size limit** | Write > 100 KB | Blocked, audit logged |
| **Blocked commands** | `sudo`, `curl \| sh`, `rm -rf /`, fork bombs | Hard-blocked, audit logged |
| **Destructive commands** | `rm`, `git reset --hard`, `git push --force` | Pauses agent, asks user `[y/N]` |
| **Token budget** | 75% used → warning, 100% → stop | Printed to terminal, audit logged |
| **Session turn cap** | 50 turns (configurable) | Loop exits gracefully |

## Design patterns

| Pattern | Where |
|---------|-------|
| **Strategy** | `BaseProvider` / `GeminiProvider` / `AzureOpenAIProvider` — swap providers without touching the loop |
| **Factory** | `create_provider()` in `agent/providers/__init__.py` — centralises provider instantiation |
| **Facade** | `agent/setup/__init__.py` — single import surface hiding project + provider setup internals |
| **Repository** | `Storage` in `agent/storage.py` — all persistence in one place |
| **Factory (tools)** | `create_tools(project_dir)` in `agent/tools.py` — binds guardrails to the project dir via closures |

## How it works

1. On startup you choose a provider and model; credentials are loaded from the local DB (or prompted for once and saved)
2. The agent receives your prompt along with four tools: `list_files`, `read_file`, `write_file`, and `run_command`
3. The model decides which tools to call and in what order
4. Tool results are fed back into the conversation — the loop continues until the model returns a plain text response (capped at 20 iterations to prevent runaway loops)
5. Each provider manages its own conversation history internally, so the loop is completely provider-agnostic
6. The full history is preserved across prompts within a session, so the agent always has context of what it built

## Adding a new provider

1. Create `agent/providers/<name>.py` implementing `BaseProvider` (`send_message` + `send_tool_results`)
2. Add it to the factory in `agent/providers/__init__.py`
3. Add a `_collect_<name>()` function and register it in `_COLLECTORS` in `agent/setup/provider.py`

## License

MIT
