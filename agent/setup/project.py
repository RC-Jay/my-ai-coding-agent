import os
from pathlib import Path

APP_ROOT = Path(__file__).parent.parent.parent
DEFAULT_PROJECTS_DIR = APP_ROOT / "projects"


def _pick_existing_project(working_dir: Path) -> Path | None:
    """List projects in working_dir and let the user pick one."""
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


def setup_project() -> tuple[Path, bool]:
    """
    Ask for a working directory and whether this is a new or existing project.
    Changes the process working directory to the project folder.
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
