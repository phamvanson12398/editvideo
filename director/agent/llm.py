"""Claude client helpers: JSON answers with validation + self-repair, images from keyframes."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from ..utils.log import log

MODEL = os.environ.get("DIRECTOR_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    pass


def available() -> bool:
    if os.environ.get("DIRECTOR_NO_LLM"):
        return False
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_PROFILE"):
        return True
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "anthropic"
    return cfg.exists() and any(cfg.iterdir())


_client = None


def client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


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


def _call(system: str, messages: list[dict], effort: str, max_tokens: int) -> str:
    import anthropic

    kwargs = dict(
        model=MODEL, max_tokens=max_tokens, system=system, messages=messages,
        output_config={"effort": effort},
    )
    try:
        with client().beta.messages.stream(**kwargs, betas=[FALLBACK_BETA], fallbacks="default") as stream:
            msg = stream.get_final_message()
    except anthropic.BadRequestError as e:
        # Model or platform without server-side fallback support: retry plain.
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


def ask_json(system: str, content: list[dict] | str, *, validate: Callable[[Any], Any] | None = None,
             effort: str = "high", max_tokens: int = 32000, retries: int = 2) -> Any:
    """Ask for a JSON answer; on parse/validation errors, show Claude the error and ask for a fix."""
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
            log(f"JSON từ Claude chưa hợp lệ (lần {attempt + 1}): {str(e)[:200]}")
            messages += [
                {"role": "assistant", "content": text or "(trống)"},
                {"role": "user", "content": f"JSON trên không hợp lệ: {str(e)[:1500]}\nHãy trả lại DUY NHẤT một JSON đã sửa, đúng schema."},
            ]
    raise LLMError(f"Claude không trả được JSON hợp lệ: {last_err}")
