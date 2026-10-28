"""Windows writes text files as cp1252 by default, which crashes on Vietnamese/Korean text.
Every text read/write in the code must say encoding="utf-8"."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_OBJ = {"os", "Image", "webbrowser", "zipfile", "tarfile", "wave"}


def _offenders(folder: Path) -> list[str]:
    bad = []
    for p in folder.rglob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name not in ("write_text", "read_text", "open") or any(k.arg == "encoding" for k in n.keywords):
                continue
            if isinstance(f, ast.Attribute) and getattr(f.value, "id", "") in SKIP_OBJ:
                continue
            modes = [a.value for a in n.args[(0 if isinstance(f, ast.Attribute) else 1):][:1] if isinstance(a, ast.Constant)]
            modes += [k.value.value for k in n.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
            if any("b" in str(m) for m in modes):
                continue
            bad.append(f"{p.relative_to(ROOT)}:{n.lineno} {name}()")
    return bad


def test_text_io_is_utf8():
    assert _offenders(ROOT / "director") + _offenders(ROOT / "tests") == []
