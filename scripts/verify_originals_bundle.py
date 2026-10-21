"""Read-only validation and optional no-overwrite restore of original SkyED modules."""
from __future__ import annotations
import argparse
import json
import stat
import sys
import zipfile
from pathlib import Path
from discover_original_skyed import MISSING_MODULES, SECRET_PATTERNS, sha256_bytes

class RecoveryValidationError(ValueError):
    pass

def inspect_bundle(zip_path: Path) -> tuple[dict, list[tuple[str, bytes]]]:
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise RecoveryValidationError("ZIP contains duplicate members")
        if "recovery-manifest.json" not in names:
            raise RecoveryValidationError("Recovery manifest absent")
        manifest = json.loads(z.read("recovery-manifest.json"))
        declared = manifest.get("files")
        if not isinstance(declared, list) or not declared:
            raise RecoveryValidationError("No original modules declared")
        expected_names = {"recovery-manifest.json"}
        contents = []
        for item in declared:
            module = str(item.get("module", ""))
            rel = str(item.get("relative_path", ""))
            if module not in {"skyed." + n for n in MISSING_MODULES} or rel != "skyed/" + module.removeprefix("skyed.") + ".py":
                raise RecoveryValidationError(f"Unexpected module/path: {module} ({rel})")
            if rel in expected_names:
                raise RecoveryValidationError(f"Duplicate declaration: {rel}")
            expected_names.add(rel)
            if rel not in names:
                raise RecoveryValidationError(f"Missing member: {rel}")
            info = z.getinfo(rel)
            if info.file_size > 5 * 1024 * 1024:
                raise RecoveryValidationError(f"Excessive source size: {rel}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise RecoveryValidationError(f"Symlink source refused: {rel}")
            data = z.read(info)
            if sha256_bytes(data) != str(item.get("sha256", "")):
                raise RecoveryValidationError(f"SHA256 mismatch: {rel}")
            if any(rx.search(data) for rx in SECRET_PATTERNS):
                raise RecoveryValidationError(f"Possible embedded credential: {rel}")
            try:
                compile(data, rel, "exec", dont_inherit=True)
            except SyntaxError as exc:
                raise RecoveryValidationError(f"Python syntax invalid: {rel}: {exc}") from exc
            contents.append((rel, data))
        if set(names) != expected_names:
            raise RecoveryValidationError("Unexpected ZIP files present")
        if int(manifest.get("found_count", -1)) != len(contents):
            raise RecoveryValidationError("Manifest file count mismatch")
        return manifest, contents

def restore_bundle(zip_path: Path, repo: Path, apply: bool = False) -> dict:
    repo = Path(repo).resolve()
    if not (repo / "skyed" / "__init__.py").is_file():
        raise RecoveryValidationError("Destination is not a SkyED Git checkout")
    manifest, contents = inspect_bundle(zip_path)
    items = []
    for rel, data in contents:
        dest = repo / rel
        if not dest.resolve().is_relative_to(repo):
            raise RecoveryValidationError(f"Unsafe target: {rel}")
        if dest.exists() or dest.is_symlink():
            raise RecoveryValidationError(f"Refusing to overwrite: {rel}")
        items.append({"relative_path": rel, "sha256": sha256_bytes(data),
                      "status": "COPIED_AND_VERIFIED" if apply else "READY_TO_COPY"})
    if apply:
        for rel, data in contents:
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as f:
                f.write(data)
            if sha256_bytes(dest.read_bytes()) != sha256_bytes(data):
                raise RecoveryValidationError(f"Post-copy SHA mismatch: {rel}")
    return {"mode": "APPLY" if apply else "PREVIEW", "verified_originals": len(items),
            "remaining_from_12": len(MISSING_MODULES) - len(items),
            "files": items, "source_root_from_manifest": manifest.get("source_root", ""),
            "warning": "Audit code and secrets before public GitHub commit. No deployment authorized."}

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--report", type=Path)
    a = p.parse_args(argv)
    try:
        result = restore_bundle(a.zip, a.repo, a.apply)
        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
        if a.report:
            if a.report.exists():
                raise RecoveryValidationError(f"Refusing to overwrite report: {a.report}")
            a.report.parent.mkdir(parents=True, exist_ok=True)
            a.report.write_text(output + "\n", encoding="utf-8")
        return 0
    except (OSError, zipfile.BadZipFile, KeyError, TypeError, ValueError) as exc:
        print(f"RECOVERY_BLOCKED: {exc}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
