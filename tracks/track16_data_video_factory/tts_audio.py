"""Zero-cost ($0.00) macOS neural TTS + pluggable Edge-TTS / ElevenLabs audio mastering.

Renders clean 48kHz stereo mastered narration audio with an optional subtle
procedural ambient pulse bed generated purely in FFmpeg (zero copyright risk).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class AudioRenderError(RuntimeError):
    """Raised when TTS synthesis or FFmpeg audio mastering fails."""


@dataclass(frozen=True)
class MasteredAudio:
    """Result metadata for a mastered narration WAV/M4A file."""

    path: Path
    duration: float
    speech_start: float
    speech_duration: float
    backend: str
    voice: str


def find_binary(name: str, fallbacks: Sequence[str] = ()) -> str:
    """Locate an executable binary cleanly across PATH and Homebrew paths."""
    found = shutil.which(name)
    if found:
        return found
    for candidate in fallbacks:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise AudioRenderError("Required binary %r not found on system" % (name,))


def get_ffmpeg_bin() -> str:
    return find_binary("ffmpeg", ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"))


def get_ffprobe_bin() -> str:
    return find_binary("ffprobe", ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"))


def list_macos_voices() -> List[str]:
    """Return installed macOS `/usr/bin/say` voice names."""
    say_bin = find_binary("say", ("/usr/bin/say",))
    proc = subprocess.run(
        [say_bin, "-v", "?"],
        capture_output=True,
        text=True,
        check=True,
    )
    voices: List[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # Voice name precedes the locale column (e.g. "Ava (Premium)       en_US")
        parts = line.split("  ")
        name = parts[0].strip()
        if name:
            voices.append(name)
    return voices


def select_macos_voice(lang: str = "en", preferred_voice: Optional[str] = None) -> str:
    """Pick the highest quality installed macOS voice for the given language."""
    installed = list_macos_voices()
    if preferred_voice and preferred_voice in installed:
        return preferred_voice

    if lang.lower().startswith("ja"):
        candidates = ("Kyoko (Enhanced)", "Kyoko", "Otoya", "Eddy (日本語（日本）)")
    else:
        candidates = ("Ava (Premium)", "Daniel", "Samantha", "Alex", "Karen")

    for cand in candidates:
        if cand in installed:
            return cand
    if installed:
        return installed[0]
    raise AudioRenderError("No macOS voices available via /usr/bin/say")


def probe_media(media_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect a video or audio file with ffprobe and return structured metadata."""
    ffprobe_bin = get_ffprobe_bin()
    p = Path(media_path)
    if not p.exists():
        raise AudioRenderError("Media file does not exist: %s" % p)

    proc = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(p),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    return {
        "path": str(p),
        "size_bytes": p.stat().st_size,
        "duration": float(fmt.get("duration", 0.0)),
        "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else 0,
        "video": (
            {
                "codec_name": video_stream.get("codec_name"),
                "pix_fmt": video_stream.get("pix_fmt"),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "r_frame_rate": video_stream.get("r_frame_rate"),
            }
            if video_stream
            else None
        ),
        "audio": (
            {
                "codec_name": audio_stream.get("codec_name"),
                "sample_rate": int(audio_stream.get("sample_rate", 0))
                if audio_stream.get("sample_rate")
                else 0,
                "channels": int(audio_stream.get("channels", 0)),
            }
            if audio_stream
            else None
        ),
    }


def _synthesize_macos_say(
    text: str,
    out_raw: Path,
    lang: str = "en",
    voice: Optional[str] = None,
    rate_wpm: Optional[int] = None,
) -> Tuple[Path, str]:
    say_bin = find_binary("say", ("/usr/bin/say",))
    chosen_voice = select_macos_voice(lang=lang, preferred_voice=voice)
    wpm = rate_wpm if rate_wpm is not None else (196 if lang.lower().startswith("ja") else 188)
    cmd = [say_bin, "-v", chosen_voice, "-r", str(wpm), "-o", str(out_raw), text]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_raw.exists() or out_raw.stat().st_size == 0:
        raise AudioRenderError(
            "macOS say failed (rc=%d): %s" % (proc.returncode, proc.stderr.strip())
        )
    return out_raw, chosen_voice


def _synthesize_edge_tts(
    text: str,
    out_raw: Path,
    lang: str = "en",
    voice: Optional[str] = None,
) -> Tuple[Path, str]:
    edge_bin = find_binary("edge-tts")
    chosen_voice = voice or ("ja-JP-NanamiNeural" if lang.lower().startswith("ja") else "en-US-AndrewNeural")
    cmd = [edge_bin, "--voice", chosen_voice, "--text", text, "--write-media", str(out_raw)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_raw.exists():
        raise AudioRenderError("edge-tts failed: %s" % proc.stderr.strip())
    return out_raw, chosen_voice


def _synthesize_elevenlabs(
    text: str,
    out_raw: Path,
    voice: Optional[str] = None,
) -> Tuple[Path, str]:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise AudioRenderError(
            "ELEVENLABS_API_KEY is not set; use default zero-cost 'macos_say' backend instead."
        )
    voice_id = voice or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    url = "https://api.elevenlabs.io/v1/text-to-speech/%s" % voice_id
    payload = json.dumps(
        {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.78},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out_raw.write_bytes(resp.read())
    return out_raw, voice_id


def synthesize_mastered_narration(
    text: str,
    output_wav: Union[str, Path],
    lang: str = "en",
    backend: str = "macos_say",
    voice: Optional[str] = None,
    rate_wpm: Optional[int] = None,
    include_ambient_bed: bool = True,
    lead_in_sec: float = 0.25,
    tail_pad_sec: float = 0.75,
) -> MasteredAudio:
    """Generate spoken narration and master it to 48kHz stereo WAV via FFmpeg."""
    if not text.strip():
        raise AudioRenderError("Narration text must be non-empty")

    ffmpeg_bin = get_ffmpeg_bin()
    out_path = Path(output_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="track16_tts_") as tmpdir:
        tmp_dir = Path(tmpdir)
        backend_norm = backend.strip().lower()
        if backend_norm == "macos_say":
            raw_speech, used_voice = _synthesize_macos_say(
                text, tmp_dir / "speech.aiff", lang=lang, voice=voice, rate_wpm=rate_wpm
            )
        elif backend_norm == "edge_tts":
            raw_speech, used_voice = _synthesize_edge_tts(
                text, tmp_dir / "speech.mp3", lang=lang, voice=voice
            )
        elif backend_norm == "elevenlabs":
            raw_speech, used_voice = _synthesize_elevenlabs(
                text, tmp_dir / "speech.mp3", voice=voice
            )
        else:
            raise AudioRenderError("Unsupported TTS backend: %r" % (backend,))

        speech_info = probe_media(raw_speech)
        speech_dur = float(speech_info["duration"])
        if speech_dur <= 0.1:
            raise AudioRenderError("Synthesized speech duration too short: %.3fs" % speech_dur)

        total_dur = speech_dur + lead_in_sec + tail_pad_sec
        delay_ms = int(round(lead_in_sec * 1000.0))

        # Vocal polish chain: clean sub-rumble, subtle presence boost, smooth loudness normalization
        vocal_filter = (
            "[0:a]aresample=48000,"
            "highpass=f=85,"
            "equalizer=f=3400:t=q:w=1.2:g=2.0,"
            "dynaudnorm=f=150:g=11:p=0.90,"
            "aformat=channel_layouts=stereo,"
            "adelay=%d|%d,"
            "apad=pad_dur=%.3f[vox]"
            % (delay_ms, delay_ms, tail_pad_sec + 0.25)
        )

        if include_ambient_bed:
            # Subtle synthetic documentary finance pulse bed (zero copyright, -26dB under speech)
            fade_out_start = max(0.2, total_dur - 0.85)
            bed_expr = (
                "0.045*sin(2*PI*65.41*t)"
                "+0.028*sin(2*PI*98.00*t)"
                "+0.016*sin(2*PI*130.81*t)*(0.55+0.45*sin(2*PI*0.85*t))"
                "+0.010*sin(2*PI*196.00*t)*(0.5+0.5*sin(2*PI*1.70*t))"
            )
            filter_complex = (
                "%s;"
                "[1:a]lowpass=f=280,"
                "aformat=channel_layouts=stereo,"
                "afade=t=in:st=0:d=0.45,"
                "afade=t=out:st=%.3f:d=0.80,"
                "volume=0.35[bed];"
                "[vox][bed]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95,"
                "atrim=0:%.3f[out]"
                % (vocal_filter, fade_out_start, total_dur)
            )
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(raw_speech),
                "-f",
                "lavfi",
                "-i",
                "aevalsrc='%s':s=48000:d=%.3f" % (bed_expr, total_dur),
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(out_path),
            ]
        else:
            filter_complex = "%s;[vox]alimiter=limit=0.95,atrim=0:%.3f[out]" % (
                vocal_filter,
                total_dur,
            )
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(raw_speech),
                "-filter_complex",
                filter_complex,
                "-map",
                "[out]",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(out_path),
            ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_path.exists():
            raise AudioRenderError(
                "FFmpeg audio mastering failed (rc=%d): %s"
                % (proc.returncode, proc.stderr[-500:])
            )

    mastered_info = probe_media(out_path)
    return MasteredAudio(
        path=out_path,
        duration=float(mastered_info["duration"]),
        speech_start=lead_in_sec,
        speech_duration=speech_dur,
        backend=backend_norm,
        voice=used_voice,
    )
