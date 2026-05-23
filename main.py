import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from agent import run_agent

load_dotenv()

APP_ROOT = Path(__file__).parent
DEFAULT_PROJECTS_DIR = APP_ROOT / "projects"


def pick_existing_project(working_dir: Path) -> Path | None:
    """List projects in working_dir and let the user pick one."""
    projects = sorted(p for p in working_dir.iterdir() if p.is_dir())

    if not projects:
        print(f"No projects found in {working_dir}.")
        return None

    print("\nExisting projects:")
    for i, p in enumerate(projects, 1):
        print(f"  {i}. {p.name}")

    print("Enter project name or number: ", end="")
    selection = input().strip()

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


def setup() -> tuple[Path, bool]:
    """
    Ask for a working directory, then whether this is a new or existing project.
    Returns (project_dir, is_new).
    """
    print(f"Working directory (leave blank to use {DEFAULT_PROJECTS_DIR}): ", end="")
    raw = input().strip()
    working_dir = Path(raw).expanduser().resolve() if raw else DEFAULT_PROJECTS_DIR
    working_dir.mkdir(parents=True, exist_ok=True)

    print("New or existing project? [n/e]: ", end="")
    choice = input().strip().lower()

    if choice in ("e", "existing"):
        project_dir = pick_existing_project(working_dir)
        if project_dir is None:
            print("Falling back to new project.")
            choice = "n"
        else:
            os.chdir(project_dir)
            print(f"Working directory set to: {project_dir}")
            return project_dir, False

    if choice in ("n", "new", ""):
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

    print(f"Unknown choice '{choice}', exiting.")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="AI Code Agent")
    parser.add_argument("prompt", nargs="?", help="Initial prompt (optional)")
    parser.add_argument("--verbose", action="store_true", default=False, help="Print tool calls and token usage")
    args = parser.parse_args()

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    contents = []

    print("AI Code Agent — type 'exit' to quit")
    print("─" * 40)

    project_dir, is_new = setup()

    # For existing projects, ask the agent to explore and summarise first
    if not is_new:
        contents.append(types.Content(role="user", parts=[types.Part(text=(
            "This is an existing project. Please explore it: list the files and read "
            "the important ones (README, pyproject.toml, main source files). "
            "Then give me a short summary of what's already been built so you're up to speed "
            "before I give you further instructions."
        ))]))
        try:
            run_agent(client, contents, project_dir, verbose=args.verbose)
        except Exception as e:
            print(f"\n[Error during project scan] {e}")

    prompt = args.prompt or input("\nYou: ").strip()

    while True:
        if prompt.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if not prompt:
            prompt = input("\nYou: ").strip()
            continue

        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        try:
            run_agent(client, contents, project_dir, verbose=args.verbose)
        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except errors.ClientError as e:
            print(f"\n[API Error] {e.code}: {e.message}")
        except RuntimeError as e:
            print(f"\n[Error] {e}")
        except Exception as e:
            print(f"\n[Unexpected Error] {e}")

        prompt = input("\nYou: ").strip()


if __name__ == "__main__":
    main()
