"""AI model helpers: JSON answers with validation + self-repair, images/video from the job.

Default provider: **Antigravity CLI** (`agy`, Google's replacement for Gemini CLI). Log in once with a
Google account by running `agy`; no API key. The tool writes the request (text + images + video) into a
temporary folder and runs `agy -p ... --output-format json` there; the agent reads the files itself.

Optional providers, only when chosen explicitly with DIRECTOR_LLM=gemini|claude:
- gemini: Gemini API with GEMINI_API_KEY / GOOGLE_API_KEY.
- claude: Anthropic API with ANTHROPIC_API_KEY.

Content blocks are passed around in one neutral format:
  {"type": "text", "text": ...} | {"type": "image", "source": {...base64 jpeg...}} | {"type": "video", "path": ...}
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from ..utils.log import log, warn

GEMINI_MODELS = [m for m in (os.environ.get("DIRECTOR_GEMINI_MODEL"), "gemini-pro-latest", "gemini-flash-latest", "gemini-2.5-flash") if m]
CLAUDE_MODEL = os.environ.get("DIRECTOR_MODEL", "claude-opus-5-5")
CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    pass


def _gemini_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _claude_key() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE"):
        return True
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "anthropic"
    return cfg.exists() and any(cfg.iterdir())


def agy_bin() -> str | None:
    """Antigravity CLI executable."""
    if os.environ.get("AGY_BIN"):
        return os.environ["AGY_BIN"]
    for name in ("agy", "agy.exe", "agy.cmd"):
        p = shutil.which(name)
        if p:
            return p
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for cand in (Path(local) / "agy" / "bin" / "agy.exe", Path(local) / "Antigravity" / "agy.exe",
                     Path(local) / "Antigravity" / "bin" / "agy.exe"):
            if cand.exists():
                return str(cand)
    home = Path.home() / ".local" / "bin" / "agy"
    return str(home) if home.exists() else None


def provider() -> str | None:
    if os.environ.get("DIRECTOR_NO_LLM"):
        return None
    want = os.environ.get("DIRECTOR_LLM", "").lower()
    if want == "gemini":
        return "gemini" if _gemini_key() else None
    if want == "claude":
        return "claude" if _claude_key() else None
    return "antigravity" if agy_bin() else None


def available() -> bool:
    return provider() is not None


def provider_label() -> str:
    return {"antigravity": "Antigravity", "gemini": "Gemini API", "claude": "Claude"}.get(provider() or "", "AI")


def image_block(path: str | Path, max_side: int = 768) -> dict:
    import cv2

    img = cv2.imread(str(path))
    if img is None:
        raise LLMError(f"không đọc được ảnh {path}")
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(buf.tobytes()).decode()}}


def video_block(path: str | Path) -> dict:
    """A whole video (Antigravity/Gemini can watch it; Claude skips it and relies on the frames)."""
    return {"type": "video", "path": str(path)}


def extract_json(text: str) -> Any:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    start = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("không có JSON trong câu trả lời")
    end = max(t.rfind("}"), t.rfind("]"))
    return json.loads(t[start:end + 1])


# ---------------------------------------------------------------- Antigravity CLI (agy)


class AntigravityAuthError(LLMError):
    pass


def _write_request(system: str, messages: list[dict], workdir: Path) -> list[str]:
    """Write the conversation into workdir/REQUEST.md (+ image/video files). Returns attachment names."""
    attachments: list[str] = []
    lines = [f"# VAI TRÒ\n{system}\n"]
    img_no = 0
    for m in messages:
        lines.append("\n# NGƯỜI DÙNG" if m["role"] == "user" else "\n# CÂU TRẢ LỜI TRƯỚC ĐÓ CỦA BẠN")
        content = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        for b in content:
            t = b.get("type")
            if t == "text":
                lines.append(b["text"])
            elif t == "image":
                name = f"img_{img_no:03d}.jpg"
                img_no += 1
                (workdir / name).write_bytes(base64.b64decode(b["source"]["data"]))
                attachments.append(name)
                lines.append(f"[Ảnh: {name}]")
            elif t == "video":
                src = Path(b["path"])
                name = f"video_{len(attachments):03d}{src.suffix.lower() or '.mp4'}"
                try:
                    try:
                        os.link(src, workdir / name)
                    except OSError:
                        if src.stat().st_size > 500 * 1024 * 1024:
                            raise
                        shutil.copyfile(src, workdir / name)
                    attachments.append(name)
                    lines.append(f"[Video: {name}]")
                except OSError:
                    warn(f"Không đính kèm được video {src.name}, AI chỉ xem ảnh.")
    lines.append("\n# YÊU CẦU ĐẦU RA\nChỉ trả lời bằng MỘT đối tượng JSON hợp lệ, không thêm chữ nào khác. "
                 "Chỉ đọc/xem các file trong thư mục này, không sửa, không tạo file, không chạy lệnh.")
    (workdir / "REQUEST.md").write_text("\n".join(lines), encoding="utf-8")
    return attachments


def _call_antigravity(system: str, messages: list[dict]) -> str:
    exe = agy_bin()
    if not exe:
        raise LLMError("Không tìm thấy Antigravity CLI (agy). Chạy 6_CAI_ANTIGRAVITY.bat để cài và đăng nhập.")
    base = Path(os.environ.get("DIRECTOR_HOME") or Path.home() / ".director") / "ai_tmp"
    base.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="req_", dir=base))
    try:
        attachments = _write_request(system, messages, workdir)
        media = ", ".join(attachments)
        prompt = ("Read the file REQUEST.md in the current folder and do exactly what it asks."
                  + (f" Look at these attached files in the same folder: {media}." if media else "")
                  + " Reply with ONLY the JSON object. Do not modify or create any file.")
        cmd = [exe, "-p", prompt, "--output-format", "json"]
        cmd += [a for a in os.environ.get("DIRECTOR_AGY_ARGS", "").split() if a]  # e.g. a model flag
        last = ""
        for attempt in range(3):
            proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=int(os.environ.get("DIRECTOR_AGY_TIMEOUT", "1800")),
                                  stdin=subprocess.DEVNULL)
            out = (proc.stdout or "").strip()
            err_text = (proc.stderr or "")[-2000:]
            data = None
            if "{" in out:
                try:
                    data = json.loads(out[out.find("{"):out.rfind("}") + 1])
                except json.JSONDecodeError:
                    data = None
            if isinstance(data, dict):
                status = str(data.get("status", "")).upper()
                resp = data.get("response")
                if resp and status in ("", "SUCCESS"):
                    return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
                err = data.get("error")
                last = f"status={status} {err if err else ''}".strip()
                if status == "WAITING":
                    last += " (agy đang chờ cấp quyền; tool chỉ cần quyền đọc file trong thư mục tạm)"
            elif proc.returncode == 0 and out:
                return out  # plain text output: ask_json extracts the JSON
            else:
                last = err_text or out or f"exit {proc.returncode}"
            low = (last + err_text).lower()
            if any(k in low for k in ("login", "sign in", "authenticat", "credential", "oauth")):
                raise AntigravityAuthError("Antigravity CLI chưa đăng nhập. Mở cửa sổ lệnh, gõ `agy` và đăng nhập tài khoản Google "
                                           "(hoặc chạy 6_CAI_ANTIGRAVITY.bat).")
            if "flags provided but not defined" in low and "output-format" in low:
                cmd = [c for c in cmd if c not in ("--output-format", "json")]  # very old agy build
                continue
            if any(k in low for k in ("quota", "rate limit", "429", "resource exhausted")):
                wait = 30 * (attempt + 1)
                log(f"Antigravity báo hết hạn mức tạm thời, chờ {wait}s...")
                time.sleep(wait)
                continue
            time.sleep(3)
        raise LLMError(f"Antigravity CLI lỗi: {last}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------- Gemini API (optional)

_gclient = None
_uploaded: dict[str, Any] = {}


def _gemini():
    global _gclient
    if _gclient is None:
        try:
            from google import genai
        except ImportError as e:
            raise LLMError("Chưa cài thư viện Gemini: pip install google-genai") from e
        _gclient = genai.Client(api_key=_gemini_key())
    return _gclient


def _gemini_upload(path: str) -> Any:
    if path in _uploaded:
        return _uploaded[path]
    client = _gemini()
    log(f"Tải video lên Gemini để AI xem: {Path(path).name}")
    f = client.files.upload(file=path)
    deadline = time.time() + 300
    while getattr(f.state, "name", str(f.state)) == "PROCESSING" and time.time() < deadline:
        time.sleep(3)
        f = client.files.get(name=f.name)
    if getattr(f.state, "name", str(f.state)) != "ACTIVE":
        raise LLMError(f"Gemini không xử lý được video ({f.state})")
    _uploaded[path] = f
    return f


def _gemini_parts(content: list[dict]) -> list:
    from google.genai import types

    parts: list = []
    for b in content:
        t = b.get("type")
        if t == "text":
            parts.append(types.Part.from_text(text=b["text"]))
        elif t == "image":
            parts.append(types.Part.from_bytes(data=base64.b64decode(b["source"]["data"]), mime_type=b["source"]["media_type"]))
        elif t == "video":
            try:
                f = _gemini_upload(b["path"])
                parts.append(types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type or "video/mp4"))
            except Exception as e:
                warn(f"Không gửi được video cho Gemini, chỉ dùng ảnh: {e}")
    return parts


def _call_gemini(system: str, messages: list[dict], max_tokens: int) -> str:
    from google.genai import errors, types

    contents = []
    for m in messages:
        content = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        contents.append(types.Content(role="model" if m["role"] == "assistant" else "user", parts=_gemini_parts(content)))
    config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens,
                                         response_mime_type="application/json")
    last: Exception | None = None
    for model in list(dict.fromkeys(GEMINI_MODELS)):
        for attempt in range(3):
            try:
                resp = _gemini().models.generate_content(model=model, contents=contents, config=config)
                text = resp.text or ""
                if not text:
                    reason = getattr(resp.candidates[0], "finish_reason", None) if resp.candidates else None
                    raise LLMError(f"Gemini trả về rỗng (finish_reason={reason})")
                return text
            except errors.ClientError as e:  # 4xx: bad key, unknown model, quota
                last = e
                code = getattr(e, "code", None)
                if code == 404:
                    log(f"Model {model} không dùng được, thử model khác...")
                    break
                if code == 429:
                    wait = 20 * (attempt + 1)
                    log(f"Gemini báo hết hạn mức tạm thời, chờ {wait}s...")
                    time.sleep(wait)
                    continue
                raise LLMError(f"Gemini từ chối yêu cầu ({code}): {e}") from e
            except errors.ServerError as e:  # 5xx: retry
                last = e
                time.sleep(5 * (attempt + 1))
    raise LLMError(f"Không gọi được Gemini: {last}")


# ---------------------------------------------------------------- Claude

_cclient = None


def client():
    """Anthropic client (Claude provider)."""
    global _cclient
    if _cclient is None:
        import anthropic

        _cclient = anthropic.Anthropic()
    return _cclient


def _call_claude(system: str, messages: list[dict], effort: str, max_tokens: int) -> str:
    import anthropic

    clean = []
    for m in messages:
        c = m["content"]
        if isinstance(c, list):
            c = [b for b in c if b.get("type") != "video"]  # Claude gets the frames instead
        clean.append({"role": m["role"], "content": c})
    kwargs = dict(model=CLAUDE_MODEL, max_tokens=max_tokens, system=system, messages=clean, output_config={"effort": effort})
    try:
        with client().beta.messages.stream(**kwargs, betas=[CLAUDE_FALLBACK_BETA], fallbacks="default") as stream:
            msg = stream.get_final_message()
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        with client().messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        cat = getattr(getattr(msg, "stop_details", None), "category", None)
        raise LLMError(f"Claude từ chối yêu cầu (category={cat}).")
    if msg.stop_reason == "max_tokens":
        log("CẢNH BÁO: câu trả lời của Claude bị cắt (max_tokens).")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# ---------------------------------------------------------------- common


def _call(system: str, messages: list[dict], effort: str, max_tokens: int) -> str:
    p = provider()
    if p == "antigravity":
        return _call_antigravity(system, messages)
    if p == "gemini":
        return _call_gemini(system, messages, max_tokens)
    if p == "claude":
        return _call_claude(system, messages, effort, max_tokens)
    raise LLMError("Chưa có AI: cài và đăng nhập Antigravity CLI (chạy 6_CAI_ANTIGRAVITY.bat).")


def ask_json(system: str, content: list[dict] | str, *, validate: Callable[[Any], Any] | None = None,
             effort: str = "high", max_tokens: int = 32000, retries: int = 2) -> Any:
    """Ask for a JSON answer; on parse/validation errors, show the model the error and ask for a fix."""
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    messages: list[dict] = [{"role": "user", "content": content}]
    last_err = None
    for attempt in range(retries + 1):
        text = _call(system, messages, effort, max_tokens)
        try:
            data = extract_json(text)
            return validate(data) if validate else data
        except Exception as e:  # noqa: BLE001 - any parse/validation problem is fed back
            last_err = e
            log(f"JSON từ AI chưa hợp lệ (lần {attempt + 1}): {str(e)[:200]}")
            messages += [
                {"role": "assistant", "content": text or "(trống)"},
                {"role": "user", "content": f"JSON trên không hợp lệ: {str(e)[:1500]}\nHãy trả lại DUY NHẤT một JSON đã sửa, đúng schema."},
            ]
    raise LLMError(f"AI không trả được JSON hợp lệ: {last_err}")
