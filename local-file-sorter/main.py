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


def main() -> None:
    check_imports()

    try:
        from src.gui.app import SorterApp
    except Exception as exc:
        print(f"GUI konnte nicht geladen werden: {exc}", file=sys.stderr)
        print("Prüfe ob tkinter installiert ist (python3-tk / python3.x-tk).", file=sys.stderr)
        sys.exit(1)

    app = SorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
