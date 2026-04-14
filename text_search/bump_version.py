"""Increment the PATCH component of VERSION in text_search/app.py."""
import re
import sys
from pathlib import Path

APP_PY = Path(__file__).parent / "app.py"
_VERSION_RE = re.compile(r'^(VERSION\s*=\s*["\'])v(\d+)\.(\d+)\.(\d+)(["\'])', re.MULTILINE)


def bump(text: str) -> tuple[str, str]:
    """Return (updated_text, new_version_string). Raises if pattern not found."""
    m = _VERSION_RE.search(text)
    if not m:
        raise ValueError("VERSION = \"vMAJOR.MINOR.PATCH\" not found in app.py")
    prefix, major, minor, patch, quote = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    new_version = f"v{major}.{minor}.{int(patch) + 1}"
    new_line = f'{prefix}{new_version}{quote}'
    return _VERSION_RE.sub(new_line, text, count=1), new_version


def main() -> None:
    original = APP_PY.read_text(encoding="utf-8")
    updated, new_version = bump(original)
    APP_PY.write_text(updated, encoding="utf-8")
    print(f"Bumped to {new_version}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"bump_version: error — {exc}", file=sys.stderr)
        sys.exit(1)
