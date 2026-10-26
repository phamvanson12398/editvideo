"""Long-term memory (SQLite): series recognition by character appearance, and user preferences.

- Series: when a new video's characters look like a known series, reuse names, caption colors and style.
- Preferences: past commands / revision requests, summarized into the LLM prompt.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

import numpy as np

from ..perception.schema import VideoIndex
from ..style.dna import StyleDNA
from ..utils.log import log


def db_path() -> Path:
    base = Path(os.environ.get("DIRECTOR_HOME") or Path.home() / ".director")
    base.mkdir(parents=True, exist_ok=True)
    return base / "memory.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.execute("""CREATE TABLE IF NOT EXISTS series (
        id TEXT PRIMARY KEY, name TEXT, style TEXT, created REAL, updated REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS characters (
        series_id TEXT, char_key TEXT, name TEXT, color TEXT, feature TEXT, appearances INTEGER,
        PRIMARY KEY (series_id, char_key))""")
    con.execute("""CREATE TABLE IF NOT EXISTS prefs (
        ts REAL, series_id TEXT, kind TEXT, text TEXT)""")
    return con


def _vec(f: list[float]) -> np.ndarray:
    v = np.asarray(f, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def match_series(idx: VideoIndex, thr: float = 0.9) -> tuple[str | None, dict[str, dict]]:
    """Return (series_id, mapping new char id -> stored {key, name, color})."""
    chars = [c for c in idx.characters if c.feature]
    if not chars:
        return None, {}
    con = _conn()
    rows = con.execute("SELECT series_id, char_key, name, color, feature FROM characters").fetchall()
    con.close()
    by_series: dict[str, list[tuple]] = {}
    for r in rows:
        by_series.setdefault(r[0], []).append(r)
    best_sid, best_score, best_map = None, 0.0, {}
    for sid, stored in by_series.items():
        mapping, sims = {}, []
        for c in chars[:6]:
            v = _vec(c.feature)
            scored = [(float(v @ _vec(json.loads(s[4]))), s) for s in stored]
            if not scored:
                continue
            sim, s = max(scored, key=lambda x: x[0])
            sims.append(sim)
            if sim >= thr:
                mapping[c.id] = {"key": s[1], "name": s[2], "color": s[3]}
        score = float(np.mean(sims)) if sims else 0.0
        if mapping and score > best_score:
            best_sid, best_score, best_map = sid, score, mapping
    if best_sid and best_score >= thr * 0.95:
        return best_sid, best_map
    return None, {}


def apply_series_memory(idx: VideoIndex, style: StyleDNA) -> None:
    try:
        sid, mapping = match_series(idx)
    except Exception:
        return
    if not sid:
        return
    idx.series_id = sid
    for c in idx.characters:
        m = mapping.get(c.id)
        if m:
            c.name = c.name or m["name"]
            c.color = m["color"] or c.color
    con = _conn()
    row = con.execute("SELECT name, style FROM series WHERE id=?", (sid,)).fetchone()
    con.close()
    log(f"Nhận ra bộ phim đã dựng trước đây ({row[0] if row else sid}): dùng lại tên & màu nhân vật.")
    if row and row[1] and not style.description:
        stored = StyleDNA.model_validate_json(row[1])
        style.__dict__.update(stored.__dict__)


def remember_job(idx: VideoIndex, style: StyleDNA, command: str) -> None:
    try:
        con = _conn()
        sid = idx.series_id or str(uuid.uuid4())[:8]
        now = time.time()
        con.execute("INSERT OR IGNORE INTO series (id, name, style, created, updated) VALUES (?,?,?,?,?)",
                    (sid, Path(idx.source.path).stem, style.model_dump_json(), now, now))
        con.execute("UPDATE series SET style=?, updated=? WHERE id=?", (style.model_dump_json(), now, sid))
        for c in idx.characters:
            if not c.feature:
                continue
            con.execute("""INSERT INTO characters (series_id, char_key, name, color, feature, appearances)
                           VALUES (?,?,?,?,?,?)
                           ON CONFLICT(series_id, char_key) DO UPDATE SET
                             name=COALESCE(excluded.name, characters.name), color=excluded.color,
                             feature=excluded.feature, appearances=characters.appearances + excluded.appearances""",
                        (sid, c.id, c.name, c.color, json.dumps(c.feature), c.appearances))
        if command.strip():
            con.execute("INSERT INTO prefs (ts, series_id, kind, text) VALUES (?,?,?,?)", (now, sid, "command", command))
        con.commit()
        con.close()
        idx.series_id = sid
    except Exception as e:
        log(f"Không ghi được bộ nhớ: {e}")


def remember_revision(idx: VideoIndex, instruction: str) -> None:
    try:
        con = _conn()
        con.execute("INSERT INTO prefs (ts, series_id, kind, text) VALUES (?,?,?,?)", (time.time(), idx.series_id, "revision", instruction))
        con.commit()
        con.close()
    except Exception:
        pass


def preference_notes(limit: int = 12) -> list[str]:
    """Recent commands and revision requests, newest first (fed to the LLM as user taste)."""
    try:
        con = _conn()
        rows = con.execute("SELECT kind, text FROM prefs ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        con.close()
    except Exception:
        return []
    return [f"[{'lệnh' if k == 'command' else 'sửa'}] {t}" for k, t in rows]
