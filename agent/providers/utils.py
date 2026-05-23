import inspect
from typing import get_type_hints

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
}


def function_to_openai_schema(fn) -> dict:
    """Convert a Python function with type hints and a docstring to an OpenAI tool schema."""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""

    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        annotation = hints.get(name, str)
        properties[name] = {"type": _TYPE_MAP.get(annotation, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": doc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
