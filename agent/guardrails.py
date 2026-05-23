"""
Guardrail checks used by the tool functions.
All functions return either an error string (check failed) or None (check passed).
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# File size
# ---------------------------------------------------------------------------

MAX_FILE_BYTES = 100 * 1024  # 100 KB


def check_file_size(content: str) -> str | None:
    size = len(content.encode())
    if size > MAX_FILE_BYTES:
        return f"File too large: {size / 1024:.1f} KB exceeds the {MAX_FILE_BYTES // 1024} KB limit per write."
    return None


# ---------------------------------------------------------------------------
# Path confinement
# ---------------------------------------------------------------------------

def check_path(path: str, project_dir: Path) -> str | None:
    """Reject any path that resolves outside project_dir."""
    try:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_relative_to(project_dir.resolve()):
            return f"Access denied: '{path}' is outside the project directory."
    except Exception as e:
        return f"Invalid path: {e}"
    return None


# ---------------------------------------------------------------------------
# Sensitive file protection
# ---------------------------------------------------------------------------

_SENSITIVE_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "credentials.json", "token.json"}
_SENSITIVE_SUFFIXES = {".pem", ".key", ".crt", ".pfx", ".p12", ".ppk"}
_SENSITIVE_PREFIXES = {".env"}


def is_sensitive_file(path: str) -> bool:
    p = Path(path)
    name = p.name.lower()
    if name in _SENSITIVE_NAMES:
        return True
    if p.suffix.lower() in _SENSITIVE_SUFFIXES:
        return True
    # .env, .env.local, .env.production, …
    if name == ".env" or name.startswith(".env."):
        return True
    return False


# ---------------------------------------------------------------------------
# Prompt injection detection
# ---------------------------------------------------------------------------

_INJECTION_RE = re.compile(
    r"ignore\s+(all\s+)?previous\s+instructions"
    r"|disregard\s+(all\s+)?(previous|prior)\s+instructions"
    r"|you\s+are\s+now\s+a\b"
    r"|new\s+system\s+prompt"
    r"|forget\s+(all\s+)?previous"
    r"|act\s+as\s+if\s+you",
    re.IGNORECASE,
)


def check_prompt_injection(content: str) -> bool:
    return bool(_INJECTION_RE.search(content))


# ---------------------------------------------------------------------------
# Command safety
# ---------------------------------------------------------------------------

_BLOCKED: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bsudo\b"),                          "sudo is not permitted"),
    (re.compile(r"rm\s+-\w*r\w*f\s+/"),               "rm -rf / is not permitted"),
    (re.compile(r"curl\s+.+\|\s*(ba)?sh"),             "piping curl to a shell is not permitted"),
    (re.compile(r"wget\s+.+\|\s*(ba)?sh"),             "piping wget to a shell is not permitted"),
    (re.compile(r">\s*/dev/(sd|hd|nvme|sda|sdb)"),    "writing directly to a disk device is not permitted"),
    (re.compile(r"\bmkfs\b"),                           "disk formatting is not permitted"),
    (re.compile(r":\s*\(\s*\)\s*\{"),                  "fork bombs are not permitted"),
]

_DESTRUCTIVE = re.compile(
    r"\brm\s"
    r"|\bgit\s+reset\s+--hard\b"
    r"|\bgit\s+push\s+.*--force\b"
    r"|\bgit\s+clean\b"
    r"|\btruncate\b"
    r"|\bdrop\s+table\b"
    r"|\bshred\b",
    re.IGNORECASE,
)


def check_blocked_command(command: str) -> str | None:
    """Return an error string if the command matches a hard-blocked pattern."""
    for pattern, reason in _BLOCKED:
        if pattern.search(command):
            return f"Blocked: {reason}."
    return None


def is_destructive_command(command: str) -> bool:
    """Return True if the command should require user confirmation before running."""
    return bool(_DESTRUCTIVE.search(command))
