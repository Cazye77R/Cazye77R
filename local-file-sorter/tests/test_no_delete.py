"""AST-based guard: no delete operations may appear anywhere under src/.

Forbidden patterns
------------------
Calls  : os.remove, os.unlink, Path.unlink, shutil.rmtree, shutil.rmdir,
         send2trash (any attribute access)
Imports: send2trash, (os.remove / os.unlink are stdlib so only call-sites matter)
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).parent.parent / "src"

# ---------------------------------------------------------------------------
# What we forbid
# ---------------------------------------------------------------------------

# (module, attr) pairs forbidden as attribute calls, e.g. os.remove(...)
FORBIDDEN_CALLS: set[tuple[str, str]] = {
    ("os", "remove"),
    ("os", "unlink"),
    ("shutil", "rmtree"),
    ("shutil", "rmdir"),
}

# Bare function names that are forbidden when called directly
FORBIDDEN_BARE_CALLS: set[str] = {"send2trash"}

# Forbidden method names on any object (catches Path(...).unlink())
FORBIDDEN_METHOD_CALLS: set[str] = {"unlink"}

# Forbidden import names / top-level modules
FORBIDDEN_IMPORTS: set[str] = {"send2trash"}


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------

class DeleteDetector(ast.NodeVisitor):
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.violations: list[str] = []

    def _flag(self, node: ast.AST, reason: str) -> None:
        lineno = getattr(node, "lineno", "?")
        self.violations.append(f"{self.filepath}:{lineno}: {reason}")

    # Imports ------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in FORBIDDEN_IMPORTS:
                self._flag(node, f"Verbotener Import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        top = module.split(".")[0]
        if top in FORBIDDEN_IMPORTS:
            self._flag(node, f"Verbotener Import: from {module} import ...")
        for alias in node.names:
            if alias.name in FORBIDDEN_IMPORTS:
                self._flag(node, f"Verbotener Import: {alias.name}")
        self.generic_visit(node)

    # Calls --------------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # os.remove(...) / shutil.rmtree(...) style
        if isinstance(func, ast.Attribute):
            attr = func.attr
            if isinstance(func.value, ast.Name):
                pair = (func.value.id, attr)
                if pair in FORBIDDEN_CALLS:
                    self._flag(node, f"Verbotener Aufruf: {func.value.id}.{attr}()")
            # Any object's .unlink() method
            if attr in FORBIDDEN_METHOD_CALLS:
                self._flag(node, f"Verbotener Methodenaufruf: .{attr}()")

        # Bare send2trash(...)
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_BARE_CALLS:
            self._flag(node, f"Verbotener Aufruf: {func.id}()")

        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def _collect_python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_no_delete_operations_in_src() -> None:
    py_files = _collect_python_files(SRC_ROOT)
    assert py_files, f"Keine .py-Dateien unter {SRC_ROOT} gefunden"

    all_violations: list[str] = []

    for filepath in py_files:
        source = filepath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError as exc:
            all_violations.append(f"{filepath}: SyntaxError – {exc}")
            continue

        detector = DeleteDetector(filepath)
        detector.visit(tree)
        all_violations.extend(detector.violations)

    if all_violations:
        report = "\n".join(all_violations)
        raise AssertionError(
            f"\n\nVERBOTENE LÖSCH-OPERATIONEN GEFUNDEN ({len(all_violations)} Treffer):\n\n"
            f"{report}\n"
        )
