"""Run the Remotion composition for one output."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

from ..plan.schema import EditPlan
from ..utils.log import log

ROOT = Path(__file__).resolve().parents[2]
REMOTION_DIR = ROOT / "remotion"


class RemotionError(RuntimeError):
    pass


def npx() -> str:
    for name in ("npx", "npx.cmd"):
        p = shutil.which(name)
        if p:
            return p
    raise RemotionError("Không tìm thấy Node.js (npx). Cài Node.js 18+ rồi chạy `npm install` trong thư mục remotion/.")


def ensure_installed() -> None:
    if not (REMOTION_DIR / "node_modules" / "remotion").exists():
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            raise RemotionError("Không tìm thấy npm. Cài Node.js 18+.")
        log("Cài thư viện Remotion lần đầu (npm install)...")
        proc = subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=REMOTION_DIR, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RemotionError(f"npm install lỗi:\n{proc.stderr[-2000:]}")


def browser_executable() -> str | None:
    env = os.environ.get("DIRECTOR_BROWSER") or os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if env:
        return env
    hits = sorted(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
    return hits[-1] if hits else None


def render_output(plan: EditPlan, output_id: str, public_dir: Path, out_file: Path, *, draft: bool = False,
                  concurrency: int | None = None) -> Path:
    ensure_installed()
    fonts = public_dir / "fonts"
    if not fonts.exists():
        shutil.copytree(ROOT / "assets" / "fonts", fonts)
    props = public_dir / f"props_{output_id}.json"
    data = plan.model_dump(exclude={"draft"})
    props.write_text(json.dumps({"plan": data, "outputId": output_id}, ensure_ascii=False), encoding="utf-8")
    cmd = [
        npx(), "remotion", "render", "src/index.ts", "Main", str(out_file.resolve()),
        f"--props={props.resolve()}", f"--public-dir={public_dir.resolve()}", "--muted",
        "--codec=h264", "--log=error", f"--crf={'28' if draft else '17'}",
        f"--concurrency={concurrency or max(1, min(8, (os.cpu_count() or 2) - 1))}",
        "--timeout=120000",
    ]
    if draft:
        cmd += ["--scale=0.5", "--jpeg-quality=70"]
    exe = browser_executable()
    if exe:
        cmd.append(f"--browser-executable={exe}")
    log(f"Remotion dựng khung '{output_id}'{' (nháp)' if draft else ''}...")
    proc = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not out_file.exists():
        raise RemotionError(f"Remotion render lỗi:\n{(proc.stderr or '')[-4000:]}\n{(proc.stdout or '')[-2000:]}")
    return out_file
