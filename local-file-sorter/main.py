import importlib.util
import sys


_REQUIRED = {
    "customtkinter": "customtkinter",
    "pydantic": "pydantic",
    "yaml": "pyyaml",
    "ollama": "ollama",
    "PIL": "pillow",
}


def check_imports() -> None:
    missing = []
    for module, pip_name in _REQUIRED.items():
        if importlib.util.find_spec(module) is None:
            missing.append(pip_name)
    if missing:
        print(f"Fehlende Pakete: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    check_imports()
    print("Setup OK")
