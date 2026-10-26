"""Effect usage rules: budget, cooldown, no repeats, breathing room, escalation (docs/EFFECTS.md §13).

Works on timeline-time candidates so it can be applied to any planner's output."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..style.dna import StyleDNA
from .catalog import COMBOS, EFFECTS, STRONG_COMBOS


@dataclass
class Candidate:
    id: str
    t: float  # timeline seconds
    priority: float = 0.5  # 0..1; higher wins conflicts
    payload: dict = field(default_factory=dict)
    forced: bool = False  # user-requested / structural (hook, ending): bypasses budget

    @property
    def strong(self) -> bool:
        if self.id in COMBOS:
            return self.id in STRONG_COMBOS
        e = EFFECTS.get(self.id)
        return bool(e and e.strength == "strong")

    @property
    def category(self) -> str:
        if self.id in COMBOS:
            return "combo"
        e = EFFECTS.get(self.id)
        return e.category if e else "?"


INTENSITY_SCALE = {"minimal": 0.0, "low": 0.5, "medium": 1.0, "high": 1.6, "extreme": 2.4}

# Categories that never compete for the "small effect" budget (structural / persistent).
FREE_CATEGORIES = {"edit", "time", "layout", "audio", "color"}


def apply_rules(cands: list[Candidate], style: StyleDNA, duration: float) -> list[Candidate]:
    b = style.budget
    scale = INTENSITY_SCALE.get(b.intensity, 1.0)
    banned = set(style.banned_effects)
    if scale <= 0:
        return [c for c in cands if c.forced and c.id not in banned]
    strong_gap = b.strong_combo_every_sec / scale
    small_gap = b.small_effect_every_sec / scale
    cooldown = b.cooldown_sec / max(scale, 0.5)
    breath = 2.0 / scale

    kept: list[Candidate] = []
    last_strong = -1e9
    last_small = -1e9
    last_by_id: dict[str, float] = {}
    prev_id = None
    # escalation: before the global peak, dampen strong effects in the first 30% of the video
    for c in sorted(cands, key=lambda c: (c.t, -c.priority)):
        if c.id in banned:
            continue
        if c.forced:
            kept.append(c)
            last_by_id[c.id] = c.t
            if c.strong:
                last_strong = c.t
            continue
        if c.t - last_by_id.get(c.id, -1e9) < cooldown:
            continue
        if c.strong:
            early = c.t < 0.3 * duration and c.priority < 0.85
            if early or c.t - last_strong < strong_gap:
                continue
            last_strong = c.t
        elif c.category not in FREE_CATEGORIES:
            if c.t - last_small < small_gap or c.t - last_strong < breath:
                continue
            if prev_id == c.id:
                continue
            last_small = c.t
        kept.append(c)
        last_by_id[c.id] = c.t
        prev_id = c.id
    return kept
