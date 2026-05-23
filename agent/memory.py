"""
Persistent conversation memory for the agent.

Each project stores its history in:
  <project_dir>/.agent/history.json   — full neutral-format turn log
  <project_dir>/.agent/summary.json   — rolling LLM-generated summary of older turns

On load, the last MAX_HISTORY_TURNS user-initiated turns are returned so the
provider's context window stays manageable.  When the stored turn count reaches
SUMMARISE_AFTER_TURNS the session asks the model to produce a fresh rolling
summary on exit, compressing older history into a single context message.

Neutral history format (cross-provider JSON):
  [
    {"role": "user",  "parts": [{"type": "text",        "text": "..."}]},
    {"role": "model", "parts": [{"type": "tool_call",   "name": "...", "args": {...}, "id": ""}]},
    {"role": "user",  "parts": [{"type": "tool_result", "name": "...", "result": "...", "id": ""}]},
    {"role": "model", "parts": [{"type": "text",        "text": "..."}]},
    ...
  ]
"""

import json
from pathlib import Path

MAX_HISTORY_TURNS = 20      # sliding window kept in provider context
SUMMARISE_AFTER_TURNS = 40  # trigger a rolling summary on session exit


class Memory:
    def __init__(self, project_dir: Path):
        self._dir = project_dir / ".agent"
        self._history_file = self._dir / "history.json"
        self._summary_file = self._dir / "summary.json"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, history: list[dict]) -> None:
        """Persist the full neutral-format history exported from a provider."""
        self._history_file.write_text(json.dumps(history, indent=2))

    def load(self) -> tuple[str | None, list[dict]]:
        """
        Return (summary_text | None, recent_turns).

        summary_text — LLM-generated summary of turns older than the window.
        recent_turns — last MAX_HISTORY_TURNS user-initiated turns in neutral format.
        """
        history = self._load_history()
        summary = self._load_summary()
        recent = self._get_recent(history)
        return summary, recent

    def save_summary(self, summary: str) -> None:
        """Persist a rolling summary, replacing any previous one."""
        self._summary_file.write_text(json.dumps({"summary": summary}))

    def count_stored_turns(self) -> int:
        """Return the number of user-initiated turns in the stored history."""
        return self._count_turns(self._load_history())

    def build_summary_prompt(self) -> str:
        """
        Build a prompt asking the model to summarise the stored history.
        Incorporates any existing summary so the new one covers everything.
        """
        history = self._load_history()
        existing_summary = self._load_summary()

        lines: list[str] = []

        if existing_summary:
            lines.append(f"[Previous summary]\n{existing_summary}\n\n[Continued conversation]")

        for entry in history:
            role_label = "User" if entry.get("role") == "user" else "Agent"
            for part in entry.get("parts", []):
                ptype = part.get("type")
                if ptype == "text":
                    lines.append(f"{role_label}: {part.get('text', '')}")
                elif ptype == "tool_call":
                    args_str = str(part.get("args", {}))[:120]
                    lines.append(f"Agent called tool: {part.get('name')}({args_str})")
                elif ptype == "tool_result":
                    result = str(part.get("result", ""))[:200]
                    lines.append(f"Tool result: {result}")

        conversation = "\n".join(lines)

        return (
            "You are summarising a conversation between a user and an AI coding agent.\n"
            "Produce a concise but thorough summary covering:\n"
            "- What project is being built and its purpose\n"
            "- What has been implemented so far\n"
            "- Key decisions and design choices made\n"
            "- Any bugs or issues encountered and how they were resolved\n"
            "- The current state of the project\n\n"
            "This summary will give the agent full context at the start of the next session.\n\n"
            f"Conversation:\n{conversation}\n\nSummary:"
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_history(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        try:
            return json.loads(self._history_file.read_text())
        except Exception:
            return []

    def _load_summary(self) -> str | None:
        if not self._summary_file.exists():
            return None
        try:
            return json.loads(self._summary_file.read_text()).get("summary")
        except Exception:
            return None

    def _get_recent(self, history: list[dict]) -> list[dict]:
        """Trim history to the last MAX_HISTORY_TURNS user-initiated turns."""
        turn_starts = [
            i for i, entry in enumerate(history)
            if entry.get("role") == "user"
            and any(p.get("type") == "text" for p in entry.get("parts", []))
        ]
        if len(turn_starts) <= MAX_HISTORY_TURNS:
            return history
        cutoff = turn_starts[-MAX_HISTORY_TURNS]
        return history[cutoff:]

    def _count_turns(self, history: list[dict]) -> int:
        """Count user-initiated turns (text messages, not tool results)."""
        return sum(
            1 for entry in history
            if entry.get("role") == "user"
            and any(p.get("type") == "text" for p in entry.get("parts", []))
        )
