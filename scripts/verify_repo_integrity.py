"""Read-only integrity scanner for imports of missing SkyED project modules."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def missing_project_modules(repo: Path) -> list[dict]:
    repo = Path(repo).resolve()
    missing: dict[str, set[str]] = {}

    def exists(name: str) -> bool:
        if not name.startswith("skyed."):
            return True
        path = repo.joinpath(*name.split("."))
        return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()

    for file in sorted(repo.rglob("*.py")):
        relative = file.relative_to(repo)
        if any(p in {".git", ".venv", "venv", "__pycache__", "output", "dist"} for p in relative.parts):
            continue
        package = ".".join(relative.parts[:-1])
        try:
            tree = ast.parse(file.read_text(encoding="utf-8-sig"), filename=str(relative))
        except (SyntaxError, UnicodeError) as exc:
            missing.setdefault(f"PARSE_ERROR:{relative}", set()).add(str(exc))
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names if alias.name.startswith("skyed.")]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".") if package else []
                    if node.level > len(parts):
                        continue
                    base = ".".join(parts[:len(parts) - node.level + 1])
                    names = [base + ("." + node.module if node.module else "")]
                elif node.module and node.module.startswith("skyed."):
                    names = [node.module]
            for name in names:
                if not exists(name):
                    missing.setdefault(name, set()).add(str(relative))
    return [{"module": name, "required_by": sorted(required)} for name, required in sorted(missing.items())]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if not (args.repo / "skyed" / "__init__.py").is_file():
        print("INVALID_REPOSITORY: skyed/__init__.py missing")
        return 3
    missing = missing_project_modules(args.repo)
    report = {"status": "BLOCKED" if missing else "PASS", "missing_count": len(missing), "missing_modules": missing}
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
