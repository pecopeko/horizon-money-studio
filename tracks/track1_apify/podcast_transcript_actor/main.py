"""Apify Pay-Per-Event Actor: Podcast RSS, Show Notes & Podcasting 2.0 Transcript Extractor."""

from __future__ import annotations

import asyncio
import email.utils
import html
import json
import math
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

try:
    from apify import Actor
except ImportError:  # Allow local unit testing without apify SDK installed.
    Actor = None  # type: ignore[assignment]

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
USER_AGENT = "HorizonPodcastExtractor/1.0 (+https://github.com/pecopeko/apify-ppe-actors)"

_CDATA_RE = re.compile(r"<!\[CDATA\[.*?\]\]>", re.DOTALL)
_UNSAFE_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_XML_ENCODING_RE = re.compile(
    r"^\s*<\?xml[^>]*encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']",
    re.IGNORECASE,
)
_APPLE_ID_RE = re.compile(r"(?:id|^)(\d{5,15})(?:\D|$)")
_TIMING_LINE_RE = re.compile(
    r"^\s*(\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*-->\s*(\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)(?:\s+.*)?$"
)
_VTT_SPEAKER_RE = re.compile(r"<v(?:\.[^>\s]+)?\s+([^>]+)>(.*?)(?:</v>|$)", re.DOTALL)
_INLINE_TAG_RE = re.compile(r"<[^>]+>")
_TXT_TIMESTAMP_LINE_RE = re.compile(
    r"^\s*[\[(](\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)[\])]\s*(.+)$"
)

_TRANSCRIPT_FORMAT_PRIORITY: dict[str, int] = {
    "json": 0,
    "vtt": 1,
    "srt": 2,
    "txt": 3,
}


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML-to-plain-text converter preserving paragraph/line breaks."""

    _BREAK_TAGS = frozenset({"br", "hr", "li", "tr"})
    _BLOCK_TAGS = frozenset({"p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"})
    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lower in self._BREAK_TAGS:
            self._parts.append("\n")
        elif lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if not self._skip_depth and lower in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self._parts.append(data)

    def get_text(self) -> str:
        joined = "".join(self._parts).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in joined.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def strip_html_to_text(raw_html: str | None) -> str:
    """Convert HTML show notes or summaries into clean plain text."""
    if not raw_html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    parser.close()
    text = parser.get_text()
    return html.unescape(text)


def validate_http_url(url: str) -> str:
    """Validate that a URL uses HTTP(S) with a valid network host."""
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Unsupported or invalid HTTP(S) URL: {url!r}")
    return cleaned


def normalize_apple_podcast_id(raw_value: str) -> str:
    """Extract numeric Apple Podcasts ID from an ID string or Apple Podcasts URL."""
    cleaned = str(raw_value).strip()
    if cleaned.isdigit():
        return cleaned
    match = _APPLE_ID_RE.search(cleaned)
    if not match:
        raise ValueError(f"Invalid Apple Podcasts ID or URL: {raw_value!r}")
    return match.group(1)


def decode_xml_bytes(xml_payload: str | bytes) -> str:
    """Decode raw XML bytes respecting declared XML encoding when present."""
    if isinstance(xml_payload, str):
        return xml_payload.lstrip("\ufeff")
    head = xml_payload[:256].decode("ascii", errors="ignore")
    enc_match = _XML_ENCODING_RE.search(head)
    encoding = enc_match.group(1) if enc_match else "utf-8"
    try:
        text = xml_payload.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        text = xml_payload.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def parse_xml_safely(xml_payload: str | bytes) -> ET.Element:
    """Parse XML while strictly rejecting DTD and ENTITY declarations (billion-laughs guard)."""
    xml_text = decode_xml_bytes(xml_payload)
    stripped_no_cdata = _CDATA_RE.sub("", xml_text)
    if _UNSAFE_DTD_RE.search(stripped_no_cdata):
        raise ValueError("Unsafe XML rejected: DTD and ENTITY declarations are disallowed.")
    return ET.fromstring(xml_text)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1].lower()
    return tag.lower()


def _child_text(parent: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in parent:
        if _local_name(child.tag) in wanted:
            txt = "".join(child.itertext()).strip()
            if txt:
                return txt
    return ""


def _parse_iso_pubdate(raw_date: str) -> str | None:
    if not raw_date:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw_date)
        return dt.isoformat()
    except (TypeError, ValueError):
        return raw_date


def parse_timestamp_seconds(raw_ts: str | int | float | None) -> float | None:
    """Convert numeric seconds or HH:MM:SS.mmm / MM:SS.mmm timestamps into seconds."""
    if raw_ts is None or isinstance(raw_ts, bool):
        return None
    if isinstance(raw_ts, (int, float)):
        val = float(raw_ts)
        return round(val, 3) if math.isfinite(val) and val >= 0.0 else None

    text = str(raw_ts).strip()
    if not text:
        return None
    if text.endswith("s"):
        text = text[:-1].strip()
    try:
        val = float(text)
        return round(val, 3) if math.isfinite(val) and val >= 0.0 else None
    except ValueError:
        pass

    normalized = text.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if any(not math.isfinite(n) or n < 0.0 for n in nums):
        return None
    if len(nums) == 2:
        total = nums[0] * 60.0 + nums[1]
    else:
        total = nums[0] * 3600.0 + nums[1] * 60.0 + nums[2]
    return round(total, 3)


def detect_transcript_format(
    content: str,
    mime_type: str | None = None,
    url: str | None = None,
) -> str:
    """Identify transcript format ('json', 'vtt', 'srt', or 'txt') from MIME, URL, or content."""
    mime = (mime_type or "").lower()
    if "json" in mime:
        return "json"
    if "vtt" in mime:
        return "vtt"
    if "srt" in mime or "subrip" in mime:
        return "srt"

    if url:
        path = urlparse(url).path.lower()
        if path.endswith(".json"):
            return "json"
        if path.endswith(".vtt"):
            return "vtt"
        if path.endswith(".srt"):
            return "srt"
        if path.endswith(".txt"):
            return "txt"

    head = content.lstrip("\ufeff \t\r\n")
    if head.upper().startswith("WEBVTT"):
        return "vtt"
    if head.startswith("{") or head.startswith("["):
        try:
            json.loads(content)
            return "json"
        except json.JSONDecodeError:
            pass
    if "-->" in content[:2000]:
        return "srt"
    return "txt"


def _clean_cue_text(raw_lines: list[str]) -> tuple[str | None, str]:
    joined = " ".join(ln.strip() for ln in raw_lines if ln.strip())
    speaker: str | None = None
    vtt_match = _VTT_SPEAKER_RE.search(joined)
    if vtt_match:
        speaker = vtt_match.group(1).strip() or None
        joined = _VTT_SPEAKER_RE.sub(lambda m: m.group(2), joined)
    plain = _INLINE_TAG_RE.sub("", joined)
    plain = html.unescape(plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return speaker, plain


def parse_srt_transcript(content: str) -> list[dict[str, Any]]:
    """Parse SubRip (.srt) subtitles into normalized transcript segments."""
    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized.strip())
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        timing_idx = -1
        timing_match: re.Match[str] | None = None
        for idx, line in enumerate(lines[:2]):
            m = _TIMING_LINE_RE.match(line)
            if m:
                timing_idx = idx
                timing_match = m
                break
        if timing_match is None:
            continue
        start_sec = parse_timestamp_seconds(timing_match.group(1))
        end_sec = parse_timestamp_seconds(timing_match.group(2))
        speaker, text = _clean_cue_text(lines[timing_idx + 1 :])
        if text:
            segments.append(
                {
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "speaker": speaker,
                    "text": text,
                }
            )
    return segments


def parse_vtt_transcript(content: str) -> list[dict[str, Any]]:
    """Parse WebVTT (.vtt) subtitles into normalized transcript segments."""
    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized.strip())
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        head_upper = lines[0].strip().upper()
        if head_upper.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing_idx = -1
        timing_match: re.Match[str] | None = None
        for idx, line in enumerate(lines[:2]):
            m = _TIMING_LINE_RE.match(line)
            if m:
                timing_idx = idx
                timing_match = m
                break
        if timing_match is None:
            continue
        start_sec = parse_timestamp_seconds(timing_match.group(1))
        end_sec = parse_timestamp_seconds(timing_match.group(2))
        speaker, text = _clean_cue_text(lines[timing_idx + 1 :])
        if text:
            segments.append(
                {
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "speaker": speaker,
                    "text": text,
                }
            )
    return segments


def parse_json_transcript(content: str) -> list[dict[str, Any]]:
    """Parse Podcasting 2.0 JSON or Whisper-style transcript payloads into segments."""
    payload = json.loads(content.lstrip("\ufeff"))
    raw_segments: list[Any] = []
    if isinstance(payload, list):
        raw_segments = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("segments"), list):
            raw_segments = payload["segments"]
        elif isinstance(payload.get("cues"), list):
            raw_segments = payload["cues"]
        elif isinstance(payload.get("text"), str) and payload["text"].strip():
            return [
                {
                    "start_sec": None,
                    "end_sec": None,
                    "speaker": None,
                    "text": re.sub(r"\s+", " ", payload["text"]).strip(),
                }
            ]

    segments: list[dict[str, Any]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        raw_text = (
            item.get("body")
            or item.get("text")
            or item.get("transcript")
            or item.get("content")
            or ""
        )
        text = re.sub(r"\s+", " ", html.unescape(str(raw_text))).strip()
        if not text:
            continue
        raw_speaker = item.get("speaker") or item.get("speakerName")
        speaker = str(raw_speaker).strip() if raw_speaker else None
        start_val = item.get("startTime") if "startTime" in item else item.get("start")
        end_val = item.get("endTime") if "endTime" in item else item.get("end")
        segments.append(
            {
                "start_sec": parse_timestamp_seconds(start_val),
                "end_sec": parse_timestamp_seconds(end_val),
                "speaker": speaker or None,
                "text": text,
            }
        )
    return segments


def parse_txt_transcript(content: str) -> list[dict[str, Any]]:
    """Parse plain-text transcripts (with optional bracketed timestamps) into segments."""
    normalized = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    segments: list[dict[str, Any]] = []
    for line in normalized.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        ts_match = _TXT_TIMESTAMP_LINE_RE.match(cleaned)
        if ts_match:
            start_sec = parse_timestamp_seconds(ts_match.group(1))
            text = re.sub(r"\s+", " ", ts_match.group(2)).strip()
        else:
            start_sec = None
            text = re.sub(r"\s+", " ", cleaned).strip()
        if text:
            segments.append(
                {
                    "start_sec": start_sec,
                    "end_sec": None,
                    "speaker": None,
                    "text": text,
                }
            )
    return segments


def normalize_transcript(
    content: str,
    mime_type: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Parse and normalize SRT, VTT, JSON, or TXT transcripts into segments and full text."""
    fmt = detect_transcript_format(content, mime_type=mime_type, url=url)
    if fmt == "json":
        segments = parse_json_transcript(content)
    elif fmt == "vtt":
        segments = parse_vtt_transcript(content)
    elif fmt == "srt":
        segments = parse_srt_transcript(content)
    else:
        segments = parse_txt_transcript(content)

    full_transcript = " ".join(seg["text"] for seg in segments if seg.get("text"))
    full_transcript = re.sub(r"\s+", " ", full_transcript).strip()
    return {
        "format": fmt,
        "segment_count": len(segments),
        "segments": segments,
        "full_transcript": full_transcript,
    }


def parse_chapters_json(content: str) -> list[dict[str, Any]]:
    """Parse Podcasting 2.0 JSON chapters into normalized chapter objects."""
    payload = json.loads(content.lstrip("\ufeff"))
    raw_chapters = payload.get("chapters", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_chapters, list):
        return []

    chapters: list[dict[str, Any]] = []
    for ch in raw_chapters:
        if not isinstance(ch, dict):
            continue
        title = str(ch.get("title") or "").strip()
        start_sec = parse_timestamp_seconds(ch.get("startTime"))
        if not title and start_sec is None:
            continue
        chapters.append(
            {
                "start_sec": start_sec,
                "title": title,
                "url": str(ch.get("url")).strip() if ch.get("url") else None,
                "img": str(ch.get("img")).strip() if ch.get("img") else None,
            }
        )
    return chapters


def _extract_channel_metadata(channel: ET.Element, feed_url: str) -> dict[str, Any]:
    image_url = ""
    for child in channel:
        lname = _local_name(child.tag)
        if lname == "image":
            href = (child.attrib.get("href") or "").strip()
            if href:
                image_url = urljoin(feed_url, href)
                break
            nested_url = _child_text(child, "url")
            if nested_url:
                image_url = urljoin(feed_url, nested_url)
                break

    return {
        "feed_url": feed_url,
        "podcast_title": _child_text(channel, "title"),
        "podcast_link": _child_text(channel, "link"),
        "podcast_description": strip_html_to_text(_child_text(channel, "description", "summary")),
        "podcast_language": _child_text(channel, "language"),
        "podcast_author": _child_text(channel, "author", "managingeditor"),
        "podcast_image": image_url or None,
    }


def _extract_episode_from_item(
    item: ET.Element,
    channel_meta: dict[str, Any],
    feed_url: str,
) -> dict[str, Any]:
    raw_encoded = _child_text(item, "encoded")
    raw_desc = _child_text(item, "description")
    raw_summary = _child_text(item, "summary")
    best_notes = max((raw_encoded, raw_desc, raw_summary), key=len)

    audio_info: dict[str, Any] | None = None
    transcript_candidates: list[dict[str, Any]] = []
    chapters_info: dict[str, Any] | None = None

    for child in item:
        lname = _local_name(child.tag)
        if lname == "enclosure" and audio_info is None:
            enc_url = (child.attrib.get("url") or "").strip()
            if enc_url:
                raw_len = (child.attrib.get("length") or "").strip()
                length_bytes = int(raw_len) if raw_len.isdigit() else None
                audio_info = {
                    "url": urljoin(feed_url, enc_url),
                    "type": (child.attrib.get("type") or "").strip() or None,
                    "length_bytes": length_bytes,
                }
        elif lname == "transcript":
            t_url = (child.attrib.get("url") or "").strip()
            if t_url:
                t_type = (child.attrib.get("type") or "").strip() or None
                resolved_url = urljoin(feed_url, t_url)
                inferred_fmt = detect_transcript_format("", mime_type=t_type, url=resolved_url)
                transcript_candidates.append(
                    {
                        "url": resolved_url,
                        "type": t_type,
                        "language": (child.attrib.get("language") or "").strip() or None,
                        "rel": (child.attrib.get("rel") or "").strip() or None,
                        "priority": _TRANSCRIPT_FORMAT_PRIORITY.get(inferred_fmt, 99),
                    }
                )
        elif lname == "chapters" and chapters_info is None:
            c_url = (child.attrib.get("url") or "").strip()
            if c_url:
                chapters_info = {
                    "url": urljoin(feed_url, c_url),
                    "type": (child.attrib.get("type") or "").strip() or None,
                }

    transcript_candidates.sort(key=lambda item_cfg: item_cfg["priority"])
    for cand in transcript_candidates:
        cand.pop("priority", None)

    pub_raw = _child_text(item, "pubdate", "published", "updated")
    ep_num = _child_text(item, "episode")
    season_num = _child_text(item, "season")

    return {
        **channel_meta,
        "episode_title": _child_text(item, "title"),
        "episode_guid": _child_text(item, "guid", "id") or None,
        "episode_link": _child_text(item, "link") or None,
        "pub_date": pub_raw or None,
        "pub_date_iso": _parse_iso_pubdate(pub_raw),
        "author": _child_text(item, "author", "creator") or channel_meta.get("podcast_author") or None,
        "episode_number": int(ep_num) if ep_num.isdigit() else (ep_num or None),
        "season_number": int(season_num) if season_num.isdigit() else (season_num or None),
        "duration": _child_text(item, "duration") or None,
        "explicit": _child_text(item, "explicit") or None,
        "show_notes": strip_html_to_text(best_notes),
        "audio": audio_info,
        "transcript_candidates": transcript_candidates,
        "chapters_url": chapters_info["url"] if chapters_info else None,
        "chapters_type": chapters_info["type"] if chapters_info else None,
    }


def parse_podcast_rss_xml(
    xml_payload: str | bytes,
    feed_url: str,
    max_episodes: int = 10,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Safely parse a podcast RSS XML feed into channel metadata and episode skeletons."""
    root = parse_xml_safely(xml_payload)
    channel: ET.Element | None = None
    if _local_name(root.tag) == "channel":
        channel = root
    else:
        for child in root:
            if _local_name(child.tag) == "channel":
                channel = child
                break
    if channel is None:
        raise ValueError(f"RSS <channel> element not found in feed: {feed_url}")

    channel_meta = _extract_channel_metadata(channel, feed_url=feed_url)
    episodes: list[dict[str, Any]] = []
    for child in channel:
        if _local_name(child.tag) == "item":
            episodes.append(_extract_episode_from_item(child, channel_meta, feed_url))
            if len(episodes) >= max_episodes:
                break
    return channel_meta, episodes


def resolve_feed_sources(
    client: httpx.Client,
    apple_ids: list[str],
    search_queries: list[str],
    rss_urls: list[str],
    country: str = "US",
    search_limit: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve Apple Podcast IDs, iTunes search terms, and RSS URLs into unique feed specs."""
    resolved: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def _add_feed(feed_url: str, source_type: str, source_query: str, itunes_meta: dict[str, Any] | None = None) -> None:
        cleaned = validate_http_url(feed_url)
        if cleaned in seen_urls:
            return
        seen_urls.add(cleaned)
        resolved.append(
            {
                "feed_url": cleaned,
                "source_type": source_type,
                "source_query": source_query,
                "itunes_track_id": itunes_meta.get("trackId") if itunes_meta else None,
                "itunes_collection_name": itunes_meta.get("collectionName") if itunes_meta else None,
            }
        )

    for raw_id in apple_ids:
        try:
            pid = normalize_apple_podcast_id(raw_id)
            resp = client.get(
                ITUNES_LOOKUP_URL,
                params={"id": pid, "entity": "podcast", "country": country},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            matched = next((r for r in results if isinstance(r, dict) and r.get("feedUrl")), None)
            if not matched:
                errors.append({"source": raw_id, "stage": "itunes_lookup", "error": "No feedUrl returned by iTunes Lookup."})
                continue
            _add_feed(str(matched["feedUrl"]), "apple_id", str(raw_id), matched)
        except Exception as exc:
            errors.append({"source": raw_id, "stage": "itunes_lookup", "error": str(exc)})

    for query in search_queries:
        cleaned_query = query.strip()
        if not cleaned_query:
            continue
        try:
            resp = client.get(
                ITUNES_SEARCH_URL,
                params={
                    "term": cleaned_query,
                    "media": "podcast",
                    "limit": search_limit,
                    "country": country,
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            feed_hits = [r for r in results if isinstance(r, dict) and r.get("feedUrl")]
            if not feed_hits:
                errors.append({"source": cleaned_query, "stage": "itunes_search", "error": "No podcast feedUrl hits returned."})
                continue
            for item in feed_hits[:search_limit]:
                _add_feed(str(item["feedUrl"]), "itunes_search", cleaned_query, item)
        except Exception as exc:
            errors.append({"source": cleaned_query, "stage": "itunes_search", "error": str(exc)})

    for raw_url in rss_urls:
        try:
            _add_feed(str(raw_url), "rss_url", str(raw_url))
        except Exception as exc:
            errors.append({"source": raw_url, "stage": "rss_url_validation", "error": str(exc)})

    return resolved, errors


def _populate_episode_transcript(
    client: httpx.Client,
    episode: dict[str, Any],
    fetch_transcripts: bool,
    include_segments: bool,
) -> None:
    candidates = episode.get("transcript_candidates") or []
    if not candidates:
        episode["transcript_status"] = "not_provided_in_rss"
        episode["transcript_url"] = None
        episode["transcript_type"] = None
        episode["transcript_language"] = None
        episode["transcript_format"] = None
        episode["transcript_segment_count"] = 0
        episode["full_transcript"] = ""
        if include_segments:
            episode["transcript_segments"] = []
        return

    if not fetch_transcripts:
        primary = candidates[0]
        episode["transcript_status"] = "skipped_by_config"
        episode["transcript_url"] = primary["url"]
        episode["transcript_type"] = primary.get("type")
        episode["transcript_language"] = primary.get("language")
        episode["transcript_format"] = None
        episode["transcript_segment_count"] = 0
        episode["full_transcript"] = ""
        if include_segments:
            episode["transcript_segments"] = []
        return

    last_err: str | None = None
    for cand in candidates:
        try:
            t_url = validate_http_url(cand["url"])
            resp = client.get(t_url)
            resp.raise_for_status()
            norm = normalize_transcript(
                resp.text,
                mime_type=cand.get("type") or resp.headers.get("content-type"),
                url=t_url,
            )
            episode["transcript_status"] = "extracted"
            episode["transcript_url"] = t_url
            episode["transcript_type"] = cand.get("type")
            episode["transcript_language"] = cand.get("language")
            episode["transcript_format"] = norm["format"]
            episode["transcript_segment_count"] = norm["segment_count"]
            episode["full_transcript"] = norm["full_transcript"]
            if include_segments:
                episode["transcript_segments"] = norm["segments"]
            return
        except Exception as exc:
            last_err = f"{cand['url']}: {exc}"

    episode["transcript_status"] = "fetch_failed"
    episode["transcript_error"] = last_err
    episode["transcript_url"] = candidates[0]["url"]
    episode["transcript_type"] = candidates[0].get("type")
    episode["transcript_language"] = candidates[0].get("language")
    episode["transcript_format"] = None
    episode["transcript_segment_count"] = 0
    episode["full_transcript"] = ""
    if include_segments:
        episode["transcript_segments"] = []


def _populate_episode_chapters(
    client: httpx.Client,
    episode: dict[str, Any],
    fetch_chapters: bool,
) -> None:
    chapters_url = episode.get("chapters_url")
    if not chapters_url:
        episode["chapters_status"] = "not_provided_in_rss"
        episode["chapters"] = []
        return
    if not fetch_chapters:
        episode["chapters_status"] = "skipped_by_config"
        episode["chapters"] = []
        return
    try:
        validated = validate_http_url(chapters_url)
        resp = client.get(validated)
        resp.raise_for_status()
        episode["chapters"] = parse_chapters_json(resp.text)
        episode["chapters_status"] = "extracted"
    except Exception as exc:
        episode["chapters"] = []
        episode["chapters_status"] = "fetch_failed"
        episode["chapters_error"] = str(exc)


def extract_podcast_episodes(
    apple_podcast_ids: list[str] | None = None,
    search_queries: list[str] | None = None,
    rss_urls: list[str] | None = None,
    max_episodes_per_feed: int = 10,
    search_limit_per_query: int = 3,
    country: str = "US",
    fetch_transcripts: bool = True,
    fetch_chapters: bool = True,
    include_transcript_segments: bool = True,
    timeout_sec: float = 20.0,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve podcast feeds, parse RSS XML safely, and enrich episodes with transcripts & chapters."""
    apple_ids = [str(x) for x in (apple_podcast_ids or []) if str(x).strip()]
    queries = [str(x) for x in (search_queries or []) if str(x).strip()]
    urls = [str(x) for x in (rss_urls or []) if str(x).strip()]
    if not (apple_ids or queries or urls):
        return [], []

    owns_client = client is None
    active_client = client or httpx.Client(
        timeout=timeout_sec,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        feeds, res_errors = resolve_feed_sources(
            active_client,
            apple_ids=apple_ids,
            search_queries=queries,
            rss_urls=urls,
            country=country,
            search_limit=search_limit_per_query,
        )
        errors.extend(res_errors)

        for feed_spec in feeds:
            feed_url = feed_spec["feed_url"]
            try:
                resp = active_client.get(feed_url)
                resp.raise_for_status()
                _, episodes = parse_podcast_rss_xml(
                    resp.content,
                    feed_url=feed_url,
                    max_episodes=max_episodes_per_feed,
                )
            except Exception as exc:
                errors.append({"source": feed_url, "stage": "rss_fetch_or_parse", "error": str(exc)})
                continue

            for ep in episodes:
                ep["source_type"] = feed_spec["source_type"]
                ep["source_query"] = feed_spec["source_query"]
                ep["itunes_track_id"] = feed_spec["itunes_track_id"]
                _populate_episode_transcript(
                    active_client,
                    ep,
                    fetch_transcripts=fetch_transcripts,
                    include_segments=include_transcript_segments,
                )
                _populate_episode_chapters(
                    active_client,
                    ep,
                    fetch_chapters=fetch_chapters,
                )
                records.append(ep)
    finally:
        if owns_client:
            active_client.close()

    return records, errors


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The 'apify' package is required to run the Actor entrypoint.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        apple_ids = actor_input.get("applePodcastIds") or []
        search_queries = actor_input.get("searchQueries") or []
        rss_urls = actor_input.get("rssUrls") or []

        if not (apple_ids or search_queries or rss_urls):
            raise ValueError(
                "Provide at least one of 'applePodcastIds', 'searchQueries', or 'rssUrls'."
            )

        max_episodes = max(1, min(int(actor_input.get("maxEpisodesPerFeed", 10)), 500))
        search_limit = max(1, min(int(actor_input.get("searchLimitPerQuery", 3)), 25))
        country = str(actor_input.get("country", "US")).strip() or "US"
        fetch_transcripts = bool(actor_input.get("fetchTranscripts", True))
        fetch_chapters = bool(actor_input.get("fetchChapters", True))
        include_segments = bool(actor_input.get("includeTranscriptSegments", True))

        records, errors = await asyncio.to_thread(
            extract_podcast_episodes,
            apple_podcast_ids=[str(x) for x in apple_ids],
            search_queries=[str(x) for x in search_queries],
            rss_urls=[str(x) for x in rss_urls],
            max_episodes_per_feed=max_episodes,
            search_limit_per_query=search_limit,
            country=country,
            fetch_transcripts=fetch_transcripts,
            fetch_chapters=fetch_chapters,
            include_transcript_segments=include_segments,
        )

        for err in errors:
            Actor.log.warning(f"Feed warning ({err.get('stage')}): {err.get('source')} -> {err.get('error')}")

        if not records and errors:
            raise RuntimeError(f"All requested podcast sources failed: {errors}")

        for record in records:
            await Actor.push_data(record)
            await Actor.charge(event_name="episode_extracted", count=1)


if __name__ == "__main__":
    asyncio.run(main())
