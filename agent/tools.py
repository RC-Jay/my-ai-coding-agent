import os
import subprocess
from pathlib import Path


def list_files(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        entries = sorted(Path(path).iterdir())
        return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries)
    except Exception as e:
        return f"Error listing files: {e}"


def read_file(path: str) -> str:
    """Read and return the full contents of a file."""
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories if needed."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def run_command(command: str) -> str:
    """Run a shell command in the project directory and return its output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output.strip() or "Command completed with no output"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error running command: {e}"


TOOLS = [list_files, read_file, write_file, run_command]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}
