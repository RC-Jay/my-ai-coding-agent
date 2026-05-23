import argparse
import os
from pathlib import Path

from agent import run_agent
from agent.prompts import system_prompt
from agent.providers import create_provider
from agent.storage import Storage
from agent.tools import TOOLS

APP_ROOT = Path(__file__).parent
DEFAULT_PROJECTS_DIR = APP_ROOT / "projects"

_PROVIDERS = {
    "1": ("Gemini",        "gemini"),
    "2": ("Azure OpenAI",  "azure_openai"),
}

_MODELS = {
    "gemini":       ["gemini-2.5-flash", "gemini-2.5-pro"],
    "azure_openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
}


# ---------------------------------------------------------------------------
# Provider / credential setup
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Partially mask a sensitive value for display."""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _prompt_cached(storage: Storage, key: str, label: str, secret: bool = False) -> str:
    """
    Return stored value for key, or ask the user and save it.
    If a value is already stored, show it and allow the user to overwrite by typing a new one.
    """
    existing = storage.get(key)
    if existing:
        display = _mask(existing) if secret else existing
        new_value = input(f"{label} [{display}] (press Enter to keep): ").strip()
        if new_value:
            storage.set(key, new_value)
            return new_value
        return existing
    value = input(f"{label}: ").strip()
    storage.set(key, value)
    return value


def setup_provider(storage: Storage):
    last = storage.get("last_provider") or "1"

    print("\nSelect provider:")
    for key, (name, _) in _PROVIDERS.items():
        marker = "  (last used)" if key == last else ""
        print(f"  {key}. {name}{marker}")

    choice = input(f"Choice [{last}]: ").strip() or last
    if choice not in _PROVIDERS:
        choice = last
    storage.set("last_provider", choice)

    provider_name, provider_id = _PROVIDERS[choice]
    config: dict = {"provider": provider_id}

    if provider_id == "gemini":
        config["api_key"] = _prompt_cached(storage, "gemini_api_key", "Gemini API key", secret=True)

        # Gemini requires a model selection
        models = _MODELS["gemini"]
        last_model = storage.get("last_model_gemini") or "1"

        print("\nSelect model:")
        for i, m in enumerate(models, 1):
            marker = "  (last used)" if str(i) == last_model else ""
            print(f"  {i}. {m}{marker}")

        model_choice = input(f"Choice [{last_model}]: ").strip() or last_model
        try:
            model = models[int(model_choice) - 1]
        except (ValueError, IndexError):
            model = models[0]
            model_choice = "1"

        storage.set("last_model_gemini", model_choice)
        config["model"] = model

    elif provider_id == "azure_openai":
        config["api_key"]    = _prompt_cached(storage, "azure_api_key",    "Azure OpenAI API key", secret=True)
        config["endpoint"]   = _prompt_cached(storage, "azure_endpoint",   "Azure endpoint (https://…)")
        config["deployment"] = _prompt_cached(storage, "azure_deployment", "Deployment name")
        # Deployment already has the model baked in — no separate model selection needed
        config["model"] = config["deployment"]

    print(f"\nUsing {provider_name} / {config['model']}")
    return config


# ---------------------------------------------------------------------------
# Project directory setup
# ---------------------------------------------------------------------------

def _pick_existing_project(working_dir: Path) -> Path | None:
    projects = sorted(p for p in working_dir.iterdir() if p.is_dir())
    if not projects:
        print(f"No projects found in {working_dir}.")
        return None

    print("\nExisting projects:")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p.name}")

    selection = input("Enter project name or number: ").strip()
    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(projects):
            return projects[idx]
        print("Invalid number.")
        return None

    project_dir = working_dir / selection
    if not project_dir.is_dir():
        print(f"Project '{selection}' not found.")
        return None
    return project_dir


def setup(storage: Storage) -> tuple[Path, bool]:
    """
    Ask for working directory and whether this is a new or existing project.
    Returns (project_dir, is_new).
    """
    print(f"\nWorking directory (leave blank to use {DEFAULT_PROJECTS_DIR}): ", end="")
    raw = input().strip()
    working_dir = Path(raw).expanduser().resolve() if raw else DEFAULT_PROJECTS_DIR
    working_dir.mkdir(parents=True, exist_ok=True)

    print("New or existing project? [n/e]: ", end="")
    choice = input().strip().lower()

    if choice in ("e", "existing"):
        project_dir = _pick_existing_project(working_dir)
        if project_dir is None:
            print("Falling back to new project.")
            choice = "n"
        else:
            os.chdir(project_dir)
            print(f"Working directory set to: {project_dir}")
            return project_dir, False

    # New project (default)
    print("Project name: ", end="")
    name = input().strip()
    if not name:
        print("Project name cannot be empty.")
        raise SystemExit(1)

    project_dir = working_dir / name
    project_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(project_dir)
    print(f"Working directory set to: {project_dir}")
    return project_dir, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AI Code Agent")
    parser.add_argument("prompt", nargs="?", help="Initial prompt (optional)")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Print tool calls and token usage")
    args = parser.parse_args()

    storage = Storage()

    print("AI Code Agent — type 'exit' to quit")
    print("─" * 40)

    project_dir, is_new = setup(storage)
    provider_config = setup_provider(storage)
    provider = create_provider(
        provider_config,
        tools=TOOLS,
        system_instruction=system_prompt(project_dir),
    )

    # For existing projects, scan and summarise before taking user input
    if not is_new:
        print("\nScanning project — this may take a moment...")
        try:
            run_agent(provider, (
                "This is an existing project. Start by listing all files in the current directory. "
                "Then read whatever files are present — source code, config, docs, anything. "
                "Give me a short summary of what the project does and what's already been built. "
                "Don't assume any specific structure or filenames."
            ), verbose=args.verbose)
        except Exception as e:
            print(f"\n[Error during project scan] {e}")

    def get_prompt() -> str | None:
        """Read a line from the user. Returns None on exit (EOF or exit command)."""
        try:
            value = input("\nYou (exit to quit): ").strip()
            return None if value.lower() in ("exit", "quit") else value
        except (KeyboardInterrupt, EOFError):
            return None

    prompt = args.prompt or get_prompt()

    while prompt is not None:
        if not prompt:
            prompt = get_prompt()
            continue

        print("\nThinking...")
        try:
            run_agent(provider, prompt, verbose=args.verbose)
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            print(f"\n[Error] {e}")

        prompt = get_prompt()

    print("\nGoodbye!")
    storage.close()


if __name__ == "__main__":
    main()
