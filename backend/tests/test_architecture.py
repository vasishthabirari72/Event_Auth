import ast
from pathlib import Path


def test_core_has_no_platform_imports():
    root = Path(__file__).parents[1] / "src/event_auth/core"
    allowed = {"__future__", "collections", "dataclasses", "enum", "math", "typing", "uuid"}
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"Use explicit imports for boundary checks: {path}"
                names = [node.module or ""]
            else:
                continue
            assert all(
                name.split(".")[0] in allowed or name.startswith("event_auth.core.")
                for name in names
            ), path
