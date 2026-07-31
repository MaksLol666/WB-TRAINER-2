import ast
from pathlib import Path


def test_main_initializes_database_through_imported_module():
    source = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports_database = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app"
        and any(alias.name == "database" for alias in node.names)
        for node in tree.body
    )
    calls_init_db = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "database"
        and node.func.attr == "init_db"
        for node in ast.walk(tree)
    )

    assert imports_database
    assert calls_init_db
