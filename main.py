import argparse

from agent import run_agent
from agent.prompts import system_prompt
from agent.providers import create_provider
from agent.setup import setup_project, setup_provider
from agent.storage import Storage
from agent.tools import TOOLS


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

    print("AI Code Agent — type 'exit' to quit")
    print("─" * 40)

    storage = Storage()
    project_dir, is_new = setup_project()
    provider_config = setup_provider(storage)
    provider = create_provider(
        provider_config,
        tools=TOOLS,
        system_instruction=system_prompt(project_dir),
    )

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

    prompt = args.prompt or get_prompt()

    while prompt is not None:
        if not prompt:
            prompt = get_prompt()
            continue

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
