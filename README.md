# My AI Coding Agent

An interactive AI coding agent powered by Google Gemini that can create and edit multi-file Python projects from natural language prompts.

## Features

- **Interactive REPL** — have a back-and-forth conversation to build and refine your project
- **Multi-file project support** — the agent creates properly structured Python projects, not just single scripts
- **New or existing projects** — start fresh or load an existing project (the agent reads it first to get up to speed)
- **Python best practices** — automatically scaffolds `pyproject.toml`, `README.md`, `.gitignore`, and a `uv` virtual environment
- **Self-verifying** — the agent runs the project after creating it, catches errors, and fixes them before handing back to you
- **Tool use** — the agent can list files, read files, write files, and run shell commands autonomously

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A [Google AI Studio](https://aistudio.google.com/apikey) API key

## Setup

```bash
# Clone the repo
git clone git@github.com:RC-Jay/my-ai-coding-agent.git
cd my-ai-coding-agent

# Create virtual environment and install dependencies
uv venv
uv pip install -e .

# Add your Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

## Usage

```bash
uv run main.py
```

You'll be prompted to choose a working directory and whether you're starting a new project or continuing an existing one.

```
AI Code Agent — type 'exit' to quit
────────────────────────────────────────
Working directory (leave blank to use .../projects):
New or existing project? [n/e]: n
Project name: my-todo-app
Working directory set to: .../projects/my-todo-app

You: Build a CLI todo app with add, list, and delete commands
Agent: ...
You: Add a priority field to tasks
Agent: ...
You: exit
```

### Options

| Flag | Description |
|------|-------------|
| `--verbose` | Print each tool call and token usage per turn |

## Project structure

```
my-ai-coding-agent/
├── main.py              # CLI, setup, entry point
├── agent/
│   ├── __init__.py
│   ├── loop.py          # Agent loop and API retry logic
│   ├── tools.py         # Tools: list_files, read_file, write_file, run_command
│   └── prompts.py       # System instruction / best practices prompt
├── pyproject.toml
└── .env.example
```

## How it works

1. The agent receives your prompt along with four tools: `list_files`, `read_file`, `write_file`, and `run_command`
2. Gemini decides which tools to call and in what order
3. Tool results are fed back into the conversation — the loop continues until Gemini stops calling tools
4. The full conversation history is preserved across prompts, so the agent always has context of what it built

## License

MIT
