"""
Append-only JSON audit log written to data/audit.log.
Every tool call and session boundary is recorded.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path(__file__).parent.parent / "data" / "audit.log"


def _logger() -> logging.Logger:
    log = logging.getLogger("agent.audit")
    if not log.handlers:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def _write(record: dict) -> None:
    record["ts"] = datetime.now(timezone.utc).isoformat()
    _logger().info(json.dumps(record))


def log_session_start(project_dir: str, provider: str, model: str) -> None:
    _write({"event": "session_start", "project": project_dir, "provider": provider, "model": model})


def log_session_end(total_tokens: int) -> None:
    _write({"event": "session_end", "total_tokens": total_tokens})


def log_tool_call(tool: str, args: dict, result: str) -> None:
    _write({
        "event": "tool_call",
        "tool": tool,
        "args": {k: str(v)[:200] for k, v in args.items()},
        "result": result[:500],
    })


def log_guardrail(kind: str, detail: str) -> None:
    _write({"event": "guardrail", "kind": kind, "detail": detail})
