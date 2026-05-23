from agent.storage import Storage

# Registry of supported providers: key → (display name, provider_id)
PROVIDERS: dict[str, tuple[str, str]] = {
    "1": ("Gemini",       "gemini"),
    "2": ("Azure OpenAI", "azure_openai"),
}

# Available models per provider (only relevant where the user must choose)
MODELS: dict[str, list[str]] = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
}


def _mask(value: str) -> str:
    """Partially mask a sensitive value for display."""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _prompt_cached(storage: Storage, key: str, label: str, secret: bool = False) -> str:
    """
    Return the stored value for key, or prompt the user and save it.
    If a value is already stored, display it and allow overwriting.
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


def _select_model(storage: Storage, provider_id: str) -> str:
    """Prompt the user to pick a model from the provider's model list."""
    models = MODELS[provider_id]
    last_key = f"last_model_{provider_id}"
    last = storage.get(last_key) or "1"

    print("\nSelect model:")
    for i, m in enumerate(models, 1):
        marker = "  (last used)" if str(i) == last else ""
        print(f"  {i}. {m}{marker}")

    choice = input(f"Choice [{last}]: ").strip() or last
    try:
        model = models[int(choice) - 1]
    except (ValueError, IndexError):
        model = models[0]
        choice = "1"

    storage.set(last_key, choice)
    return model


def _collect_gemini(storage: Storage, config: dict) -> None:
    config["api_key"] = _prompt_cached(storage, "gemini_api_key", "Gemini API key", secret=True)
    config["model"]   = _select_model(storage, "gemini")


def _collect_azure_openai(storage: Storage, config: dict) -> None:
    config["api_key"]    = _prompt_cached(storage, "azure_api_key",    "Azure OpenAI API key", secret=True)
    config["endpoint"]   = _prompt_cached(storage, "azure_endpoint",   "Azure endpoint (https://…)")
    config["deployment"] = _prompt_cached(storage, "azure_deployment", "Deployment name")
    # Deployment already encodes the model — no separate selection needed
    config["model"] = config["deployment"]


_COLLECTORS = {
    "gemini":       _collect_gemini,
    "azure_openai": _collect_azure_openai,
}


def setup_provider(storage: Storage) -> dict:
    """
    Prompt the user to select a provider, collect credentials, and return
    a config dict suitable for passing to create_provider().
    """
    last = storage.get("last_provider") or "1"

    print("\nSelect provider:")
    for key, (name, _) in PROVIDERS.items():
        marker = "  (last used)" if key == last else ""
        print(f"  {key}. {name}{marker}")

    choice = input(f"Choice [{last}]: ").strip() or last
    if choice not in PROVIDERS:
        choice = last
    storage.set("last_provider", choice)

    provider_name, provider_id = PROVIDERS[choice]
    config: dict = {"provider": provider_id}

    _COLLECTORS[provider_id](storage, config)

    print(f"\nUsing {provider_name} / {config['model']}")
    return config
