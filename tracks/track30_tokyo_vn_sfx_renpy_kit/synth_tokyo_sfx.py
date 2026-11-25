"""Deterministic 48kHz 16-bit PCM Pure-Python Synthesizer for Track 30.

Tokyo Visual Novel & Indie Game Audio + Smartphone Messenger UI Kit
Author: peco (https://pecopeko.itch.io | https://github.com/pecopeko)
License: Royalty-Free Commercial Asset Generator (Zero external samples)

Synthesizes 40 distinct 48,000 Hz 16-bit PCM WAV files across 5 categories
using physical modeling, modal resonance, multi-operator FM, subtractive
biquad filtering, and Schroeder comb/all-pass reverberation.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SAMPLE_RATE = 48000
TWO_PI = 2.0 * math.pi


@dataclass(frozen=True)
class SfxSpec:
    """Metadata and synthesis recipe for a single Tokyo SFX WAV asset."""

    index: int
    folder: str
    filename: str
    title_en: str
    title_jp: str
    free_sample: bool
    peak_target: float
    builder: Callable[[], list[float]]

    @property
    def rel_path(self) -> str:
        return f"{self.folder}/{self.filename}"


# ---------------------------------------------------------------------------
# Core DSP Primitives (48 kHz, pure Python math/random, tiny RAM footprint)
# ---------------------------------------------------------------------------


def zeros(duration_sec: float) -> list[float]:
    """Allocate a zero-initialized mono float buffer."""
    n = max(64, int(round(duration_sec * SAMPLE_RATE)))
    return [0.0] * n


def note_hz(midi_note: float) -> float:
    """Convert MIDI note number (69 = A4 = 440 Hz) to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))


def remove_dc_offset(buf: list[float]) -> list[float]:
    """Apply a steep 1-pole DC blocker (~6 Hz cutoff at 48kHz) + mean removal."""
    n = len(buf)
    if n == 0:
        return buf
    out = [0.0] * n
    r = 0.9992
    prev_x = 0.0
    prev_y = 0.0
    for i, x in enumerate(buf):
        y = x - prev_x + r * prev_y
        out[i] = y
        prev_x = x
        prev_y = y
    mean_val = sum(out) / float(n)
    if abs(mean_val) > 1e-12:
        for i in range(n):
            out[i] -= mean_val
    return out


def biquad_filter(
    buf: list[float],
    mode: str,
    freq_hz: float,
    q: float = 0.707,
    gain_db: float = 0.0,
) -> list[float]:
    """Apply an Audio-EQ-Cookbook RBJ biquad filter at 48 kHz."""
    n = len(buf)
    if n == 0:
        return buf
    f0 = max(20.0, min(SAMPLE_RATE * 0.46, freq_hz))
    q_safe = max(0.12, q)
    w0 = TWO_PI * f0 / SAMPLE_RATE
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / (2.0 * q_safe)

    if mode == "lowpass":
        b0 = (1.0 - cos_w0) * 0.5
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif mode == "highpass":
        b0 = (1.0 + cos_w0) * 0.5
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif mode == "bandpass":
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif mode == "peaking":
        amp = 10.0 ** (gain_db / 40.0)
        b0 = 1.0 + alpha * amp
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * amp
        a0 = 1.0 + alpha / amp
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / amp
    else:
        raise ValueError(f"Unsupported biquad mode: {mode}")

    inv_a0 = 1.0 / a0
    c_b0 = b0 * inv_a0
    c_b1 = b1 * inv_a0
    c_b2 = b2 * inv_a0
    c_a1 = a1 * inv_a0
    c_a2 = a2 * inv_a0

    out = [0.0] * n
    x1 = 0.0
    x2 = 0.0
    y1 = 0.0
    y2 = 0.0
    for i, x0 in enumerate(buf):
        y0 = c_b0 * x0 + c_b1 * x1 + c_b2 * x2 - c_a1 * y1 - c_a2 * y2
        out[i] = y0
        x2 = x1
        x1 = x0
        y2 = y1
        y1 = y0
    return out


def apply_schroeder_reverb(
    buf: list[float],
    room_scale: float = 1.0,
    feedback: float = 0.76,
    damping: float = 0.35,
    wet: float = 0.25,
    slapback_ms: float = 0.0,
    slapback_gain: float = 0.0,
) -> list[float]:
    """Schroeder 4-comb (damped) + 2-allpass reverberator with optional slapback."""
    n = len(buf)
    if n == 0 or wet <= 0.0:
        return list(buf)

    prime_delays = [1433, 1693, 1931, 2179]
    comb_delays = [max(37, int(round(d * room_scale))) for d in prime_delays]
    fb = max(0.05, min(0.93, feedback))
    damp = max(0.02, min(0.85, damping))
    damp_inv = 1.0 - damp

    comb_sum = [0.0] * n
    for delay in comb_delays:
        ring = [0.0] * delay
        idx = 0
        filt_store = 0.0
        for i, x in enumerate(buf):
            delayed = ring[idx]
            filt_store = delayed * damp_inv + filt_store * damp
            ring[idx] = x + filt_store * fb
            comb_sum[i] += delayed
            idx += 1
            if idx == delay:
                idx = 0

    # Two series allpass diffusers
    wet_sig = [v * 0.25 for v in comb_sum]
    for ap_delay_base, ap_g in ((241, 0.5), (83, 0.5)):
        ap_delay = max(17, int(round(ap_delay_base * max(0.6, room_scale))))
        ap_ring = [0.0] * ap_delay
        ap_idx = 0
        for i, x in enumerate(wet_sig):
            buf_out = ap_ring[ap_idx]
            vn = x + buf_out * ap_g
            ap_ring[ap_idx] = vn
            wet_sig[i] = buf_out - vn * ap_g
            ap_idx += 1
            if ap_idx == ap_delay:
                ap_idx = 0

    dry = 1.0 - wet * 0.45
    out = [buf[i] * dry + wet_sig[i] * wet for i in range(n)]

    if slapback_ms > 1.0 and slapback_gain > 0.0:
        sb_samples = int(round(slapback_ms * 0.001 * SAMPLE_RATE))
        for i in range(sb_samples, n):
            out[i] += buf[i - sb_samples] * slapback_gain
    return out


def finalize_pcm16(
    buf: list[float],
    peak_target: float = 0.84,
    fade_in_ms: float = 2.5,
    fade_out_ms: float = 16.0,
) -> bytes:
    """DC-block, cosine-fade boundaries, soft-limit, and pack 16-bit PCM bytes."""
    clean = remove_dc_offset(buf)
    n = len(clean)
    fade_in = min(n // 4, max(24, int(round(fade_in_ms * 0.001 * SAMPLE_RATE))))
    fade_out = min(n // 3, max(48, int(round(fade_out_ms * 0.001 * SAMPLE_RATE))))

    # Raised-cosine boundary fades before normalization
    for i in range(fade_in):
        w = 0.5 * (1.0 - math.cos(math.pi * i / float(fade_in)))
        clean[i] *= w
    for i in range(fade_out):
        w = 0.5 * (1.0 - math.cos(math.pi * i / float(fade_out)))
        clean[n - 1 - i] *= w

    max_abs = max((abs(v) for v in clean), default=0.0)
    if max_abs < 1e-9:
        max_abs = 1.0

    # Normalize into gentle tanh soft-saturator so peaks never hard-clip
    drive = 1.25
    norm_tanh = 1.0 / math.tanh(drive)
    scale = peak_target / max_abs

    shaped_buf = [math.tanh(val * scale * drive) * norm_tanh * peak_target for val in clean]

    # Remove any asymmetric-waveform post-saturation DC shift, then re-window edges
    post_mean = sum(shaped_buf) / float(n)
    if abs(post_mean) > 1e-12:
        for i in range(n):
            shaped_buf[i] -= post_mean
        for i in range(fade_in):
            shaped_buf[i] *= 0.5 * (1.0 - math.cos(math.pi * i / float(fade_in)))
        for i in range(fade_out):
            shaped_buf[n - 1 - i] *= 0.5 * (1.0 - math.cos(math.pi * i / float(fade_out)))

    pcm = bytearray(n * 2)
    for i, shaped in enumerate(shaped_buf):
        sample_int = int(round(shaped * 32000.0))
        if sample_int > 31800:
            sample_int = 31800
        elif sample_int < -31800:
            sample_int = -31800
        struct.pack_into("<h", pcm, i * 2, sample_int)

    # Guarantee strictly zero boundary endpoints (zero pop/click)
    struct.pack_into("<h", pcm, 0, 0)
    struct.pack_into("<h", pcm, (n - 1) * 2, 0)
    return bytes(pcm)


def add_fm_chime_note(
    buf: list[float],
    start_sec: float,
    duration_sec: float,
    freq_hz: float,
    amp: float = 0.5,
    mod_ratio: float = 3.0,
    mod_index: float = 2.1,
    decay_rate: float = 1.65,
    brightness_decay: float = 7.5,
) -> None:
    """Mix a multi-partial Japanese electromechanical/FM chime tone into buf."""
    n_total = len(buf)
    i0 = max(0, int(round(start_sec * SAMPLE_RATE)))
    length = int(round(duration_sec * SAMPLE_RATE))
    i1 = min(n_total, i0 + length)
    if i1 <= i0:
        return

    attack_samples = max(24, int(0.0045 * SAMPLE_RATE))
    rel_samples = max(96, int(0.045 * SAMPLE_RATE))
    dt = 1.0 / SAMPLE_RATE

    w_c1 = TWO_PI * freq_hz
    w_c2 = TWO_PI * (freq_hz * 1.0009)  # Gentle chorus warmth
    w_m1 = TWO_PI * (freq_hz * mod_ratio)
    w_m2 = TWO_PI * (freq_hz * 5.04)  # Inharmonic tonebar strike overtone

    for idx in range(i0, i1):
        k = idx - i0
        t = k * dt
        if k < attack_samples:
            env_a = 0.5 * (1.0 - math.cos(math.pi * k / float(attack_samples)))
        else:
            env_a = 1.0
        rem = i1 - 1 - idx
        if rem < rel_samples:
            env_r = 0.5 * (1.0 - math.cos(math.pi * rem / float(rel_samples)))
        else:
            env_r = 1.0

        env_body = math.exp(-t * decay_rate) * env_a * env_r
        idx_m1 = mod_index * math.exp(-t * brightness_decay)
        idx_m2 = (mod_index * 0.42) * math.exp(-t * 26.0)

        mod = idx_m1 * math.sin(w_m1 * t) + idx_m2 * math.sin(w_m2 * t)
        carrier = 0.62 * math.sin(w_c1 * t + mod) + 0.38 * math.sin(w_c2 * t + mod * 0.7)
        sub_oct = 0.16 * math.sin(0.5 * w_c1 * t) * math.exp(-t * (decay_rate * 0.8))
        buf[idx] += amp * env_body * (carrier + sub_oct)


def add_modal_strike(
    buf: list[float],
    start_sec: float,
    duration_sec: float,
    modes: list[tuple[float, float, float]],
    amp: float = 0.6,
    mallet_noise: float = 0.08,
    mallet_decay: float = 140.0,
    seed: int = 101,
) -> None:
    """Mix a physical modal resonator strike: modes = [(freq_hz, rel_amp, decay_rate)]."""
    n_total = len(buf)
    i0 = max(0, int(round(start_sec * SAMPLE_RATE)))
    i1 = min(n_total, i0 + int(round(duration_sec * SAMPLE_RATE)))
    if i1 <= i0:
        return

    rng = random.Random(seed)
    dt = 1.0 / SAMPLE_RATE
    attack = max(8, int(0.0012 * SAMPLE_RATE))
    rel = max(64, int(0.025 * SAMPLE_RATE))

    # Precompute angular velocities and random tiny initial phases
    compiled = [
        (TWO_PI * f, a, d, rng.uniform(0.0, 0.35))
        for (f, a, d) in modes
        if f < SAMPLE_RATE * 0.47
    ]

    for idx in range(i0, i1):
        k = idx - i0
        t = k * dt
        env_a = (k / float(attack)) if k < attack else 1.0
        rem = i1 - 1 - idx
        env_r = (rem / float(rel)) if rem < rel else 1.0

        total = 0.0
        for w, rel_a, dec, ph in compiled:
            total += rel_a * math.exp(-t * dec) * math.sin(w * t + ph)
        if mallet_noise > 0.0 and t < 0.045:
            total += mallet_noise * (rng.random() * 2.0 - 1.0) * math.exp(-t * mallet_decay)
        buf[idx] += amp * env_a * env_r * total


# ---------------------------------------------------------------------------
# Category 01: School Chimes (4 WAVs)
# ---------------------------------------------------------------------------


def synth_01_school_chime_courtyard() -> list[float]:
    """Japanese high school 4-phrase Westminster chime ('Kin-Kon-Kan-Kon') outdoors."""
    buf = zeros(7.8)
    # Public-domain Westminster 4 phrases in F Major (classic Japanese school key):
    # Phrase 1: F4-A4-G4-C4 | Phrase 2: F4-G4-A4-F4
    # Phrase 3: A4-F4-G4-C4 | Phrase 4: C4-G4-A4-F4
    f4, g4, a4, c4 = note_hz(65), note_hz(67), note_hz(69), note_hz(60)
    phrases = [
        [f4, a4, g4, c4],
        [f4, g4, a4, f4],
        [a4, f4, g4, c4],
        [c4, g4, a4, f4],
    ]
    t = 0.12
    step = 0.34
    for p_idx, notes in enumerate(phrases):
        for n_idx, freq in enumerate(notes):
            is_hold = n_idx == 3
            dur = 1.15 if is_hold else 0.72
            add_fm_chime_note(
                buf,
                start_sec=t,
                duration_sec=dur,
                freq_hz=freq,
                amp=0.45,
                mod_ratio=3.0,
                mod_index=2.25,
                decay_rate=1.45 if is_hold else 2.05,
                brightness_decay=6.8,
            )
            # Subtle harmonic fifth shimmer on held notes
            if is_hold:
                add_fm_chime_note(
                    buf,
                    start_sec=t,
                    duration_sec=dur * 1.1,
                    freq_hz=freq * 2.0,
                    amp=0.11,
                    mod_ratio=2.0,
                    mod_index=1.1,
                    decay_rate=2.2,
                )
            t += step * (1.85 if is_hold else 1.0)
        if p_idx == 1:
            t += 0.08

    # Outdoor courtyard ambience: concrete building slapback + open air reverb
    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.55,
        feedback=0.81,
        damping=0.42,
        wet=0.36,
        slapback_ms=185.0,
        slapback_gain=0.19,
    )
    return buf


def synth_02_school_chime_classroom_speaker() -> list[float]:
    """Indoor classroom wall PA speaker Westminster chime with relay click."""
    buf = zeros(4.9)
    rng = random.Random(3002)
    # Relay click ON at t=0.06s + subtle PA transformer hum + tape hiss
    for i in range(int(0.05 * SAMPLE_RATE), int(4.45 * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        hum = 0.004 * math.sin(TWO_PI * 100.0 * t) + 0.002 * math.sin(TWO_PI * 200.0 * t)
        hiss = 0.0025 * (rng.random() * 2.0 - 1.0)
        buf[i] += hum + hiss

    add_modal_strike(
        buf, 0.05, 0.04, [(1450.0, 0.7, 180.0), (2900.0, 0.5, 240.0)], amp=0.16, seed=12
    )

    f4, g4, a4, c4 = note_hz(65), note_hz(67), note_hz(69), note_hz(60)
    seq = [(f4, 0.42), (a4, 0.42), (g4, 0.42), (c4, 0.82), (f4, 0.42), (g4, 0.42), (a4, 0.42), (f4, 0.95)]
    t_cursor = 0.22
    for freq, step_dur in seq:
        add_fm_chime_note(
            buf,
            start_sec=t_cursor,
            duration_sec=step_dur * 1.45,
            freq_hz=freq,
            amp=0.52,
            mod_ratio=3.0,
            mod_index=2.5,
            decay_rate=2.1,
        )
        t_cursor += step_dur

    # Relay click OFF at t=4.44s
    add_modal_strike(
        buf, 4.44, 0.04, [(1320.0, 0.7, 190.0), (2650.0, 0.4, 260.0)], amp=0.14, seed=19
    )

    # Classroom speaker cabinet bandpass (420 Hz - 3300 Hz) + tight room reflection
    buf = biquad_filter(buf, "highpass", 390.0, q=0.85)
    buf = biquad_filter(buf, "lowpass", 3250.0, q=0.95)
    buf = biquad_filter(buf, "peaking", 1150.0, q=1.6, gain_db=3.5)
    buf = apply_schroeder_reverb(buf, room_scale=0.58, feedback=0.62, damping=0.50, wet=0.18)
    return buf


def synth_03_homeroom_two_tone_chime() -> list[float]:
    """2-tone homeroom warning chime ('Pin-Pon': A4 -> F4 tubular reed bell)."""
    buf = zeros(2.65)
    add_fm_chime_note(
        buf, 0.08, 1.35, note_hz(69), amp=0.56, mod_ratio=2.0, mod_index=1.85, decay_rate=1.8
    )
    add_fm_chime_note(
        buf, 0.64, 1.85, note_hz(65), amp=0.58, mod_ratio=2.0, mod_index=1.75, decay_rate=1.45
    )
    buf = apply_schroeder_reverb(buf, room_scale=0.82, feedback=0.72, damping=0.40, wet=0.22)
    return buf


def synth_04_pa_broadcast_four_note_prefix() -> list[float]:
    """4-note ascending PA announcement prefix chime (C4 -> E4 -> G4 -> C5)."""
    buf = zeros(2.95)
    add_modal_strike(buf, 0.03, 0.03, [(1600.0, 0.6, 220.0)], amp=0.10, seed=41)
    notes = [(60, 0.34), (64, 0.34), (67, 0.34), (72, 1.55)]
    t = 0.14
    for midi_n, dur in notes:
        add_fm_chime_note(
            buf,
            start_sec=t,
            duration_sec=max(0.85, dur),
            freq_hz=note_hz(midi_n),
            amp=0.50,
            mod_ratio=4.0,
            mod_index=1.55,
            decay_rate=2.0 if dur < 0.5 else 1.35,
            brightness_decay=9.0,
        )
        t += 0.33
    buf = biquad_filter(buf, "highpass", 240.0, q=0.75)
    buf = biquad_filter(buf, "lowpass", 5600.0, q=0.8)
    buf = apply_schroeder_reverb(buf, room_scale=0.75, feedback=0.68, damping=0.45, wet=0.20)
    return buf


# ---------------------------------------------------------------------------
# Category 02: Konbini & Shops (5 WAVs — 100% Original Copyright-Clear)
# ---------------------------------------------------------------------------


def synth_05_konbini_door_melody_sunny_a() -> list[float]:
    """Original cheerful Tokyo convenience-store door melody #1 in G Major."""
    buf = zeros(3.15)
    rng = random.Random(3005)
    # Subtle automatic glass sliding door motor glide underneath first 0.9s
    door_noise = zeros(3.15)
    for i in range(int(0.04 * SAMPLE_RATE), int(0.95 * SAMPLE_RATE)):
        t = (i / SAMPLE_RATE) - 0.04
        env = math.sin(math.pi * min(1.0, t / 0.91))
        door_noise[i] = 0.035 * env * (rng.random() * 2.0 - 1.0)
    door_noise = biquad_filter(door_noise, "bandpass", 620.0, q=2.2)
    for i in range(len(buf)):
        buf[i] += door_noise[i]

    # Original bright G-major pentatonic welcome motif (distinct from any real chain):
    # D5 - B4 - G4 - A4 - B4 - D5 - G5 (upbeat bounce!)
    melody = [
        (74, 0.23),
        (71, 0.23),
        (67, 0.23),
        (69, 0.23),
        (71, 0.23),
        (74, 0.23),
        (79, 1.25),
    ]
    harm = [
        (67, 0.23),
        (62, 0.23),
        (59, 0.23),
        (60, 0.23),
        (62, 0.23),
        (66, 0.23),
        (71, 1.25),
    ]
    t = 0.10
    for (m_n, dur), (h_n, _) in zip(melody, harm):
        add_fm_chime_note(
            buf,
            start_sec=t,
            duration_sec=max(0.55, dur * 1.4),
            freq_hz=note_hz(m_n),
            amp=0.46,
            mod_ratio=2.0,
            mod_index=2.3,
            decay_rate=3.4 if dur < 0.4 else 1.8,
            brightness_decay=11.0,
        )
        add_fm_chime_note(
            buf,
            start_sec=t,
            duration_sec=max(0.45, dur * 1.3),
            freq_hz=note_hz(h_n),
            amp=0.22,
            mod_ratio=2.0,
            mod_index=1.2,
            decay_rate=3.8 if dur < 0.4 else 2.0,
        )
        t += 0.23

    buf = apply_schroeder_reverb(buf, room_scale=0.62, feedback=0.64, damping=0.42, wet=0.17)
    return buf


def synth_06_konbini_door_melody_breeze_b() -> list[float]:
    """Original late-night Tokyo konbini / bakery electronic door chime #2 in Eb Major."""
    buf = zeros(2.95)
    # Original gentle 5-note Eb major motif: Bb4 -> G4 -> C5 -> Bb4 -> Eb5
    notes = [
        (70, 63, 0.28),
        (67, 58, 0.28),
        (72, 63, 0.28),
        (70, 62, 0.28),
        (75, 67, 1.35),
    ]
    t = 0.08
    for lead, bass, dur in notes:
        add_fm_chime_note(
            buf,
            start_sec=t,
            duration_sec=max(0.65, dur * 1.3),
            freq_hz=note_hz(lead),
            amp=0.46,
            mod_ratio=3.0,
            mod_index=1.65,
            decay_rate=2.6 if dur < 0.4 else 1.55,
            brightness_decay=9.5,
        )
        add_fm_chime_note(
            buf,
            start_sec=t,
            duration_sec=max(0.60, dur * 1.25),
            freq_hz=note_hz(bass),
            amp=0.24,
            mod_ratio=1.0,
            mod_index=0.9,
            decay_rate=2.8 if dur < 0.4 else 1.65,
        )
        t += 0.28
    buf = apply_schroeder_reverb(buf, room_scale=0.68, feedback=0.66, damping=0.44, wet=0.18)
    return buf


def synth_07_izakaya_sliding_door_chirin() -> list[float]:
    """Wooden lattice sliding door ('Garagara') + brass shop bell ('Chirin-chirin!')."""
    buf = zeros(2.45)
    rng = random.Random(3007)

    # 1. Wooden door rolling across wooden rail groove (0.05s - 0.92s)
    wood_raw = zeros(2.45)
    for i in range(int(0.05 * SAMPLE_RATE), int(0.92 * SAMPLE_RATE)):
        t = (i / SAMPLE_RATE) - 0.05
        # Periodic wood-grain slat rattle (~26 Hz modulated)
        rattle = 0.55 + 0.45 * math.sin(TWO_PI * 27.0 * t + 1.8 * math.sin(TWO_PI * 6.5 * t))
        env = math.sin(math.pi * min(1.0, t / 0.87))
        wood_raw[i] = env * rattle * (rng.random() * 2.0 - 1.0) * 0.42
    wood_low = biquad_filter(wood_raw, "bandpass", 245.0, q=2.8)
    wood_mid = biquad_filter(wood_raw, "bandpass", 590.0, q=3.2)
    for i in range(len(buf)):
        buf[i] += wood_low[i] * 0.85 + wood_mid[i] * 0.55

    # Wooden frame end-stop knock at t=0.90s
    add_modal_strike(
        buf,
        0.90,
        0.28,
        [(138.0, 0.9, 32.0), (285.0, 0.55, 45.0), (540.0, 0.3, 68.0)],
        amp=0.44,
        mallet_noise=0.14,
        seed=71,
    )

    # 2. Brass shop-door 'Chirin-chirin!' triple bell ring triggered as door opens
    brass_modes = [
        (2680.0, 0.85, 5.2),
        (4135.0, 0.65, 6.8),
        (5890.0, 0.48, 8.5),
        (7640.0, 0.32, 11.0),
        (9420.0, 0.18, 14.5),
    ]
    for strike_t, strike_amp, s_seed in ((0.22, 0.48, 72), (0.37, 0.56, 73), (0.88, 0.34, 74)):
        add_modal_strike(
            buf,
            strike_t,
            1.45,
            brass_modes,
            amp=strike_amp,
            mallet_noise=0.05,
            mallet_decay=220.0,
            seed=s_seed,
        )

    buf = apply_schroeder_reverb(buf, room_scale=0.65, feedback=0.65, damping=0.38, wet=0.18)
    return buf


def synth_08_ic_card_transit_pass_pipi() -> list[float]:
    """Tokyo transit ticket gate IC card 'Pi-Pi!' chirp (2000 Hz -> 2480 Hz)."""
    buf = zeros(0.62)

    def add_ic_chirp(t0: float, dur: float, f_hz: float, level: float) -> None:
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(buf), i0 + int(round(dur * SAMPLE_RATE)))
        att = max(12, int(0.0025 * SAMPLE_RATE))
        rel = max(24, int(0.006 * SAMPLE_RATE))
        for idx in range(i0, i1):
            k = idx - i0
            t = k / SAMPLE_RATE
            ea = (k / float(att)) if k < att else 1.0
            rem = i1 - 1 - idx
            er = (rem / float(rel)) if rem < rel else 1.0
            # Piezo transducer fundamental + crisp 3rd & 5th harmonic sheen
            sig = (
                0.80 * math.sin(TWO_PI * f_hz * t)
                + 0.16 * math.sin(TWO_PI * (f_hz * 3.0) * t)
                + 0.04 * math.sin(TWO_PI * (f_hz * 5.0) * t)
            )
            buf[idx] += level * ea * er * sig

    # Tiny card plastic tap at t=0.02s
    add_modal_strike(
        buf, 0.02, 0.035, [(920.0, 0.6, 160.0), (2350.0, 0.5, 210.0)], amp=0.14, seed=81
    )
    add_ic_chirp(0.055, 0.062, 2000.0, 0.68)
    add_ic_chirp(0.142, 0.088, 2480.0, 0.76)

    buf = apply_schroeder_reverb(buf, room_scale=0.52, feedback=0.52, damping=0.45, wet=0.10)
    return buf


def synth_09_ic_card_error_triple_beep() -> list[float]:
    """Transit IC gate insufficient-balance urgent triple buzzer + flap clack."""
    buf = zeros(0.98)
    for pulse_idx, t0 in enumerate((0.05, 0.21, 0.37)):
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(buf), i0 + int(round(0.115 * SAMPLE_RATE)))
        att = int(0.003 * SAMPLE_RATE)
        rel = int(0.008 * SAMPLE_RATE)
        for idx in range(i0, i1):
            k = idx - i0
            t = k / SAMPLE_RATE
            ea = (k / float(att)) if k < att else 1.0
            rem = i1 - 1 - idx
            er = (rem / float(rel)) if rem < rel else 1.0
            # Urgent dual-frequency warning buzzer (960 Hz + 1420 Hz + odd harmonics)
            sig = (
                0.52 * math.sin(TWO_PI * 960.0 * t)
                + 0.36 * math.sin(TWO_PI * 1420.0 * t)
                + 0.14 * math.sin(TWO_PI * 2880.0 * t)
            )
            buf[idx] += 0.66 * ea * er * sig
        if pulse_idx == 1:
            # Gate flap solenoid snap shut!
            add_modal_strike(
                buf,
                t0 + 0.03,
                0.18,
                [(210.0, 0.9, 45.0), (580.0, 0.6, 65.0), (1480.0, 0.4, 95.0)],
                amp=0.38,
                mallet_noise=0.16,
                seed=92,
            )

    buf = apply_schroeder_reverb(buf, room_scale=0.60, feedback=0.58, damping=0.45, wet=0.14)
    return buf


# ---------------------------------------------------------------------------
# Category 03: Trains & Crossings (7 WAVs — 100% Original Copyright-Clear)
# ---------------------------------------------------------------------------


def synth_10_fumikiri_railroad_crossing() -> list[float]:
    """Fumikiri ('Kan-Kan-Kan') dual detuned 700Hz + 748Hz inharmonic modal bells."""
    buf = zeros(3.85)
    # Real Japanese electronic/electromechanical fumikiri mixes two slightly
    # detuned bell units (~700 Hz & ~748 Hz) creating unmistakable metallic beating.
    bell_a_modes = [
        (700.0, 1.00, 5.4),
        (1498.0, 0.56, 8.2),
        (2387.0, 0.38, 11.5),
        (3410.0, 0.24, 15.0),
        (4620.0, 0.14, 21.0),
    ]
    bell_b_modes = [
        (748.0, 0.94, 5.7),
        (1602.0, 0.52, 8.6),
        (2550.0, 0.35, 12.0),
        (3642.0, 0.22, 16.0),
        (4910.0, 0.12, 22.0),
    ]
    period = 0.445  # ~135 BPM iconic crossing cadence
    for k in range(8):
        t_strike = 0.06 + k * period
        add_modal_strike(
            buf,
            t_strike,
            0.85,
            bell_a_modes,
            amp=0.42,
            mallet_noise=0.07,
            mallet_decay=200.0,
            seed=1000 + k,
        )
        # Second pole across the tracks strikes ~18ms offset!
        add_modal_strike(
            buf,
            t_strike + 0.018,
            0.85,
            bell_b_modes,
            amp=0.39,
            mallet_noise=0.06,
            mallet_decay=210.0,
            seed=2000 + k,
        )

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.10,
        feedback=0.68,
        damping=0.44,
        wet=0.20,
        slapback_ms=135.0,
        slapback_gain=0.12,
    )
    return buf


def synth_11_ekimelo_commuter_platform_sunrise() -> list[float]:
    """Original copyright-clear Tokyo commuter platform departure Eki-Melo #1 (C Maj)."""
    buf = zeros(5.25)
    # Original uplifting morning commuter progression:
    # Bar 1: Cmaj7 arpeggio -> Fmaj7 | Bar 2: Dm9 -> G13 -> Cadd9 resolve
    events = [
        # (start_sec, midi_note, dur_sec, amp)
        (0.10, 60, 0.90, 0.28),
        (0.10, 76, 0.42, 0.42),
        (0.32, 79, 0.42, 0.40),
        (0.54, 83, 0.55, 0.44),
        (0.98, 65, 0.90, 0.28),
        (0.98, 81, 0.42, 0.44),
        (1.20, 77, 0.42, 0.38),
        (1.42, 72, 0.55, 0.40),
        (1.86, 62, 0.85, 0.28),
        (1.86, 74, 0.38, 0.42),
        (2.08, 77, 0.38, 0.42),
        (2.30, 81, 0.45, 0.45),
        (2.68, 67, 0.85, 0.30),
        (2.68, 79, 0.38, 0.44),
        (2.90, 74, 0.38, 0.38),
        (3.12, 71, 0.45, 0.40),
        # Final shimmering Cadd9 chord
        (3.52, 60, 1.55, 0.30),
        (3.55, 67, 1.52, 0.26),
        (3.58, 74, 1.50, 0.30),
        (3.61, 76, 1.48, 0.34),
        (3.64, 84, 1.55, 0.46),
    ]
    for t0, midi_n, dur, amp in events:
        add_fm_chime_note(
            buf,
            start_sec=t0,
            duration_sec=dur * 1.25,
            freq_hz=note_hz(midi_n),
            amp=amp,
            mod_ratio=2.0,
            mod_index=1.85,
            decay_rate=2.2 if dur < 1.0 else 1.25,
            brightness_decay=8.5,
        )

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.35,
        feedback=0.78,
        damping=0.38,
        wet=0.32,
        slapback_ms=145.0,
        slapback_gain=0.14,
    )
    return buf


def synth_12_ekimelo_twilight_express_chime() -> list[float]:
    """Original copyright-clear Tokyo rapid-express departure Eki-Melo #2 (Eb Maj)."""
    buf = zeros(5.05)
    # Original nostalgic twilight progression: Abmaj7 -> Gm7 -> Fm9 -> Bb9 -> Ebmaj9
    events = [
        (0.10, 56, 0.95, 0.28),
        (0.10, 75, 0.38, 0.42),
        (0.34, 79, 0.38, 0.40),
        (0.58, 80, 0.50, 0.44),
        (1.02, 55, 0.95, 0.28),
        (1.02, 74, 0.38, 0.42),
        (1.26, 77, 0.38, 0.38),
        (1.50, 79, 0.50, 0.44),
        (1.94, 53, 0.85, 0.28),
        (1.94, 72, 0.36, 0.42),
        (2.18, 75, 0.36, 0.40),
        (2.42, 70, 0.85, 0.30),
        (2.42, 77, 0.40, 0.42),
        (2.68, 74, 0.45, 0.40),
        # Final Ebmaj9 chord bloom
        (3.16, 51, 1.70, 0.30),
        (3.20, 63, 1.66, 0.26),
        (3.24, 70, 1.62, 0.28),
        (3.28, 74, 1.60, 0.34),
        (3.32, 79, 1.65, 0.46),
    ]
    for t0, midi_n, dur, amp in events:
        add_fm_chime_note(
            buf,
            start_sec=t0,
            duration_sec=dur * 1.25,
            freq_hz=note_hz(midi_n),
            amp=amp,
            mod_ratio=3.0,
            mod_index=1.45,
            decay_rate=2.1 if dur < 1.0 else 1.2,
            brightness_decay=9.0,
        )

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.40,
        feedback=0.79,
        damping=0.40,
        wet=0.33,
        slapback_ms=160.0,
        slapback_gain=0.15,
    )
    return buf


def synth_13_commuter_door_close_and_hiss() -> list[float]:
    """Commuter door-closing warning chime + pneumatic hiss + rubber seal thud."""
    buf = zeros(3.45)
    rng = random.Random(3013)

    # 3-pair 'Pon-Pon' door warning chimes
    for k in range(3):
        t0 = 0.08 + k * 0.56
        add_fm_chime_note(
            buf, t0, 0.28, 659.25, amp=0.46, mod_ratio=2.0, mod_index=1.4, decay_rate=5.5
        )
        add_fm_chime_note(
            buf, t0 + 0.22, 0.32, 523.25, amp=0.48, mod_ratio=2.0, mod_index=1.3, decay_rate=4.8
        )

    # Pneumatic air-cylinder hiss + sliding track glide (1.68s - 2.78s)
    hiss_raw = zeros(3.45)
    for i in range(int(1.68 * SAMPLE_RATE), int(2.80 * SAMPLE_RATE)):
        t = (i / SAMPLE_RATE) - 1.68
        burst = math.exp(-t * 3.8) if t < 0.25 else 0.38 * math.exp(-(t - 0.25) * 2.5)
        hiss_raw[i] = burst * (rng.random() * 2.0 - 1.0) * 0.65
    hiss_bp = biquad_filter(hiss_raw, "bandpass", 3100.0, q=1.5)
    glide_bp = biquad_filter(hiss_raw, "bandpass", 380.0, q=2.0)
    for i in range(len(buf)):
        buf[i] += hiss_bp[i] * 0.65 + glide_bp[i] * 0.45

    # Twin rubber door seal meeting 'Don-gacha!' at t=2.76s
    add_modal_strike(
        buf,
        2.76,
        0.48,
        [(82.0, 1.0, 18.0), (168.0, 0.75, 26.0), (410.0, 0.35, 48.0), (1120.0, 0.22, 95.0)],
        amp=0.62,
        mallet_noise=0.18,
        mallet_decay=120.0,
        seed=131,
    )
    add_modal_strike(
        buf, 2.86, 0.25, [(680.0, 0.5, 70.0), (1540.0, 0.4, 110.0)], amp=0.28, seed=132
    )

    buf = apply_schroeder_reverb(buf, room_scale=0.85, feedback=0.66, damping=0.48, wet=0.19)
    return buf


def synth_14_shinkansen_cabin_chime_original() -> list[float]:
    """Original copyright-clear bullet-train onboard announcement cabin chime."""
    buf = zeros(4.35)
    # Original refined 6-note D-major pentatonic/Lydian cabin chime:
    # D4 -> A4 -> B4 -> F#5 -> E5 -> A5 (warm vibraphone/celesta cabin timbre)
    seq = [
        (0.12, 62, 0.55, 0.40),
        (0.38, 69, 0.55, 0.42),
        (0.64, 71, 0.55, 0.44),
        (0.90, 78, 0.65, 0.48),
        (1.24, 76, 0.60, 0.44),
        (1.58, 81, 2.35, 0.52),
    ]
    for t0, midi_n, dur, amp in seq:
        add_fm_chime_note(
            buf,
            start_sec=t0,
            duration_sec=dur * 1.15,
            freq_hz=note_hz(midi_n),
            amp=amp,
            mod_ratio=4.0,
            mod_index=1.25,
            decay_rate=2.4 if dur < 1.0 else 1.15,
            brightness_decay=12.0,
        )
    # Warm D-major cushion chord underneath final note
    for chord_n in (62, 69, 74):
        add_fm_chime_note(
            buf,
            start_sec=1.58,
            duration_sec=2.35,
            freq_hz=note_hz(chord_n),
            amp=0.18,
            mod_ratio=2.0,
            mod_index=0.7,
            decay_rate=1.35,
        )

    buf = apply_schroeder_reverb(buf, room_scale=0.72, feedback=0.64, damping=0.52, wet=0.18)
    return buf


def synth_15_crosswalk_piyo_piyo_bird() -> list[float]:
    """Japanese crosswalk acoustic bird signal 'Piyo-Piyo' (downward FM chirp)."""
    buf = zeros(3.25)

    def add_piyo(t0: float, dur: float, f_start: float, f_end: float, level: float) -> None:
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(buf), i0 + int(round(dur * SAMPLE_RATE)))
        n_len = max(1, i1 - i0)
        phase = 0.0
        for k in range(n_len):
            u = k / float(n_len)
            # Concave pitch drop characteristic of Japanese acoustic traffic chirp
            freq = f_end + (f_start - f_end) * ((1.0 - u) ** 1.65)
            phase += TWO_PI * freq / SAMPLE_RATE
            env = math.sin(math.pi * u) ** 0.65
            sig = 0.84 * math.sin(phase) + 0.16 * math.sin(2.0 * phase)
            buf[i0 + k] += level * env * sig

    # Classic 'Piyo... Piyo-piyo!' cadence x 2
    for base_t in (0.12, 1.62):
        add_piyo(base_t, 0.135, 2820.0, 1460.0, 0.66)
        add_piyo(base_t + 0.42, 0.115, 2880.0, 1520.0, 0.64)
        add_piyo(base_t + 0.59, 0.145, 2760.0, 1420.0, 0.68)

    buf = biquad_filter(buf, "bandpass", 2100.0, q=0.9)
    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.20,
        feedback=0.66,
        damping=0.45,
        wet=0.20,
        slapback_ms=118.0,
        slapback_gain=0.14,
    )
    return buf


def synth_16_crosswalk_kakkou_cuckoo() -> list[float]:
    """Japanese crosswalk cuckoo signal 'Kakkou' (F5 -> Db5 hollow flute call)."""
    buf = zeros(3.40)

    def add_flute_tone(t0: float, dur: float, f_hz: float, level: float) -> None:
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(buf), i0 + int(round(dur * SAMPLE_RATE)))
        att = max(24, int(0.014 * SAMPLE_RATE))
        rel = max(48, int(0.035 * SAMPLE_RATE))
        for idx in range(i0, i1):
            k = idx - i0
            t = k / SAMPLE_RATE
            ea = 0.5 * (1.0 - math.cos(math.pi * k / float(att))) if k < att else 1.0
            rem = i1 - 1 - idx
            er = 0.5 * (1.0 - math.cos(math.pi * rem / float(rel))) if rem < rel else 1.0
            # Hollow ocarina/cuckoo odd-harmonic timbre + slight initial breath chiff
            chiff = 0.08 * math.sin(TWO_PI * (f_hz * 4.03) * t) * math.exp(-t * 48.0)
            sig = (
                0.86 * math.sin(TWO_PI * f_hz * t)
                + 0.11 * math.sin(TWO_PI * (f_hz * 3.0) * t)
                + chiff
            )
            buf[idx] += level * ea * er * math.exp(-t * 1.8) * sig

    # Classic 'Kaa-kou... Kaa-kou...' (F5 698.46 Hz -> Db5 554.37 Hz)
    for base_t in (0.14, 1.72):
        add_flute_tone(base_t, 0.165, 698.46, 0.66)
        add_flute_tone(base_t + 0.255, 0.44, 554.37, 0.70)

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.22,
        feedback=0.68,
        damping=0.44,
        wet=0.22,
        slapback_ms=128.0,
        slapback_gain=0.14,
    )
    return buf


# ---------------------------------------------------------------------------
# Category 04: Shrine & Seasons (8 WAVs)
# ---------------------------------------------------------------------------


def synth_17_edo_furin_glass_wind_chime_a() -> list[float]:
    """Edo Furin hand-blown glass wind chime #1 (high-Q crystalline summer breeze)."""
    buf = zeros(3.25)
    rng = random.Random(3017)

    # Gentle summer breeze rustle
    breeze = zeros(3.25)
    for i in range(len(breeze)):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * min(1.0, t / 3.1)) ** 1.4
        breeze[i] = 0.018 * env * (rng.random() * 2.0 - 1.0)
    breeze = biquad_filter(breeze, "bandpass", 1450.0, q=1.2)
    for i in range(len(buf)):
        buf[i] += breeze[i]

    # High-Q hand-blown glass bowl eigenmodes (with close doublet beating!)
    glass_modes = [
        (3124.0, 1.00, 2.3),
        (3129.5, 0.72, 2.5),
        (5485.0, 0.58, 3.8),
        (7910.0, 0.36, 5.4),
        (10680.0, 0.22, 7.8),
    ]
    for t0, amp, s_seed in ((0.18, 0.52, 171), (0.41, 0.34, 172), (1.16, 0.62, 173), (1.33, 0.28, 174)):
        add_modal_strike(
            buf,
            t0,
            1.85,
            glass_modes,
            amp=amp,
            mallet_noise=0.03,
            mallet_decay=320.0,
            seed=s_seed,
        )

    buf = apply_schroeder_reverb(buf, room_scale=1.05, feedback=0.74, damping=0.28, wet=0.26)
    return buf


def synth_18_edo_furin_glass_wind_chime_b() -> list[float]:
    """Edo Furin glass wind chime #2 (deeper artisan glass bowl, double shimmer)."""
    buf = zeros(3.40)
    glass_modes_b = [
        (2538.0, 1.00, 2.0),
        (2542.2, 0.78, 2.2),
        (4492.0, 0.62, 3.4),
        (6818.0, 0.40, 4.9),
        (9240.0, 0.24, 6.8),
    ]
    for t0, amp, s_seed in ((0.14, 0.58, 181), (0.86, 0.44, 182), (1.04, 0.60, 183)):
        add_modal_strike(
            buf,
            t0,
            2.15,
            glass_modes_b,
            amp=amp,
            mallet_noise=0.03,
            mallet_decay=300.0,
            seed=s_seed,
        )

    buf = apply_schroeder_reverb(buf, room_scale=1.12, feedback=0.76, damping=0.30, wet=0.28)
    return buf


def synth_19_shishi_odoshi_bamboo_fountain() -> list[float]:
    """Garden Shishi-Odoshi: water trickle + hollow bamboo rock knock ('Kakon!')."""
    buf = zeros(3.60)
    rng = random.Random(3019)

    # 1. Delicate bamboo spout water droplets (0.08s - 1.35s)
    for d_idx in range(11):
        t_drop = 0.08 + d_idx * 0.11 + rng.uniform(-0.02, 0.02)
        f_drop = rng.uniform(980.0, 1950.0)
        add_modal_strike(
            buf,
            t_drop,
            0.075,
            [(f_drop, 0.8, 55.0), (f_drop * 1.48, 0.4, 80.0)],
            amp=0.09,
            mallet_noise=0.02,
            seed=190 + d_idx,
        )

    # Water pour splash as bamboo tips over (1.28s - 1.65s)
    splash = zeros(3.60)
    for i in range(int(1.28 * SAMPLE_RATE), int(1.72 * SAMPLE_RATE)):
        t = (i / SAMPLE_RATE) - 1.28
        env = math.sin(math.pi * min(1.0, t / 0.44)) * math.exp(-t * 3.2)
        splash[i] = 0.22 * env * (rng.random() * 2.0 - 1.0)
    splash = biquad_filter(splash, "bandpass", 1850.0, q=1.1)
    for i in range(len(buf)):
        buf[i] += splash[i]

    # 2. Iconic hollow bamboo tube striking wet garden stone: 'KA-KON!'
    bamboo_modes = [
        (368.0, 1.00, 16.5),
        (746.0, 0.78, 22.0),
        (1198.0, 0.52, 30.0),
        (1845.0, 0.34, 42.0),
        (2690.0, 0.18, 60.0),
    ]
    add_modal_strike(
        buf,
        1.62,
        0.95,
        bamboo_modes,
        amp=0.78,
        mallet_noise=0.18,
        mallet_decay=160.0,
        seed=198,
    )
    # Secondary rebound tap 210ms later
    add_modal_strike(
        buf,
        1.83,
        0.65,
        [(374.0, 0.85, 20.0), (758.0, 0.60, 28.0), (1210.0, 0.38, 38.0)],
        amp=0.34,
        mallet_noise=0.10,
        mallet_decay=180.0,
        seed=199,
    )

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.30,
        feedback=0.76,
        damping=0.38,
        wet=0.28,
        slapback_ms=155.0,
        slapback_gain=0.13,
    )
    return buf


def synth_20_shrine_suzu_sacred_bell_shake() -> list[float]:
    """Shinto shrine Suzu sacred bell cluster shake (hemp rope swish + brass jingle)."""
    buf = zeros(3.25)
    rng = random.Random(3020)

    # Heavy braided hemp rope swish on two shakes
    rope = zeros(3.25)
    for shake_t in (0.08, 0.82):
        i0 = int(shake_t * SAMPLE_RATE)
        i1 = min(len(rope), i0 + int(0.32 * SAMPLE_RATE))
        for i in range(i0, i1):
            u = (i - i0) / float(i1 - i0)
            rope[i] += 0.16 * math.sin(math.pi * u) * (rng.random() * 2.0 - 1.0)
    rope = biquad_filter(rope, "bandpass", 480.0, q=1.5)
    for i in range(len(buf)):
        buf[i] += rope[i]

    # Cascading cluster of brass pellet bells inside hollow bronze sphere
    for shake_idx, base_t in enumerate((0.14, 0.88)):
        n_hits = 11 if shake_idx == 0 else 13
        for h in range(n_hits):
            jitter_t = base_t + h * 0.024 + rng.uniform(0.0, 0.018)
            root_f = rng.uniform(1720.0, 2480.0)
            modes = [
                (root_f, 0.85, 7.5),
                (root_f * 1.72, 0.65, 9.5),
                (root_f * 2.63, 0.45, 12.0),
                (root_f * 3.81, 0.28, 16.0),
            ]
            hit_amp = 0.24 * (1.0 - 0.045 * h)
            add_modal_strike(
                buf,
                jitter_t,
                1.25,
                modes,
                amp=hit_amp,
                mallet_noise=0.06,
                mallet_decay=240.0,
                seed=2000 + shake_idx * 50 + h,
            )

    buf = apply_schroeder_reverb(buf, room_scale=1.28, feedback=0.77, damping=0.34, wet=0.28)
    return buf


def synth_21_shrine_kashiwade_two_claps() -> list[float]:
    """Shinto shrine Kashiwade: two cupped-palm ritual claps in wooden sanctuary."""
    buf = zeros(2.65)
    rng = random.Random(3021)

    for clap_idx, t_clap in enumerate((0.18, 1.06)):
        clap_buf = zeros(2.65)
        # Real handclap = 3 micro-staggered skin impacts over ~11ms + palm Helmholtz air pop
        for sub in range(4):
            sub_t = t_clap + sub * 0.0031 + rng.uniform(0.0, 0.0012)
            i0 = int(round(sub_t * SAMPLE_RATE))
            i1 = min(len(clap_buf), i0 + int(0.032 * SAMPLE_RATE))
            for idx in range(i0, i1):
                dt = (idx - i0) / SAMPLE_RATE
                clap_buf[idx] += (rng.random() * 2.0 - 1.0) * math.exp(-dt * 195.0) * 0.55

        # Cupped palm cavity resonance (~980 Hz) + bright skin snap (~2350 Hz)
        palm_body = biquad_filter(clap_buf, "bandpass", 980.0 + clap_idx * 35.0, q=2.6)
        skin_snap = biquad_filter(clap_buf, "bandpass", 2420.0, q=1.7)
        for i in range(len(buf)):
            buf[i] += palm_body[i] * 1.15 + skin_snap[i] * 0.75

    buf = apply_schroeder_reverb(
        buf,
        room_scale=1.48,
        feedback=0.80,
        damping=0.42,
        wet=0.35,
        slapback_ms=112.0,
        slapback_gain=0.22,
    )
    return buf


def synth_22_higurashi_twilight_cicada() -> list[float]:
    """Evening Higurashi twilight cicada ('Kana-kana-kana-kana-kana...')."""
    buf = zeros(4.25)
    # Higurashi call is an extraordinarily musical, bell-like dual-formant (~3950 & ~4720 Hz)
    # phrase of accelerating pulses rising gently in pitch and fading into twilight.
    pulses: list[tuple[float, float, float]] = []
    t = 0.14
    for k in range(15):
        u = k / 14.0
        # Syllables accelerate from 0.28s spacing down to 0.15s
        gap = 0.27 - 0.115 * (u**0.75)
        pitch_mult = 1.0 + 0.045 * math.sin(math.pi * u) - 0.02 * (u**2)
        env_gain = math.sin(math.pi * min(1.0, (k + 1.2) / 15.8)) ** 0.85
        pulses.append((t, pitch_mult, env_gain))
        t += gap

    for idx_p, (t0, p_mult, gain) in enumerate(pulses):
        # Each 'Ka-na' syllable has a crisp 'Ka' onset and singing 'na' metallic ring
        dur = 0.175
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(buf), i0 + int(round(dur * SAMPLE_RATE)))
        f1 = 3940.0 * p_mult
        f2 = 4710.0 * p_mult
        f_tymbal = 235.0 * p_mult
        for idx in range(i0, i1):
            dt = (idx - i0) / SAMPLE_RATE
            u = dt / dur
            syll_env = (math.sin(math.pi * u) ** 0.7) * math.exp(-dt * 4.5)
            tymbal_am = 0.72 + 0.28 * math.sin(TWO_PI * f_tymbal * dt)
            # Two-step 'Ka -> na' slight upward inflection inside each syllable
            infl = 1.0 - 0.035 * math.exp(-dt * 45.0)
            sig = 0.64 * math.sin(TWO_PI * f1 * infl * dt + idx_p * 0.3) + 0.36 * math.sin(
                TWO_PI * f2 * infl * dt
            )
            buf[idx] += 0.58 * gain * syll_env * tymbal_am * sig

    buf = apply_schroeder_reverb(buf, room_scale=1.45, feedback=0.79, damping=0.35, wet=0.34)
    return buf


def synth_23_minminzemi_summer_cicada() -> list[float]:
    """Summer Minminzemi cicada ('Miiiin-min-min-min-miiiii...')."""
    buf = zeros(4.25)
    rng = random.Random(3023)
    # Authentic Minminzemi cadence envelopes & formant trajectories:
    # Call segments: long 'Miiin' (0.12..0.95), 'min' (1.02..1.45), 'min' (1.52..1.95),
    # 'min' (2.02..2.45), tapering 'miiiii...' (2.52..3.95)
    segments = [
        (0.12, 0.82, 1.00, True),
        (1.00, 0.42, 0.92, False),
        (1.48, 0.42, 0.88, False),
        (1.96, 0.42, 0.82, False),
        (2.44, 1.50, 0.76, True),
    ]
    raw = zeros(4.25)
    phase_c = 0.0
    for t0, dur, amp, is_long in segments:
        i0 = int(round(t0 * SAMPLE_RATE))
        i1 = min(len(raw), i0 + int(round(dur * SAMPLE_RATE)))
        n_seg = max(1, i1 - i0)
        for k in range(n_seg):
            u = k / float(n_seg)
            # 'Mi-i-n' pitch curve: rises sharply then drops into nasal 'n'
            curve = math.sin(math.pi * min(1.0, u * (1.15 if is_long else 1.0)))
            f_pulse = 165.0 + 48.0 * curve
            phase_c += TWO_PI * f_pulse / SAMPLE_RATE
            # Rich pulse-train buzz (harmonics 1..12) + subtle air buzz
            buzz = (
                0.30 * math.sin(phase_c)
                + 0.26 * math.sin(2.0 * phase_c)
                + 0.22 * math.sin(6.0 * phase_c)
                + 0.18 * math.sin(9.0 * phase_c)
                + 0.14 * math.sin(12.0 * phase_c)
                + 0.08 * (rng.random() * 2.0 - 1.0)
            )
            env = math.sin(math.pi * u) ** (0.55 if not is_long else 0.75)
            if is_long and t0 > 2.0:
                env *= (1.0 - u) ** 0.55
            raw[i0 + k] += amp * env * buzz

    # Dual nasal cicada body formants (~1550 Hz & ~2850 Hz)
    f_low = biquad_filter(raw, "bandpass", 1580.0, q=2.4)
    f_high = biquad_filter(raw, "bandpass", 2880.0, q=2.8)
    for i in range(len(buf)):
        buf[i] = f_low[i] * 0.75 + f_high[i] * 0.65

    buf = apply_schroeder_reverb(buf, room_scale=1.20, feedback=0.70, damping=0.40, wet=0.22)
    return buf


def synth_24_jihanki_vending_can_drop() -> list[float]:
    """Night Jihanki vending machine hum + button Pi! + heavy cold can drop ('Gakon!')."""
    buf = zeros(2.85)
    rng = random.Random(3024)

    # 1. Quiet nocturnal compressor hum (100 Hz + 200 Hz + gentle fan)
    for i in range(len(buf)):
        t = i / SAMPLE_RATE
        buf[i] += (
            0.018 * math.sin(TWO_PI * 100.0 * t)
            + 0.011 * math.sin(TWO_PI * 200.0 * t)
            + 0.005 * math.sin(TWO_PI * 300.0 * t)
            + 0.0025 * (rng.random() * 2.0 - 1.0)
        )

    # 2. Plastic button press click + 'Pi!' confirmation beep at t=0.24s
    add_modal_strike(
        buf, 0.22, 0.04, [(880.0, 0.7, 150.0), (2100.0, 0.5, 200.0)], amp=0.22, seed=241
    )
    add_fm_chime_note(
        buf, 0.25, 0.095, 2080.0, amp=0.34, mod_ratio=2.0, mod_index=0.6, decay_rate=16.0
    )

    # 3. Internal release solenoid + chute roll (0.68s - 1.12s)
    add_modal_strike(
        buf, 0.68, 0.14, [(290.0, 0.8, 45.0), (760.0, 0.5, 70.0)], amp=0.26, seed=242
    )
    roll = zeros(2.85)
    for i in range(int(0.75 * SAMPLE_RATE), int(1.14 * SAMPLE_RATE)):
        t = (i / SAMPLE_RATE) - 0.75
        roll[i] = 0.18 * math.sin(math.pi * (t / 0.39)) * (rng.random() * 2.0 - 1.0)
    roll = biquad_filter(roll, "bandpass", 420.0, q=2.2)
    for i in range(len(buf)):
        buf[i] += roll[i]

    # 4. Heavy cold aluminum can hitting steel pickup chute: 'GA-KON!'
    chute_modes = [
        (148.0, 1.00, 14.0),
        (318.0, 0.82, 19.0),
        (685.0, 0.60, 26.0),
        (1390.0, 0.42, 35.0),
        (2740.0, 0.26, 48.0),  # Aluminum can wall ring
    ]
    add_modal_strike(
        buf, 1.14, 0.85, chute_modes, amp=0.82, mallet_noise=0.22, mallet_decay=130.0, seed=243
    )
    add_modal_strike(
        buf,
        1.31,
        0.65,
        [(162.0, 0.85, 18.0), (355.0, 0.70, 24.0), (890.0, 0.48, 34.0), (2680.0, 0.25, 52.0)],
        amp=0.52,
        mallet_noise=0.14,
        mallet_decay=150.0,
        seed=244,
    )

    buf = apply_schroeder_reverb(buf, room_scale=0.88, feedback=0.64, damping=0.46, wet=0.18)
    return buf


# ---------------------------------------------------------------------------
# Category 05: VN Messenger & JRPG UI (16 WAVs)
# ---------------------------------------------------------------------------


def synth_25_messenger_kidoku_pop() -> list[float]:
    """'Kidoku' incoming message / read-receipt water-droplet pop."""
    buf = zeros(0.42)
    i0 = int(0.025 * SAMPLE_RATE)
    dur = 0.072
    n_len = int(dur * SAMPLE_RATE)
    phase = 0.0
    for k in range(n_len):
        u = k / float(n_len)
        # Smooth upward pitch sweep 510 Hz -> 1420 Hz
        freq = 510.0 + 910.0 * (u**0.72)
        phase += TWO_PI * freq / SAMPLE_RATE
        env = math.sin(math.pi * u) ** 0.65 * math.exp(-u * 1.4)
        buf[i0 + k] += 0.74 * env * (0.86 * math.sin(phase) + 0.14 * math.sin(2.0 * phase))

    # Subtle crystalline tail ping
    add_fm_chime_note(
        buf, 0.075, 0.28, 1420.0, amp=0.18, mod_ratio=2.0, mod_index=0.6, decay_rate=14.0
    )
    buf = apply_schroeder_reverb(buf, room_scale=0.45, feedback=0.48, damping=0.45, wet=0.10)
    return buf


def synth_26_messenger_send_swoosh() -> list[float]:
    """Outgoing chat message airy send swoosh + soft ascending confirmation."""
    buf = zeros(0.48)
    rng = random.Random(3026)

    # Time-varying swept resonance swoosh (650 Hz -> 3200 Hz)
    n_sw = int(0.165 * SAMPLE_RATE)
    i0 = int(0.025 * SAMPLE_RATE)
    y1 = 0.0
    y2 = 0.0
    for k in range(n_sw):
        u = k / float(n_sw)
        f_center = 650.0 + 2550.0 * (u**1.3)
        w0 = TWO_PI * f_center / SAMPLE_RATE
        r = 0.92
        x = (rng.random() * 2.0 - 1.0) * math.sin(math.pi * u)
        y0 = (1.0 - r) * x + 2.0 * r * math.cos(w0) * y1 - (r * r) * y2
        y2 = y1
        y1 = y0
        buf[i0 + k] += 0.42 * y0

    add_fm_chime_note(
        buf, 0.095, 0.16, 880.0, amp=0.28, mod_ratio=2.0, mod_index=0.8, decay_rate=15.0
    )
    add_fm_chime_note(
        buf, 0.145, 0.25, 1318.5, amp=0.34, mod_ratio=2.0, mod_index=0.7, decay_rate=12.0
    )
    return buf


def synth_27_messenger_sticker_bounce() -> list[float]:
    """Cute Tokyo chat sticker ('Stamp') playful rubbery two-bounce pop."""
    buf = zeros(0.66)
    for b_idx, (t0, dur, f0, f1, amp) in enumerate(
        ((0.03, 0.16, 360.0, 820.0, 0.65), (0.19, 0.26, 540.0, 1046.5, 0.72))
    ):
        i0 = int(t0 * SAMPLE_RATE)
        n_len = int(dur * SAMPLE_RATE)
        phase = 0.0
        for k in range(n_len):
            u = k / float(n_len)
            # Bouncy pitch overshoot + settle
            bounce = math.sin(math.pi * min(1.0, u * 1.35))
            freq = f0 + (f1 - f0) * bounce
            phase += TWO_PI * freq / SAMPLE_RATE
            env = (math.sin(math.pi * min(1.0, u * 1.1)) ** 0.55) * math.exp(-u * 2.2)
            sig = 0.75 * math.sin(phase) + 0.25 * math.sin(2.0 * phase + 0.4 * math.sin(3.0 * phase))
            buf[i0 + k] += amp * env * sig
        if b_idx == 1:
            add_fm_chime_note(
                buf, t0 + 0.05, 0.35, 1567.98, amp=0.22, mod_ratio=2.0, mod_index=1.0, decay_rate=10.0
            )
    buf = apply_schroeder_reverb(buf, room_scale=0.50, feedback=0.52, damping=0.45, wet=0.12)
    return buf


def synth_28_messenger_typing_tick() -> list[float]:
    """Capacitive smartphone keyboard / typing '...' indicator crisp soft tick."""
    buf = zeros(0.16)
    add_modal_strike(
        buf,
        0.015,
        0.09,
        [(1680.0, 0.9, 130.0), (3420.0, 0.55, 190.0), (5800.0, 0.25, 260.0)],
        amp=0.55,
        mallet_noise=0.05,
        mallet_decay=350.0,
        seed=281,
    )
    return buf


def synth_29_smartphone_desk_vibrate() -> list[float]:
    """Smartphone vibrating twice on a wooden study desk at night ('Bzz... Bzz...')."""
    buf = zeros(1.28)
    for t0 in (0.08, 0.64):
        i0 = int(t0 * SAMPLE_RATE)
        dur = 0.39
        n_len = int(dur * SAMPLE_RATE)
        att = int(0.028 * SAMPLE_RATE)
        rel = int(0.042 * SAMPLE_RATE)
        for k in range(n_len):
            t = k / SAMPLE_RATE
            ea = 0.5 * (1.0 - math.cos(math.pi * k / float(att))) if k < att else 1.0
            rem = n_len - 1 - k
            er = 0.5 * (1.0 - math.cos(math.pi * rem / float(rel))) if rem < rel else 1.0
            # 154 Hz linear resonant actuator + wooden tabletop buzz harmonics
            buzz = (
                0.55 * math.sin(TWO_PI * 154.0 * t)
                + 0.26 * math.sin(TWO_PI * 308.0 * t + 0.5)
                + 0.14 * math.sin(TWO_PI * 462.0 * t)
                + 0.09 * math.sin(TWO_PI * 770.0 * t)
                + 0.05 * math.sin(TWO_PI * 1078.0 * t)
            )
            # Subtle wood-contact amplitude flutter at 38 Hz
            flutter = 0.88 + 0.12 * math.sin(TWO_PI * 38.5 * t)
            buf[i0 + k] += 0.65 * ea * er * flutter * buzz

    buf = apply_schroeder_reverb(buf, room_scale=0.55, feedback=0.54, damping=0.55, wet=0.12)
    return buf


def _make_vn_blip(
    base_freq: float,
    end_freq: float,
    dur_sec: float,
    harm2: float,
    harm3: float,
    lp_hz: float,
) -> list[float]:
    """Helper for non-fatiguing musical Visual Novel text blips."""
    buf = zeros(0.14)
    i0 = int(0.012 * SAMPLE_RATE)
    n_len = int(dur_sec * SAMPLE_RATE)
    att = max(16, int(0.004 * SAMPLE_RATE))
    phase = 0.0
    for k in range(n_len):
        u = k / float(n_len)
        freq = base_freq + (end_freq - base_freq) * u
        phase += TWO_PI * freq / SAMPLE_RATE
        ea = (k / float(att)) if k < att else 1.0
        env = ea * ((1.0 - u) ** 1.35)
        sig = math.sin(phase) + harm2 * math.sin(2.0 * phase) + harm3 * math.sin(3.0 * phase)
        buf[i0 + k] = 0.62 * env * sig
    return biquad_filter(buf, "lowpass", lp_hz, q=0.8)


def synth_30_vn_blip_female_bright() -> list[float]:
    """VN dialogue text blip: cheerful heroine voice (660 -> 715 Hz)."""
    return _make_vn_blip(660.0, 715.0, 0.058, harm2=0.28, harm3=0.08, lp_hz=3200.0)


def synth_31_vn_blip_female_calm() -> list[float]:
    """VN dialogue text blip: calm senpai / kuudere voice (494 -> 486 Hz)."""
    return _make_vn_blip(493.88, 486.0, 0.064, harm2=0.18, harm3=0.04, lp_hz=2400.0)


def synth_32_vn_blip_male_low() -> list[float]:
    """VN dialogue text blip: warm baritone / male lead voice (247 -> 238 Hz)."""
    return _make_vn_blip(246.94, 238.0, 0.068, harm2=0.36, harm3=0.16, lp_hz=1650.0)


def synth_33_vn_blip_typewriter_mech() -> list[float]:
    """Mystery / detective VN tactile mechanical key-switch text blip."""
    buf = zeros(0.12)
    add_modal_strike(
        buf,
        0.010,
        0.075,
        [(430.0, 0.85, 95.0), (1380.0, 0.65, 165.0), (3150.0, 0.55, 240.0)],
        amp=0.60,
        mallet_noise=0.14,
        mallet_decay=320.0,
        seed=331,
    )
    return buf


def synth_34_ui_choice_hover_soft() -> list[float]:
    """Branching choice button hover soft crystalline tick (G6)."""
    buf = zeros(0.24)
    add_fm_chime_note(
        buf, 0.015, 0.19, 1567.98, amp=0.44, mod_ratio=2.0, mod_index=0.75, decay_rate=18.0
    )
    return buf


def synth_35_ui_confirm_sparkle() -> list[float]:
    """Menu / choice confirm ascending D-major sparkle arpeggio."""
    buf = zeros(0.88)
    notes = [(74, 0.02), (78, 0.075), (81, 0.13), (86, 0.185)]
    for idx_n, (midi_n, t0) in enumerate(notes):
        dur = 0.28 if idx_n < 3 else 0.62
        add_fm_chime_note(
            buf,
            start_sec=t0,
            duration_sec=dur,
            freq_hz=note_hz(midi_n),
            amp=0.45,
            mod_ratio=3.0,
            mod_index=1.35,
            decay_rate=7.5 if idx_n < 3 else 3.8,
            brightness_decay=16.0,
        )
    buf = apply_schroeder_reverb(buf, room_scale=0.68, feedback=0.64, damping=0.35, wet=0.20)
    return buf


def synth_36_ui_cancel_back() -> list[float]:
    """Menu cancel / back mellow descending 2-step (E5 -> A4)."""
    buf = zeros(0.48)
    add_fm_chime_note(
        buf, 0.02, 0.18, 659.25, amp=0.46, mod_ratio=2.0, mod_index=0.9, decay_rate=11.0
    )
    add_fm_chime_note(
        buf, 0.11, 0.32, 440.00, amp=0.48, mod_ratio=2.0, mod_index=0.8, decay_rate=7.5
    )
    buf = apply_schroeder_reverb(buf, room_scale=0.52, feedback=0.52, damping=0.50, wet=0.14)
    return buf


def synth_37_ui_save_slot_chime() -> list[float]:
    """Visual Novel save-slot bookmark chime (dreamy Fmaj9 harp/celesta strum)."""
    buf = zeros(1.40)
    chord = [65, 69, 72, 76, 79, 84]  # F4 A4 C5 E5 G5 C6
    for idx_c, midi_n in enumerate(chord):
        add_fm_chime_note(
            buf,
            start_sec=0.03 + idx_c * 0.048,
            duration_sec=1.08 - idx_c * 0.04,
            freq_hz=note_hz(midi_n),
            amp=0.30,
            mod_ratio=2.0,
            mod_index=1.15,
            decay_rate=2.6,
            brightness_decay=10.0,
        )
    buf = apply_schroeder_reverb(buf, room_scale=0.95, feedback=0.72, damping=0.36, wet=0.26)
    return buf


def synth_38_vn_affection_up_chime() -> list[float]:
    """Heroine Route / Affection Up ('Koukando UP!') sparkling pentatonic glissando."""
    buf = zeros(1.58)
    gliss = [72, 74, 76, 79, 81, 84, 88]  # C5 D5 E5 G5 A5 C6 E6
    for idx_g, midi_n in enumerate(gliss):
        is_top = idx_g == len(gliss) - 1
        add_fm_chime_note(
            buf,
            start_sec=0.03 + idx_g * 0.062,
            duration_sec=1.05 if is_top else 0.48,
            freq_hz=note_hz(midi_n),
            amp=0.42 if is_top else 0.30,
            mod_ratio=3.0,
            mod_index=1.45,
            decay_rate=2.4 if is_top else 5.2,
            brightness_decay=12.0,
        )
    # Warm C-major pad harmonic underneath final sparkle
    for pad_n in (60, 67, 76):
        add_fm_chime_note(
            buf, 0.40, 1.05, note_hz(pad_n), amp=0.16, mod_ratio=1.0, mod_index=0.5, decay_rate=2.2
        )
    buf = apply_schroeder_reverb(buf, room_scale=1.08, feedback=0.75, damping=0.32, wet=0.28)
    return buf


def synth_39_vn_horror_dread_sting() -> list[float]:
    """Psychological / mystery VN sudden dread sting (sub impact + waterphone cluster)."""
    buf = zeros(2.85)
    # Deep sub-bass heart-drop boom + bowed dissonant tritone/minor-second cluster
    n = len(buf)
    i0 = int(0.03 * SAMPLE_RATE)
    for idx in range(i0, n):
        t = (idx - i0) / SAMPLE_RATE
        att = min(1.0, t / 0.018)
        # Sub boom pitching down 68 Hz -> 42 Hz
        sub_phase = TWO_PI * (42.0 * t + 1.8 * (1.0 - math.exp(-t * 8.0)))
        sub = 0.58 * math.sin(sub_phase) * math.exp(-t * 2.1)

        # Bowed metallic cluster (Bb3 233.08, B3 246.94, Eb5 622.25, E5 659.25 + FM)
        bow_env = min(1.0, t / 0.14) * math.exp(-t * 1.15)
        fm_wobble = 1.8 * math.sin(TWO_PI * 6.3 * t)
        cluster = (
            0.24 * math.sin(TWO_PI * 233.08 * t + fm_wobble)
            + 0.24 * math.sin(TWO_PI * 246.94 * t - fm_wobble)
            + 0.18 * math.sin(TWO_PI * 622.25 * t + 2.2 * math.sin(TWO_PI * 931.0 * t))
            + 0.16 * math.sin(TWO_PI * 1318.5 * t * (1.0 - 0.015 * t)) * math.exp(-t * 2.4)
        )
        buf[idx] += att * (sub + bow_env * cluster)

    buf = apply_schroeder_reverb(buf, room_scale=1.65, feedback=0.84, damping=0.45, wet=0.40)
    return buf


def synth_40_vn_flashback_shimmer() -> list[float]:
    """VN memory / flashback transition (reverse-bloom whole-tone harp wash)."""
    buf = zeros(2.45)
    # Whole-tone dream scale: C5 D5 F#5 G#5 Bb5 C6 D6 F#6 with swelling envelope
    scale_notes = [72, 74, 78, 80, 82, 84, 86, 90]
    n = len(buf)
    for idx_s, midi_n in enumerate(scale_notes):
        f_hz = note_hz(midi_n)
        t_peak = 0.28 + idx_s * 0.13
        i_start = int(max(0.02, t_peak - 0.35) * SAMPLE_RATE)
        i_end = min(n, int((t_peak + 1.15) * SAMPLE_RATE))
        for idx in range(i_start, i_end):
            t_abs = idx / SAMPLE_RATE
            dt = t_abs - t_peak
            # Asymmetric reverse-swell + gentle decay
            if dt < 0.0:
                env = math.exp(-((dt / 0.19) ** 2))
            else:
                env = math.exp(-dt * 2.4)
            sig = 0.72 * math.sin(TWO_PI * f_hz * t_abs) + 0.28 * math.sin(
                TWO_PI * (f_hz * 2.0) * t_abs + 0.6 * math.sin(TWO_PI * 5.0 * t_abs)
            )
            buf[idx] += 0.21 * env * sig

    buf = apply_schroeder_reverb(buf, room_scale=1.50, feedback=0.82, damping=0.30, wet=0.38)
    return buf


# ---------------------------------------------------------------------------
# Master Catalog of All 40 Tokyo WAV Specifications
# ---------------------------------------------------------------------------


SFX_CATALOG: tuple[SfxSpec, ...] = (
    # 01_school_chimes (4)
    SfxSpec(
        1,
        "01_school_chimes",
        "01_school_chime_courtyard_westminster.wav",
        "High School Courtyard Chime (Kin-Kon-Kan-Kon)",
        "放課後チャイム（校庭スピーカー・4フレーズ）",
        True,
        0.86,
        synth_01_school_chime_courtyard,
    ),
    SfxSpec(
        2,
        "01_school_chimes",
        "02_school_chime_classroom_speaker.wav",
        "Classroom Wall Speaker Chime",
        "教室内放送チャイム（壁掛けスピーカー）",
        False,
        0.84,
        synth_02_school_chime_classroom_speaker,
    ),
    SfxSpec(
        3,
        "01_school_chimes",
        "03_homeroom_two_tone_chime.wav",
        "Homeroom 2-Tone Chime (Pin-Pon)",
        "予鈴2音チャイム（ピンポーン）",
        False,
        0.84,
        synth_03_homeroom_two_tone_chime,
    ),
    SfxSpec(
        4,
        "01_school_chimes",
        "04_pa_broadcast_four_note_prefix.wav",
        "School PA 4-Note Broadcast Prefix",
        "校内放送4音プレフィックス（上りチャイム）",
        False,
        0.84,
        synth_04_pa_broadcast_four_note_prefix,
    ),
    # 02_konbini_and_shops (5)
    SfxSpec(
        5,
        "02_konbini_and_shops",
        "05_konbini_door_melody_sunny_a.wav",
        "Konbini Door Melody A (Original Sunny G-Maj)",
        "コンビニ入店メロディA（オリジナル明快Gメジャー）",
        True,
        0.85,
        synth_05_konbini_door_melody_sunny_a,
    ),
    SfxSpec(
        6,
        "02_konbini_and_shops",
        "06_konbini_door_melody_breeze_b.wav",
        "Konbini Door Melody B (Original Night Eb-Maj)",
        "コンビニ入店メロディB（オリジナル夜風Ebメジャー）",
        False,
        0.85,
        synth_06_konbini_door_melody_breeze_b,
    ),
    SfxSpec(
        7,
        "02_konbini_and_shops",
        "07_izakaya_sliding_door_chirin.wav",
        "Izakaya Wooden Sliding Door & Brass Bell",
        "居酒屋・古書店の引き戸と真鍮ドアベル（ガラガラ・チリン）",
        False,
        0.85,
        synth_07_izakaya_sliding_door_chirin,
    ),
    SfxSpec(
        8,
        "02_konbini_and_shops",
        "08_ic_card_transit_pass_pipi.wav",
        "IC Transit Gate Pass Chirp (Pi-Pi!)",
        "交通系IC改札タッチ通過音（ピピッ！）",
        True,
        0.82,
        synth_08_ic_card_transit_pass_pipi,
    ),
    SfxSpec(
        9,
        "02_konbini_and_shops",
        "09_ic_card_error_triple_beep.wav",
        "IC Transit Gate Error Triple Beep",
        "自動改札エラー警告音（ピピピッ・扉閉）",
        False,
        0.84,
        synth_09_ic_card_error_triple_beep,
    ),
    # 03_trains_and_crossings (7)
    SfxSpec(
        10,
        "03_trains_and_crossings",
        "10_fumikiri_railroad_crossing_loop.wav",
        "Fumikiri Railroad Crossing (700+748Hz Dual Bell)",
        "踏切警報機カンカン音（2周波うなり物理モデル）",
        True,
        0.86,
        synth_10_fumikiri_railroad_crossing,
    ),
    SfxSpec(
        11,
        "03_trains_and_crossings",
        "11_ekimelo_commuter_platform_sunrise.wav",
        "Tokyo Platform Departure Eki-Melo A (Original)",
        "駅ホーム発車メロディA（オリジナル朝陽Cメジャー）",
        False,
        0.85,
        synth_11_ekimelo_commuter_platform_sunrise,
    ),
    SfxSpec(
        12,
        "03_trains_and_crossings",
        "12_ekimelo_twilight_express_chime.wav",
        "Tokyo Platform Departure Eki-Melo B (Original)",
        "駅ホーム発車メロディB（オリジナル夕暮れ快速）",
        False,
        0.85,
        synth_12_ekimelo_twilight_express_chime,
    ),
    SfxSpec(
        13,
        "03_trains_and_crossings",
        "13_commuter_door_close_and_hiss.wav",
        "Commuter Train Door Chime & Pneumatic Hiss",
        "電車ドア閉まり予告音＋プシュー閉扉音",
        False,
        0.85,
        synth_13_commuter_door_close_and_hiss,
    ),
    SfxSpec(
        14,
        "03_trains_and_crossings",
        "14_shinkansen_cabin_chime_original.wav",
        "Bullet Train Cabin Chime (Original)",
        "特急・新幹線車内チャイム（オリジナル6音）",
        False,
        0.84,
        synth_14_shinkansen_cabin_chime_original,
    ),
    SfxSpec(
        15,
        "03_trains_and_crossings",
        "15_crosswalk_piyo_piyo_bird.wav",
        "Pedestrian Crosswalk Signal (Piyo-Piyo)",
        "音響式信号機「ピヨピヨ」",
        False,
        0.82,
        synth_15_crosswalk_piyo_piyo_bird,
    ),
    SfxSpec(
        16,
        "03_trains_and_crossings",
        "16_crosswalk_kakkou_cuckoo.wav",
        "Pedestrian Crosswalk Signal (Kakkou)",
        "音響式信号機「カッコー」",
        False,
        0.82,
        synth_16_crosswalk_kakkou_cuckoo,
    ),
    # 04_shrine_and_seasons (8)
    SfxSpec(
        17,
        "04_shrine_and_seasons",
        "17_edo_furin_glass_wind_chime_a.wav",
        "Edo Furin Glass Wind Chime A",
        "江戸風鈴A（涼風チリン・高Qガラス共鳴）",
        True,
        0.84,
        synth_17_edo_furin_glass_wind_chime_a,
    ),
    SfxSpec(
        18,
        "04_shrine_and_seasons",
        "18_edo_furin_glass_wind_chime_b.wav",
        "Edo Furin Glass Wind Chime B",
        "江戸風鈴B（中音ガラス鉢・二重余韻）",
        False,
        0.84,
        synth_18_edo_furin_glass_wind_chime_b,
    ),
    SfxSpec(
        19,
        "04_shrine_and_seasons",
        "19_shishi_odoshi_bamboo_fountain.wav",
        "Shishi-Odoshi Water Trickle & Bamboo Knock",
        "日本庭園の鹿威し（水滴と竹の「カコーン！」）",
        False,
        0.86,
        synth_19_shishi_odoshi_bamboo_fountain,
    ),
    SfxSpec(
        20,
        "04_shrine_and_seasons",
        "20_shrine_suzu_sacred_bell_shake.wav",
        "Shinto Shrine Suzu Sacred Bell Shake",
        "神社の本坪鈴（麻緒と鈴の巫女・参拝音）",
        False,
        0.85,
        synth_20_shrine_suzu_sacred_bell_shake,
    ),
    SfxSpec(
        21,
        "04_shrine_and_seasons",
        "21_shrine_kashiwade_two_claps.wav",
        "Shinto Shrine Kashiwade (2 Prayer Claps)",
        "神社の二拍手（柏手・境内残響）",
        False,
        0.85,
        synth_21_shrine_kashiwade_two_claps,
    ),
    SfxSpec(
        22,
        "04_shrine_and_seasons",
        "22_higurashi_twilight_cicada.wav",
        "Evening Higurashi Twilight Cicada",
        "夕暮れのヒグラシ（カナカナカナ…）",
        True,
        0.82,
        synth_22_higurashi_twilight_cicada,
    ),
    SfxSpec(
        23,
        "04_shrine_and_seasons",
        "23_minminzemi_summer_cicada.wav",
        "Mid-Summer Minminzemi Cicada",
        "真夏のミンミンゼミ（ミーンミンミンミー…）",
        False,
        0.82,
        synth_23_minminzemi_summer_cicada,
    ),
    SfxSpec(
        24,
        "04_shrine_and_seasons",
        "24_jihanki_vending_can_drop.wav",
        "Night Jihanki Vending Machine & Cold Can Drop",
        "夜の自動販売機（駆動ハム音＋ボタン＋ガコン！）",
        False,
        0.86,
        synth_24_jihanki_vending_can_drop,
    ),
    # 05_vn_messenger_and_jrpg_ui (16)
    SfxSpec(
        25,
        "05_vn_messenger_and_jrpg_ui",
        "25_messenger_kidoku_pop.wav",
        "Messenger 'Kidoku' Read / Bubble Pop",
        "スマホチャット受信・既読ポップ音",
        True,
        0.78,
        synth_25_messenger_kidoku_pop,
    ),
    SfxSpec(
        26,
        "05_vn_messenger_and_jrpg_ui",
        "26_messenger_send_swoosh.wav",
        "Messenger Outgoing Send Swoosh",
        "スマホチャット送信スウッシュ音",
        False,
        0.78,
        synth_26_messenger_send_swoosh,
    ),
    SfxSpec(
        27,
        "05_vn_messenger_and_jrpg_ui",
        "27_messenger_sticker_bounce.wav",
        "Messenger Sticker / Stamp Bounce",
        "スタンプ送信バウンス音",
        False,
        0.80,
        synth_27_messenger_sticker_bounce,
    ),
    SfxSpec(
        28,
        "05_vn_messenger_and_jrpg_ui",
        "28_messenger_typing_tick.wav",
        "Messenger Typing '...' Soft Tick",
        "入力中「…」ソフトタップ音",
        False,
        0.68,
        synth_28_messenger_typing_tick,
    ),
    SfxSpec(
        29,
        "05_vn_messenger_and_jrpg_ui",
        "29_smartphone_desk_vibrate.wav",
        "Smartphone Vibrating on Wooden Desk",
        "机の上のスマホバイブ着信音（ブブッ…ブブッ…）",
        False,
        0.82,
        synth_29_smartphone_desk_vibrate,
    ),
    SfxSpec(
        30,
        "05_vn_messenger_and_jrpg_ui",
        "30_vn_blip_female_bright.wav",
        "VN Dialogue Text Blip (Female Bright)",
        "ノベル文字送り音（ヒロイン・明るい声）",
        True,
        0.70,
        synth_30_vn_blip_female_bright,
    ),
    SfxSpec(
        31,
        "05_vn_messenger_and_jrpg_ui",
        "31_vn_blip_female_calm.wav",
        "VN Dialogue Text Blip (Female Calm)",
        "ノベル文字送り音（先輩・落ち着いた声）",
        False,
        0.70,
        synth_31_vn_blip_female_calm,
    ),
    SfxSpec(
        32,
        "05_vn_messenger_and_jrpg_ui",
        "32_vn_blip_male_low.wav",
        "VN Dialogue Text Blip (Male Low)",
        "ノベル文字送り音（男性・低音）",
        False,
        0.72,
        synth_32_vn_blip_male_low,
    ),
    SfxSpec(
        33,
        "05_vn_messenger_and_jrpg_ui",
        "33_vn_blip_typewriter_mech.wav",
        "VN Dialogue Text Blip (Mechanical Key)",
        "ノベル文字送り音（タイプライター・調査パート）",
        False,
        0.72,
        synth_33_vn_blip_typewriter_mech,
    ),
    SfxSpec(
        34,
        "05_vn_messenger_and_jrpg_ui",
        "34_ui_choice_hover_soft.wav",
        "UI Choice Hover Crystal Tick",
        "選択肢ホバー音（クリスタル）",
        False,
        0.68,
        synth_34_ui_choice_hover_soft,
    ),
    SfxSpec(
        35,
        "05_vn_messenger_and_jrpg_ui",
        "35_ui_confirm_sparkle.wav",
        "UI Confirm Sparkle Arpeggio",
        "決定・ルート確定スパークル音",
        False,
        0.82,
        synth_35_ui_confirm_sparkle,
    ),
    SfxSpec(
        36,
        "05_vn_messenger_and_jrpg_ui",
        "36_ui_cancel_back.wav",
        "UI Cancel / Back Two-Step",
        "キャンセル・戻る音",
        False,
        0.76,
        synth_36_ui_cancel_back,
    ),
    SfxSpec(
        37,
        "05_vn_messenger_and_jrpg_ui",
        "37_ui_save_slot_chime.wav",
        "VN Save Slot Bookmark Chime",
        "セーブ完了・しおりチャイム",
        False,
        0.82,
        synth_37_ui_save_slot_chime,
    ),
    SfxSpec(
        38,
        "05_vn_messenger_and_jrpg_ui",
        "38_vn_affection_up_chime.wav",
        "VN Affection / Bond Up Chime",
        "好感度UP・絆きらめきチャイム",
        False,
        0.84,
        synth_38_vn_affection_up_chime,
    ),
    SfxSpec(
        39,
        "05_vn_messenger_and_jrpg_ui",
        "39_vn_horror_dread_sting.wav",
        "VN Mystery / Horror Dread Sting",
        "不穏・サスペンス衝撃スティング音",
        False,
        0.86,
        synth_39_vn_horror_dread_sting,
    ),
    SfxSpec(
        40,
        "05_vn_messenger_and_jrpg_ui",
        "40_vn_flashback_shimmer.wav",
        "VN Memory / Flashback Shimmer",
        "回想シーン遷移・記憶のきらめき音",
        False,
        0.82,
        synth_40_vn_flashback_shimmer,
    ),
)


def write_wav_pcm16(target_path: Path, pcm_bytes: bytes) -> None:
    """Write mono 48,000 Hz 16-bit PCM bytes to a standard RIFF WAV file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)


def synthesize_all_sfx(output_dir: Path | None = None) -> list[Path]:
    """Synthesize all 40 Tokyo WAV files into output_dir (defaults to dist/sfx)."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "dist" / "sfx"
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for spec in SFX_CATALOG:
        raw_samples = spec.builder()
        # Shorter UI blips get tighter 1.5ms/8ms fades; ambient chimes get 2.5ms/18ms
        is_short_ui = len(raw_samples) < int(0.30 * SAMPLE_RATE)
        pcm_bytes = finalize_pcm16(
            raw_samples,
            peak_target=spec.peak_target,
            fade_in_ms=1.5 if is_short_ui else 2.5,
            fade_out_ms=8.0 if is_short_ui else 18.0,
        )
        out_path = output_dir / spec.folder / spec.filename
        write_wav_pcm16(out_path, pcm_bytes)
        written.append(out_path)
    return written


if __name__ == "__main__":
    generated = synthesize_all_sfx()
    print(f"Synthesized {len(generated)} WAV files (48,000 Hz, 16-bit PCM).")
