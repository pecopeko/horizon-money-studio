"""Pure-Python kinetic animation timeline, easing, and subtitle timing engine.

Zero third-party dependencies so this module can be imported and tested in
any Python 3.9+ / 3.11+ environment (with or without Pillow installed).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ---------------------------------------------------------------------------
# Easing primitives
# ---------------------------------------------------------------------------


def clamp01(t: float) -> float:
    """Clamp a normalized progress value to [0.0, 1.0]."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return float(t)


def ease_out_expo(t: float) -> float:
    """Fast launch with crisp exponential deceleration."""
    x = clamp01(t)
    if x >= 1.0:
        return 1.0
    return 1.0 - math.pow(2.0, -10.0 * x)


def ease_out_cubic(t: float) -> float:
    """Smooth cubic ease-out."""
    x = clamp01(t)
    inv = 1.0 - x
    return 1.0 - inv * inv * inv


def ease_in_out_cubic(t: float) -> float:
    """Balanced S-curve easing for multi-period chart transitions."""
    x = clamp01(t)
    if x < 0.5:
        return 4.0 * x * x * x
    inv = -2.0 * x + 2.0
    return 1.0 - (inv * inv * inv) / 2.0


def ease_out_back(t: float, overshoot: float = 1.45) -> float:
    """Spring-like overshoot settle for headline hooks and milestone callouts."""
    x = clamp01(t)
    c3 = overshoot + 1.0
    shifted = x - 1.0
    return 1.0 + c3 * (shifted ** 3) + overshoot * (shifted ** 2)


# ---------------------------------------------------------------------------
# Video specification dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BarRaceEntry:
    """Single entity tracked across one or more chronological periods."""

    key: str
    label: str
    color: str
    values: List[float]
    badge: str = ""
    end_period_note: str = ""

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("BarRaceEntry.key must be non-empty")
        if not self.values:
            raise ValueError("BarRaceEntry.values must contain at least one value")
        self.values = [float(v) for v in self.values]


@dataclass
class BarRaceSpec:
    """Complete declarative specification for a kinetic horizontal bar race Short."""

    title: str
    highlight_phrase: str
    subtitle: str
    category_badge: str
    source_label: str
    cta_text: str
    periods: List[str]
    entries: List[BarRaceEntry]
    narration_script: str
    unit_prefix: str = "$"
    unit_suffix: str = "B"
    value_decimals: int = 1
    total_label: str = "COMBINED TOTAL"
    lang: str = "en"
    provenance: Dict[str, Any] = field(default_factory=dict)
    kind: str = "bar_race"

    def __post_init__(self) -> None:
        if not self.periods:
            raise ValueError("BarRaceSpec.periods must be non-empty")
        if not self.entries:
            raise ValueError("BarRaceSpec.entries must be non-empty")
        expected = len(self.periods)
        for entry in self.entries:
            if len(entry.values) != expected:
                raise ValueError(
                    "Entry %s has %d values, expected %d matching periods"
                    % (entry.key, len(entry.values), expected)
                )


@dataclass
class LinePoint:
    """Single chronological observation for a macro time-series curve."""

    date_label: str
    display_date: str
    value: float


@dataclass
class LineMilestone:
    """Annotated callout pin that pops in when the curve reaches `index`."""

    index: int
    label: str
    value_text: str
    subtext: str
    color: str = "#F59E0B"
    align_above: bool = True
    x_nudge: float = 0.0


@dataclass
class MacroLineSpec:
    """Complete declarative specification for a kinetic time-series line Short."""

    title: str
    highlight_phrase: str
    subtitle: str
    category_badge: str
    source_label: str
    cta_text: str
    points: List[LinePoint]
    milestones: List[LineMilestone]
    narration_script: str
    unit_prefix: str = ""
    unit_suffix: str = "%"
    value_decimals: int = 2
    y_min: float = 0.0
    y_max: float = 6.0
    y_step: float = 1.0
    line_color: str = "#38BDF8"
    lang: str = "en"
    provenance: Dict[str, Any] = field(default_factory=dict)
    kind: str = "macro_line"

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("MacroLineSpec.points must contain at least 2 points")
        if self.y_max <= self.y_min:
            raise ValueError("MacroLineSpec.y_max must exceed y_min")
        if self.y_step <= 0:
            raise ValueError("MacroLineSpec.y_step must be positive")


VideoSpec = Union[BarRaceSpec, MacroLineSpec]


# ---------------------------------------------------------------------------
# JSON Spec Loader (supports any custom dataset: Polymarket, JP tax, AI prices)
# ---------------------------------------------------------------------------


def load_video_spec_dict(raw: Dict[str, Any]) -> VideoSpec:
    """Validate and construct a BarRaceSpec or MacroLineSpec from a JSON dict."""
    kind = str(raw.get("kind", "")).strip().lower()
    if kind == "bar_race":
        entries = [
            BarRaceEntry(
                key=str(e["key"]),
                label=str(e["label"]),
                color=str(e.get("color", "#38BDF8")),
                values=[float(v) for v in e["values"]],
                badge=str(e.get("badge", "")),
                end_period_note=str(e.get("end_period_note", "")),
            )
            for e in raw["entries"]
        ]
        return BarRaceSpec(
            title=str(raw["title"]),
            highlight_phrase=str(raw.get("highlight_phrase", "")),
            subtitle=str(raw.get("subtitle", "")),
            category_badge=str(raw.get("category_badge", "DATA VISUALIZATION")),
            source_label=str(raw.get("source_label", "PUBLIC DATASET")),
            cta_text=str(raw.get("cta_text", "CODE & DATA IN DESCRIPTION")),
            periods=[str(p) for p in raw["periods"]],
            entries=entries,
            narration_script=str(raw["narration_script"]),
            unit_prefix=str(raw.get("unit_prefix", "$")),
            unit_suffix=str(raw.get("unit_suffix", "B")),
            value_decimals=int(raw.get("value_decimals", 1)),
            total_label=str(raw.get("total_label", "COMBINED TOTAL")),
            lang=str(raw.get("lang", "en")),
            provenance=dict(raw.get("provenance", {})),
        )
    if kind == "macro_line":
        points = [
            LinePoint(
                date_label=str(p["date_label"]),
                display_date=str(p.get("display_date", p["date_label"])),
                value=float(p["value"]),
            )
            for p in raw["points"]
        ]
        milestones = [
            LineMilestone(
                index=int(m["index"]),
                label=str(m["label"]),
                value_text=str(m["value_text"]),
                subtext=str(m.get("subtext", "")),
                color=str(m.get("color", "#F59E0B")),
                align_above=bool(m.get("align_above", True)),
                x_nudge=float(m.get("x_nudge", 0.0)),
            )
            for m in raw.get("milestones", [])
        ]
        return MacroLineSpec(
            title=str(raw["title"]),
            highlight_phrase=str(raw.get("highlight_phrase", "")),
            subtitle=str(raw.get("subtitle", "")),
            category_badge=str(raw.get("category_badge", "MACRO DATA")),
            source_label=str(raw.get("source_label", "PUBLIC DATASET")),
            cta_text=str(raw.get("cta_text", "CODE & DATA IN DESCRIPTION")),
            points=points,
            milestones=milestones,
            narration_script=str(raw["narration_script"]),
            unit_prefix=str(raw.get("unit_prefix", "")),
            unit_suffix=str(raw.get("unit_suffix", "%")),
            value_decimals=int(raw.get("value_decimals", 2)),
            y_min=float(raw.get("y_min", 0.0)),
            y_max=float(raw.get("y_max", 6.0)),
            y_step=float(raw.get("y_step", 1.0)),
            line_color=str(raw.get("line_color", "#38BDF8")),
            lang=str(raw.get("lang", "en")),
            provenance=dict(raw.get("provenance", {})),
        )
    raise ValueError("Unsupported spec kind %r (expected 'bar_race' or 'macro_line')" % (kind,))


def load_video_spec_json(path: Union[str, Path]) -> VideoSpec:
    """Load and validate a custom JSON dataset spec from disk."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("JSON spec root must be an object")
    return load_video_spec_dict(raw)


# ---------------------------------------------------------------------------
# Bar-race interpolation state
# ---------------------------------------------------------------------------


@dataclass
class BarRaceItemFrame:
    """Interpolated per-bar state at timestamp `t`."""

    key: str
    label: str
    color: str
    value: float
    rank_pos: float  # 0.0 = top lane, N-1 = bottom lane (smoothly animated!)
    rank_int: int
    badge: str
    badge_alpha: float
    end_period_note: str


@dataclass
class BarRaceFrameState:
    """Complete interpolated bar-race chart state at timestamp `t`."""

    period_label: str
    period_progress: float  # 0.0 .. 1.0 overall race completion
    axis_max: float
    combined_total: float
    hook_progress: float
    in_finale: bool
    items: List[BarRaceItemFrame]


def _nice_axis_ceil(value: float) -> float:
    """Compute a clean rounded upper chart axis bound strictly above `value`."""
    if value <= 0.0:
        return 10.0
    target = value * 1.12
    exp = math.floor(math.log10(target))
    base = 10.0 ** exp
    for mult in (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        cand = mult * base
        if cand >= target:
            return cand
    return 10.0 * base


def _rank_map_for_values(values_by_key: Dict[str, float]) -> Dict[str, int]:
    """Return 0-based rank (0 = highest value) with stable deterministic tie-break."""
    ordered = sorted(values_by_key.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: idx for idx, (k, _) in enumerate(ordered)}


def interpolate_bar_race_frame(
    spec: BarRaceSpec,
    t: float,
    duration: float,
) -> BarRaceFrameState:
    """Compute smooth bar values, lane ranks, and rolling counters at time `t`."""
    safe_dur = max(duration, 1.0)
    t_clamped = max(0.0, min(t, safe_dur))
    hook_progress = ease_out_back(clamp01(t_clamped / 1.15), overshoot=1.25)

    num_periods = len(spec.periods)
    intro_end = min(1.35, safe_dur * 0.14)
    hold_duration = min(2.8, safe_dur * 0.22)
    race_end = max(intro_end + 0.5, safe_dur - hold_duration)

    # Global nice axis ceiling anchored gently so bars show dramatic scale growth
    # while keeping axis lines stable and readable.
    global_max = max(max(e.values) for e in spec.entries)
    axis_max = _nice_axis_ceil(global_max)

    if num_periods == 1:
        # Single-snapshot staggered kinetic entrance from 0 -> final value
        n = len(spec.entries)
        final_vals = {e.key: e.values[0] for e in spec.entries}
        final_ranks = _rank_map_for_values(final_vals)
        items: List[BarRaceItemFrame] = []
        total = 0.0
        for entry in spec.entries:
            rank_i = final_ranks[entry.key]
            stagger = 0.18 + rank_i * 0.14
            span = max(0.8, race_end - stagger)
            prog = ease_out_expo(clamp01((t_clamped - stagger) / span))
            val = entry.values[0] * prog
            total += val
            badge_alpha = clamp01((t_clamped - (race_end - 0.8)) / 0.8)
            items.append(
                BarRaceItemFrame(
                    key=entry.key,
                    label=entry.label,
                    color=entry.color,
                    value=val,
                    rank_pos=float(rank_i),
                    rank_int=rank_i + 1,
                    badge=entry.badge,
                    badge_alpha=badge_alpha,
                    end_period_note=entry.end_period_note,
                )
            )
        items.sort(key=lambda it: it.rank_pos)
        return BarRaceFrameState(
            period_label=spec.periods[0],
            period_progress=clamp01(t_clamped / race_end),
            axis_max=axis_max,
            combined_total=total,
            hook_progress=hook_progress,
            in_finale=t_clamped >= race_end,
            items=items,
        )

    # Multi-period bar race: Phase 1 launches 0 -> period 0; Phase 2 glides 0 -> N-1
    if t_clamped < intro_end:
        p0_vals = {e.key: e.values[0] for e in spec.entries}
        p0_ranks = _rank_map_for_values(p0_vals)
        items = []
        total = 0.0
        for entry in spec.entries:
            rank_i = p0_ranks[entry.key]
            stagger = 0.12 + rank_i * 0.08
            local_t = clamp01((t_clamped - stagger) / max(0.35, intro_end - stagger))
            val = entry.values[0] * ease_out_expo(local_t)
            total += val
            items.append(
                BarRaceItemFrame(
                    key=entry.key,
                    label=entry.label,
                    color=entry.color,
                    value=val,
                    rank_pos=float(rank_i),
                    rank_int=rank_i + 1,
                    badge=entry.badge,
                    badge_alpha=0.0,
                    end_period_note="",
                )
            )
        items.sort(key=lambda it: it.rank_pos)
        return BarRaceFrameState(
            period_label=spec.periods[0],
            period_progress=0.0,
            axis_max=axis_max,
            combined_total=total,
            hook_progress=hook_progress,
            in_finale=False,
            items=items,
        )

    # Phase 2 & 3: smooth interpolation across periods 0 .. num_periods - 1
    race_frac = clamp01((t_clamped - intro_end) / max(0.5, race_end - intro_end))
    segments = num_periods - 1
    scaled = race_frac * segments
    idx0 = min(int(math.floor(scaled)), segments - 1)
    idx1 = idx0 + 1
    seg_t = ease_in_out_cubic(scaled - idx0) if race_frac < 1.0 else 1.0
    if race_frac >= 1.0:
        idx0 = segments - 1
        idx1 = segments
        seg_t = 1.0

    ranks0 = _rank_map_for_values({e.key: e.values[idx0] for e in spec.entries})
    ranks1 = _rank_map_for_values({e.key: e.values[idx1] for e in spec.entries})

    # Dynamic axis scaling: softly grows from early period to final period so early bars feel substantial
    curr_vals_raw = {
        e.key: e.values[idx0] + (e.values[idx1] - e.values[idx0]) * seg_t
        for e in spec.entries
    }
    curr_max = max(curr_vals_raw.values())
    # Smoothly blend from initial nice axis toward final global axis
    start_axis = _nice_axis_ceil(max(e.values[0] for e in spec.entries))
    axis_dynamic = max(
        start_axis + (axis_max - start_axis) * ease_out_cubic(race_frac),
        curr_max * 1.12,
    )

    display_period = spec.periods[idx1] if seg_t >= 0.55 else spec.periods[idx0]
    badge_alpha = clamp01((race_frac - 0.72) / 0.25)

    items = []
    total = 0.0
    current_ranks = _rank_map_for_values(curr_vals_raw)
    for entry in spec.entries:
        val = curr_vals_raw[entry.key]
        total += val
        r0 = float(ranks0[entry.key])
        r1 = float(ranks1[entry.key])
        smooth_rank = r0 + (r1 - r0) * seg_t
        items.append(
            BarRaceItemFrame(
                key=entry.key,
                label=entry.label,
                color=entry.color,
                value=val,
                rank_pos=smooth_rank,
                rank_int=current_ranks[entry.key] + 1,
                badge=entry.badge,
                badge_alpha=badge_alpha,
                end_period_note=entry.end_period_note if badge_alpha > 0.35 else "",
            )
        )
    items.sort(key=lambda it: it.rank_pos)
    return BarRaceFrameState(
        period_label=display_period,
        period_progress=race_frac,
        axis_max=axis_dynamic,
        combined_total=total,
        hook_progress=hook_progress,
        in_finale=t_clamped >= race_end,
        items=items,
    )


# ---------------------------------------------------------------------------
# Macro time-series line chart interpolation state
# ---------------------------------------------------------------------------


@dataclass
class MilestoneFrameState:
    """Milestone pin state with spring reveal scale in [0.0, ~1.05]."""

    milestone: LineMilestone
    point: LinePoint
    reveal: float


@dataclass
class LineChartFrameState:
    """Complete interpolated macro time-series state at timestamp `t`."""

    hook_progress: float
    draw_progress: float  # 0.0 .. 1.0 curve sweep
    visible_points: List[Tuple[float, float]]  # (fractional_index, value)
    head_index: float
    head_value: float
    head_display_date: str
    active_milestones: List[MilestoneFrameState]
    in_finale: bool


def interpolate_line_series(
    spec: MacroLineSpec,
    t: float,
    duration: float,
) -> LineChartFrameState:
    """Compute progressive curve coordinates, live rolling value, and active milestones."""
    safe_dur = max(duration, 1.0)
    t_clamped = max(0.0, min(t, safe_dur))
    hook_progress = ease_out_back(clamp01(t_clamped / 1.05), overshoot=1.2)

    start_draw = min(0.85, safe_dur * 0.10)
    hold_duration = min(2.8, safe_dur * 0.22)
    end_draw = max(start_draw + 0.5, safe_dur - hold_duration)

    raw_frac = clamp01((t_clamped - start_draw) / max(0.5, end_draw - start_draw))
    # Gentle ease at very start & end while keeping middle sweep steady so viewers read dates
    draw_progress = 0.72 * raw_frac + 0.28 * ease_in_out_cubic(raw_frac)

    max_idx = len(spec.points) - 1
    head_index = draw_progress * max_idx
    base_idx = min(int(math.floor(head_index)), max_idx)
    next_idx = min(base_idx + 1, max_idx)
    frac = head_index - base_idx

    visible: List[Tuple[float, float]] = [
        (float(i), spec.points[i].value) for i in range(base_idx + 1)
    ]
    head_value = spec.points[base_idx].value + (
        spec.points[next_idx].value - spec.points[base_idx].value
    ) * frac
    if frac > 1e-6 and next_idx != base_idx:
        visible.append((head_index, head_value))

    nearest_idx = min(int(round(head_index)), max_idx)
    head_display_date = spec.points[nearest_idx].display_date

    # Milestone pop-in timing: triggers right as head_index passes milestone.index
    active_milestones: List[MilestoneFrameState] = []
    draw_span = max(0.5, end_draw - start_draw)
    for ms in spec.milestones:
        if 0 <= ms.index <= max_idx:
            # Estimate time when head passes ms.index
            ms_frac = ms.index / float(max_idx)
            ms_trigger_t = start_draw + ms_frac * draw_span
            if head_index >= ms.index - 0.15:
                elapsed_since = max(0.0, t_clamped - ms_trigger_t)
                reveal = ease_out_back(clamp01(elapsed_since / 0.42), overshoot=1.35)
                if reveal > 0.02:
                    active_milestones.append(
                        MilestoneFrameState(
                            milestone=ms,
                            point=spec.points[ms.index],
                            reveal=reveal,
                        )
                    )

    return LineChartFrameState(
        hook_progress=hook_progress,
        draw_progress=draw_progress,
        visible_points=visible,
        head_index=head_index,
        head_value=head_value,
        head_display_date=head_display_date,
        active_milestones=active_milestones,
        in_finale=t_clamped >= end_draw,
    )


# ---------------------------------------------------------------------------
# Word/Phrase-Synced Kinetic Subtitles Engine
# ---------------------------------------------------------------------------


@dataclass
class TimedCaptionToken:
    """Single word or Japanese phrase segment with start/end timestamps."""

    text: str
    start: float
    end: float
    chunk_index: int


@dataclass
class CaptionChunk:
    """A 1-line screenful of words/phrases rendered inside the Shorts safe zone."""

    tokens: List[TimedCaptionToken]
    start: float
    end: float


def _tokenize_narration(script: str, lang: str) -> List[str]:
    """Split English narration by words or Japanese narration by natural phrases."""
    cleaned = re.sub(r"\s+", " ", script.strip())
    if not cleaned:
        return []
    if lang.lower().startswith("ja"):
        # Split on Japanese punctuation or spaces first, then slice long runs into 4-6 char phrases
        parts = re.split(r"([、。！？\s]+)", cleaned)
        tokens: List[str] = []
        buf = ""
        for part in parts:
            if not part or part.isspace():
                if buf:
                    tokens.append(buf)
                    buf = ""
                continue
            if re.fullmatch(r"[、。！？]+", part):
                if buf:
                    tokens.append(buf + part)
                    buf = ""
                elif tokens:
                    tokens[-1] += part
                continue
            # Split long non-punctuated Japanese runs cleanly into readable 5-char segments
            run = part
            while len(run) > 7:
                tokens.append(run[:5])
                run = run[5:]
            if run:
                buf = run
        if buf:
            tokens.append(buf)
        return [tok for tok in tokens if tok.strip()]
    return [tok for tok in cleaned.split(" ") if tok.strip()]


def _spoken_weight(token: str, lang: str) -> float:
    """Estimate relative spoken duration weight for proportional audio alignment."""
    stripped = re.sub(r"[^\w%$.¥円]", "", token)
    base = max(2.2, float(len(stripped)) * (1.8 if lang.lower().startswith("ja") else 0.92))
    if any(ch.isdigit() for ch in token):
        # Spoken numbers ("five point three three percent") take longer than spelling
        base += 2.6
    if token.endswith((".", "!", "?", "。", "！", "？")):
        base += 4.2
    elif token.endswith((",", ";", ":", "—", "、")):
        base += 2.2
    return base


def build_kinetic_caption_timeline(
    script: str,
    audio_duration: float,
    lang: str = "en",
    speech_start: float = 0.20,
    speech_end_pad: float = 0.18,
    max_words_per_chunk: int = 4,
    max_chars_per_chunk: int = 26,
) -> List[CaptionChunk]:
    """Build word-synced kinetic subtitle chunks locked to spoken audio duration."""
    raw_tokens = _tokenize_narration(script, lang=lang)
    if not raw_tokens:
        return []

    effective_start = max(0.0, speech_start)
    effective_end = max(effective_start + 0.5, audio_duration - speech_end_pad)
    span = effective_end - effective_start

    weights = [_spoken_weight(tok, lang) for tok in raw_tokens]
    total_weight = sum(weights)

    # Group tokens into short punchy screen chunks respecting sentence stops
    jp_mode = lang.lower().startswith("ja")
    char_limit = 15 if jp_mode else max_chars_per_chunk
    word_limit = 3 if jp_mode else max_words_per_chunk

    grouped_indices: List[List[int]] = []
    current_group: List[int] = []
    current_chars = 0

    for idx, tok in enumerate(raw_tokens):
        sep_cost = 0 if (jp_mode or not current_group) else 1
        would_exceed_chars = current_group and (current_chars + sep_cost + len(tok) > char_limit)
        would_exceed_words = len(current_group) >= word_limit
        if would_exceed_chars or would_exceed_words:
            grouped_indices.append(current_group)
            current_group = []
            current_chars = 0

        current_group.append(idx)
        current_chars += (0 if (jp_mode or len(current_group) == 1) else 1) + len(tok)

        if tok.endswith((".", "!", "?", "。", "！", "？")):
            grouped_indices.append(current_group)
            current_group = []
            current_chars = 0

    if current_group:
        grouped_indices.append(current_group)

    # Assign exact contiguous start/end timestamps per token
    cursor = effective_start
    token_times: List[Tuple[float, float]] = []
    for w in weights:
        dur = span * (w / total_weight)
        token_times.append((cursor, cursor + dur))
        cursor += dur

    chunks: List[CaptionChunk] = []
    for c_idx, idxs in enumerate(grouped_indices):
        chunk_tokens = [
            TimedCaptionToken(
                text=raw_tokens[i],
                start=token_times[i][0],
                end=token_times[i][1],
                chunk_index=c_idx,
            )
            for i in idxs
        ]
        chunks.append(
            CaptionChunk(
                tokens=chunk_tokens,
                start=chunk_tokens[0].start,
                end=chunk_tokens[-1].end,
            )
        )
    return chunks


def active_caption_window(
    chunks: Sequence[CaptionChunk],
    t: float,
) -> Optional[Tuple[CaptionChunk, int]]:
    """Return `(active_chunk, active_token_index)` for timestamp `t`, or None."""
    if not chunks:
        return None
    for chunk in chunks:
        if chunk.start <= t <= chunk.end + 0.08:
            best_idx = 0
            for idx, tok in enumerate(chunk.tokens):
                if t >= tok.start:
                    best_idx = idx
            return (chunk, best_idx)
    return None
