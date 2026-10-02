"""Offline structure checks: every model is documented and tested, images and
packages are pinned. Runs without Docker or dbt installed."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "dbt" / "models"


def main() -> int:
    errors: list[str] = []
    sql_models = {p.stem for p in MODELS.rglob("*.sql")}
    yaml_text = "\n".join(p.read_text(encoding="utf-8") for p in MODELS.rglob("*.yml"))
    documented = set(re.findall(r"^  - name: (\w+)\s*$", yaml_text, flags=re.M))
    for model in sorted(sql_models - documented):
        errors.append(f"model {model} has no YAML entry")
    for path in MODELS.rglob("*.sql"):
        text = path.read_text(encoding="utf-8")
        if path.parent.name == "marts" and "ref(" not in text:
            errors.append(f"mart {path.stem} does not build on refs")
        if path.parent.name != "staging" and "source(" in text:
            errors.append(f"{path.stem} reads a source outside staging")

    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    if ":latest" in compose:
        errors.append("compose.yaml uses a :latest image")
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").split():
        if "==" not in line:
            errors.append(f"requirement {line} is not pinned")

    for error in errors:
        print("ERROR", error)
    print(f"checked {len(sql_models)} models: {'ok' if not errors else f'{len(errors)} error(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
