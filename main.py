import argparse

from agent import run_agent
from agent import audit
from agent.budget import Budget
from agent.display import console
from agent.memory import Memory, SUMMARISE_AFTER_TURNS
from agent.prompts import system_prompt
from agent.providers import create_provider
from agent.setup import setup_project, setup_provider
from agent.storage import Storage
from agent.tools import create_tools


def get_prompt() -> str | None:
    """Read a line from the user. Returns None on exit (EOF or exit command)."""
    try:
        value = input("\nYou (exit to quit): ").strip()
        return None if value.lower() in ("exit", "quit") else value
    except (KeyboardInterrupt, EOFError):
        return None


def main():
    parser = argparse.ArgumentParser(description="AI Code Agent")
    parser.add_argument("prompt", nargs="?", help="Initial prompt (optional)")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Print tool calls and token usage")
    args = parser.parse_args()

    console.print("[bold]AI Code Agent[/bold] — type [dim]exit[/dim] to quit")
    console.print("─" * 40)

    storage = Storage()
    project_dir, is_new = setup_project()
    provider_config = setup_provider(storage)

    tools, tool_map = create_tools(project_dir)
    provider = create_provider(
        provider_config,
        tools=tools,
        system_instruction=system_prompt(project_dir),
    )

    # ── Memory: restore context from previous sessions ────────────────────────
    memory = Memory(project_dir)
    summary, recent_turns = memory.load()
    has_context = bool(summary or recent_turns)

    if has_context:
        console.print("[dim]Restoring conversation context from previous session...[/dim]")
        provider.load_context(summary, recent_turns)

    budget = Budget(max_tokens=100_000)
    audit.log_session_start(
        str(project_dir),
        provider_config["provider"],
        provider_config["model"],
    )

    # Scan an existing project only when there is no saved memory context.
    # If context was restored the agent already knows what's been built.
    if not is_new and not has_context:
        console.print("\nScanning project — this may take a moment...")
        try:
            run_agent(provider, (
                "This is an existing project. Start by listing all files in the current directory. "
                "Then read whatever files are present — source code, config, docs, anything. "
                "Give me a short summary of what the project does and what's already been built. "
                "Don't assume any specific structure or filenames."
            ), tool_map=tool_map, budget=budget, verbose=args.verbose)
            memory.save(provider.export_history())
        except Exception as e:
            console.print(f"\n[red][Error during project scan] {e}[/red]")

    prompt = args.prompt or get_prompt()

    while prompt is not None:
        if not prompt:
            prompt = get_prompt()
            continue

        if budget.tokens_exceeded:
            console.print("[bold red]Token budget exhausted. Please start a new session.[/bold red]")
            break

        if budget.turns_exceeded:
            console.print(f"[yellow]Session turn limit ({budget.max_turns}) reached.[/yellow]")
            break

        try:
            run_agent(provider, prompt, tool_map=tool_map, budget=budget, verbose=args.verbose)
            memory.save(provider.export_history())
        except KeyboardInterrupt:
            console.print("\nInterrupted.")
            break
        except Exception as e:
            console.print(f"\n[red][Error] {e}[/red]")

        prompt = get_prompt()

    # ── Memory: summarise if the session has grown long ───────────────────────
    if memory.count_stored_turns() >= SUMMARISE_AFTER_TURNS:
        console.print("\n[dim]Summarising session history for next run...[/dim]")
        try:
            summary_text = provider.one_shot(memory.build_summary_prompt())
            memory.save_summary(summary_text)
        except Exception as e:
            console.print(f"[dim][Could not generate summary: {e}][/dim]")

    console.print(f"\n[dim]{budget.summary()}[/dim]")
    console.print("\nGoodbye!")
    audit.log_session_end(budget.total_tokens)
    storage.close()


if __name__ == "__main__":
    main()
