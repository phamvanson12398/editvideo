"""Director Studio: a small local web UI (FastAPI) to upload a video, describe the style, watch progress,
compare variants and revise by chat."""


import json
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import log as L

STATIC = Path(__file__).parent / "static"


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | done | error
    logs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    plans: list[str] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    created: float = field(default_factory=time.time)
    params: dict = field(default_factory=dict)


JOBS: dict[str, Job] = {}


_one_at_a_time = threading.Lock()  # one video at a time; later jobs wait in line ("queued")


def _run(job: Job, fn) -> None:
    def listener(line: str) -> None:
        job.logs.append(line)

    L.add_listener(listener)  # context-local: this thread (and its workers) only
    L.set_tag(f"[{job.id}]")
    with _one_at_a_time:
        job.status = "running"
        try:
            res = fn()
            job.outputs = [str(p) for p in res.outputs]
            job.plans = [str(p) for p in res.plans]
            job.summary = res.summary
            job.status = "done"
        except Exception as e:  # report to the UI
            job.error = f"{e}\n{traceback.format_exc()[-2000:]}"
            job.status = "error"
        finally:
            L.remove_listener(listener)


def create_app(out_dir: Path):
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles

    from ..effects.catalog import to_json
    from ..pipeline import JobOptions, revise_job, run_job
    from ..style.presets import list_presets

    out_dir = out_dir.resolve()
    uploads = out_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Director Studio")
    app.mount("/files", StaticFiles(directory=str(out_dir)), name="files")

    def rel(p: str) -> str:
        try:
            return "/files/" + Path(p).resolve().relative_to(out_dir).as_posix()
        except ValueError:
            return ""

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/config")
    def config():
        from ..pipeline import load_config

        return load_config()

    @app.get("/api/presets")
    def presets():
        return list_presets()

    @app.get("/api/effects")
    def effects():
        return to_json()

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)):
        name = Path(file.filename or "video.mp4").name
        dst = uploads / f"{uuid.uuid4().hex[:6]}_{name}"
        with dst.open("wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        return {"path": str(dst), "name": name}

    @app.post("/api/edit")
    def edit(video: str = Form(...), command: str = Form(""), frames: str = Form(""), preset: str = Form(""),
             variants: int = Form(1), use_llm: str = Form("auto"), draft: bool = Form(False), critic: int = Form(-1),
             text_lang: str = Form("auto"),
             sfx_volume: float = Form(-1), music_volume: float = Form(-1)):
        if not Path(video).exists():
            raise HTTPException(404, "không thấy video")
        opt = JobOptions(
            command=command, frames=[f.strip() for f in frames.split(",") if f.strip()] or None, preset=preset or None,
            out_dir=out_dir, draft=draft, variants=max(1, min(3, variants)), critic_rounds=None if critic < 0 else critic,
            sfx_volume=None if sfx_volume < 0 else sfx_volume, music_volume=None if music_volume < 0 else music_volume,
            use_llm={"on": True, "off": False}.get(use_llm), text_language=None if text_lang == "auto" else text_lang,
        )
        job = Job(id=uuid.uuid4().hex[:8], kind="edit", params={"video": video, "command": command})
        JOBS[job.id] = job
        threading.Thread(target=_run, args=(job, lambda: run_job(video, opt)), daemon=True).start()
        return {"job": job.id}

    @app.post("/api/revise")
    def revise(plan: str = Form(...), instruction: str = Form(...), use_llm: str = Form("auto"), draft: bool = Form(False)):
        if not Path(plan).exists():
            raise HTTPException(404, "không thấy kế hoạch")
        opt = JobOptions(out_dir=out_dir, draft=draft, use_llm={"on": True, "off": False}.get(use_llm))
        job = Job(id=uuid.uuid4().hex[:8], kind="revise", params={"plan": plan, "instruction": instruction})
        JOBS[job.id] = job
        threading.Thread(target=_run, args=(job, lambda: revise_job(plan, instruction, opt)), daemon=True).start()
        return {"job": job.id}

    @app.post("/api/choose")
    def choose(plan: str = Form(...), note: str = Form("")):
        from ..memory.store import remember_revision
        from ..perception.schema import VideoIndex

        p = Path(plan)
        idx = VideoIndex.model_validate(json.loads((p.parent / "index.json").read_text(encoding="utf-8")))
        remember_revision(idx, f"Người dùng chọn phương án {p.stem} {note}".strip())
        return {"ok": True}

    @app.get("/api/jobs/{jid}")
    def job_status(jid: str, since: int = 0):
        job = JOBS.get(jid)
        if not job:
            raise HTTPException(404, "không có job")
        critic = []
        for pl in job.plans:
            cj = Path(pl).with_name(Path(pl).name.replace(".plan.json", ".critic.json"))
            if cj.exists():
                critic.append(json.loads(cj.read_text(encoding="utf-8")))
        return {
            "id": job.id, "kind": job.kind, "status": job.status, "logs": job.logs[since:], "next": len(job.logs),
            "outputs": [{"path": o, "url": rel(o)} for o in job.outputs], "plans": job.plans,
            "summary": job.summary, "error": job.error, "critic": critic,
        }

    @app.get("/api/jobs")
    def jobs():
        return [{"id": j.id, "kind": j.kind, "status": j.status, "params": j.params, "created": j.created}
                for j in sorted(JOBS.values(), key=lambda j: -j.created)]

    @app.get("/api/plan")
    def plan(path: str):
        p = Path(path)
        if not p.exists():
            raise HTTPException(404)
        return FileResponse(p)

    return app


def serve(host: str = "127.0.0.1", port: int = 7860, out_dir: Path = Path("outputs")) -> None:
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit("Cần cài: pip install 'director-video[studio]'") from e
    print(f"Director Studio: http://{host}:{port}")
    uvicorn.run(create_app(out_dir), host=host, port=port, log_level="warning")
