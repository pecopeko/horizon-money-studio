"""Zero-dependency binary C2PA & ISO/IEC 19566-5 JUMBF container inspector (Python 3.11+).

Inspects real byte streams across:
- PNG (`caBX` chunk + CRC-32 verification + `eXIf`/`tEXt`/`iTXt` stripping awareness)
- JPEG (`APP11` `0xFFEB` JPEG XT ISO/IEC 19566-5 JUMBF segments with multi-packet `En`/`Z` reassembly)
- WebP (`RIFF....WEBP` little-endian `C2PA` chunk wrapping big-endian JUMBF superboxes)
- MP4 / ISOBMFF (`uuid` box `d8fec3d6-1b0e-483c-9297-5828877ec481` + `ftyp`/`moov`/`mdat`)
- Standalone `.c2pa` / `.jumbf` sidecar byte streams (`jumb`/`jumd` boxes)

Extracts JUMBF `jumb`/`jumd` labels (`c2pa`, `c2pa.assertions`, `c2pa.actions`, `c2pa.claim`,
`c2pa.signature`), IPTC `digitalSourceType` URIs, claim generator identifiers, COSE signature
presence, and SHA-256 digests (`Content-Digest` RFC 9530 ready).
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
import struct
from typing import Any
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"
C2PA_ISOBMFF_UUID_BYTES = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")
C2PA_ISOBMFF_UUID_HEX = "d8fec3d6-1b0e-483c-9297-5828877ec481"

# ISO/IEC 19566-5 / C2PA JUMBF content-type UUIDs
UUID_C2PA_STORE = bytes.fromhex("6332706100110010800000aa00389b71")
UUID_C2PA_MANIFEST = bytes.fromhex("63326d6100110010800000aa00389b71")
UUID_C2PA_ASSERTIONS = bytes.fromhex("6332617300110010800000aa00389b71")
UUID_C2PA_CLAIM = bytes.fromhex("6332636c00110010800000aa00389b71")
UUID_C2PA_SIGNATURE = bytes.fromhex("6332637300110010800000aa00389b71")
UUID_JUMBF_JSON = bytes.fromhex("6a736f6e00110010800000aa00389b71")
UUID_JUMBF_CBOR = bytes.fromhex("63626f7200110010800000aa00389b71")

C2PA_STORE_UUID_STR = "63327061-0011-0010-8000-00aa00389b71"
C2PA_SIGNATURE_UUID_STR = "63326373-0011-0010-8000-00aa00389b71"

IPTC_URI_PREFIX_HTTP = "http://cv.iptc.org/newscodes/digitalsourcetype/"
IPTC_URI_PREFIX_HTTPS = "https://cv.iptc.org/newscodes/digitalsourcetype/"

IPTC_AI_SOURCE_CODES: frozenset[str] = frozenset(
    {
        "trainedAlgorithmicMedia",
        "compositeWithTrainedAlgorithmicMedia",
        "algorithmicMedia",
        "trainedAlgorithmicData",
        "compositeSynthetic",
        "virtualRecording",
    }
)

IPTC_CAPTURE_SOURCE_CODES: frozenset[str] = frozenset(
    {
        "digitalCapture",
        "negativeFilm",
        "positiveFilm",
        "print",
        "humanEdits",
        "minorHumanEdits",
        "compositeCapture",
    }
)

_ISOBMFF_TOP_TYPES: frozenset[str] = frozenset(
    {
        "ftyp",
        "styp",
        "moov",
        "mdat",
        "free",
        "skip",
        "wide",
        "uuid",
        "meta",
        "moof",
        "sidx",
        "emsg",
    }
)

_IPTC_URI_RE = re.compile(
    r"https?://cv\.iptc\.org/newscodes/digitalsourcetype/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_BARE_DST_RE = re.compile(
    r'"?digitalSourceType"?\s*[:=]\s*"([A-Za-z0-9_:/.-]+)"',
    re.IGNORECASE,
)
_CLAIM_GEN_RE = re.compile(
    r'"?(?:claim_generator|softwareAgent)"?\s*[:=]\s*"([^"\x00-\x1f]{2,120})"',
    re.IGNORECASE,
)
_PRINTABLE_TOKEN_RE = re.compile(
    rb"((?:OpenAI|Adobe_Firefly|Firefly|Midjourney|Google|Stability|Leica|Sony|Canon|Nikon|C2PAGATE|c2pa-rs|c2patool)[A-Za-z0-9_./ -]{1,80})"
)

# Deterministic 1x1 RGB (#f2f4f7) zlib scanline shared with JS engine for byte-exact parity.
_PNG_1X1_IDAT_ZLIB = bytes.fromhex("78da63f8f4e53b0005b902de")


def _format_uuid_bytes(raw16: bytes) -> str:
    h = raw16.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _safe_fourcc(raw4: bytes) -> str:
    chars: list[str] = []
    for b in raw4:
        if 32 <= b <= 126:
            chars.append(chr(b))
        else:
            chars.append(f"\\x{b:02x}")
    return "".join(chars)


def _is_printable_fourcc(raw4: bytes) -> bool:
    return len(raw4) == 4 and all(32 <= b <= 126 for b in raw4)


@dataclass(frozen=True)
class ContainerSegment:
    """Single parsed chunk, marker segment, or BMFF box within a binary media stream."""

    kind: str
    offset: int
    length: int
    is_c2pa: bool = False
    crc_valid: bool | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JumbfParseResult:
    """Extracted metadata from one or more ISO/IEC 19566-5 JUMBF superboxes."""

    boxes: list[dict[str, Any]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    uuids: list[str] = field(default_factory=list)
    digital_source_types: list[str] = field(default_factory=list)
    canonical_iptc_uris: list[str] = field(default_factory=list)
    claim_generators: list[str] = field(default_factory=list)
    has_c2pa_manifest_store: bool = False
    has_assertions: bool = False
    has_actions: bool = False
    has_claim: bool = False
    has_signature: bool = False
    signature_byte_length: int = 0
    signature_hex_preview: str = ""
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class ContainerInspection:
    """Complete zero-dependency binary C2PA inspection output."""

    container_format: str
    mime_type: str
    byte_length: int
    sha256_hex: str
    content_digest_header: str
    c2pa_carrier: str | None
    c2pa_present: bool
    has_manifest_store: bool
    has_assertions: bool
    has_actions: bool
    has_claim: bool
    has_signature: bool
    signature_byte_length: int
    signature_hex_preview: str
    jumbf_labels: list[str]
    jumbf_boxes: list[dict[str, Any]]
    digital_source_types: list[str]
    canonical_iptc_uris: list[str]
    iptc_source_codes: list[str]
    ai_source_type_detected: bool
    non_ai_capture_asserted: bool
    claim_generators: list[str]
    legacy_metadata_present: bool
    probable_metadata_stripped: bool
    crc_errors: list[str]
    parse_warnings: list[str]
    segments: list[ContainerSegment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_format": self.container_format,
            "mime_type": self.mime_type,
            "byte_length": self.byte_length,
            "sha256_hex": self.sha256_hex,
            "content_digest_header": self.content_digest_header,
            "c2pa_carrier": self.c2pa_carrier,
            "c2pa_present": self.c2pa_present,
            "has_manifest_store": self.has_manifest_store,
            "has_assertions": self.has_assertions,
            "has_actions": self.has_actions,
            "has_claim": self.has_claim,
            "has_signature": self.has_signature,
            "signature_byte_length": self.signature_byte_length,
            "signature_hex_preview": self.signature_hex_preview,
            "jumbf_labels": list(self.jumbf_labels),
            "jumbf_boxes": list(self.jumbf_boxes),
            "digital_source_types": list(self.digital_source_types),
            "canonical_iptc_uris": list(self.canonical_iptc_uris),
            "iptc_source_codes": list(self.iptc_source_codes),
            "ai_source_type_detected": self.ai_source_type_detected,
            "non_ai_capture_asserted": self.non_ai_capture_asserted,
            "claim_generators": list(self.claim_generators),
            "legacy_metadata_present": self.legacy_metadata_present,
            "probable_metadata_stripped": self.probable_metadata_stripped,
            "crc_errors": list(self.crc_errors),
            "parse_warnings": list(self.parse_warnings),
            "segments": [s.to_dict() for s in self.segments],
        }


def _append_unique(target: list[str], value: str) -> None:
    cleaned = value.strip()
    if cleaned and cleaned not in target:
        target.append(cleaned)


def _extract_iptc_code(uri_or_code: str) -> str:
    val = uri_or_code.strip()
    m = _IPTC_URI_RE.search(val)
    if m:
        return m.group(1)
    if "/" in val:
        return val.rsplit("/", 1)[-1]
    return val


def _scan_payload_metadata(payload: bytes, out: JumbfParseResult) -> None:
    if not payload:
        return
    # Decode tolerant UTF-8 view to capture both JSON assertions and CBOR text strings
    text = payload.decode("utf-8", errors="ignore")

    for m in _IPTC_URI_RE.finditer(text):
        full_uri = m.group(0)
        _append_unique(out.digital_source_types, full_uri)
        _append_unique(out.canonical_iptc_uris, full_uri)

    # Try structured JSON parse when payload begins with '{' or '['
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            _walk_json_metadata(parsed, out)
        except json.JSONDecodeError:
            pass

    for m in _BARE_DST_RE.finditer(text):
        candidate = m.group(1).strip()
        if candidate:
            _append_unique(out.digital_source_types, candidate)
            if _IPTC_URI_RE.match(candidate):
                _append_unique(out.canonical_iptc_uris, candidate)

    for m in _CLAIM_GEN_RE.finditer(text):
        _append_unique(out.claim_generators, m.group(1))

    for m in _PRINTABLE_TOKEN_RE.finditer(payload):
        tok = m.group(1).decode("ascii", errors="ignore").strip()
        if tok:
            _append_unique(out.claim_generators, tok)


def _walk_json_metadata(node: Any, out: JumbfParseResult) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            key_low = str(k).lower()
            if key_low in ("digitalsourcetype", "digital_source_type") and isinstance(v, str):
                _append_unique(out.digital_source_types, v)
                if _IPTC_URI_RE.match(v.strip()):
                    _append_unique(out.canonical_iptc_uris, v.strip())
            elif key_low in ("claim_generator", "softwareagent") and isinstance(v, str):
                _append_unique(out.claim_generators, v)
            elif key_low == "claim_generator_info":
                if isinstance(v, dict) and isinstance(v.get("name"), str):
                    ver = str(v.get("version") or "").strip()
                    gen_label = f"{v['name']}/{ver}" if ver else v["name"]
                    _append_unique(out.claim_generators, gen_label)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and isinstance(item.get("name"), str):
                            ver = str(item.get("version") or "").strip()
                            gen_label = f"{item['name']}/{ver}" if ver else item["name"]
                            _append_unique(out.claim_generators, gen_label)
            else:
                _walk_json_metadata(v, out)
    elif isinstance(node, list):
        for elem in node:
            _walk_json_metadata(elem, out)


def parse_jumbf_boxes(
    buf: bytes,
    *,
    base_offset: int = 0,
    depth: int = 0,
    result: JumbfParseResult | None = None,
) -> JumbfParseResult:
    """Recursively parse ISO/IEC 19566-5 JUMBF (`jumb`/`jumd` and content) boxes."""
    out = result if result is not None else JumbfParseResult()
    if depth > 12:
        out.parse_warnings.append("Maximum JUMBF nesting depth (12) exceeded.")
        return out

    pos = 0
    total = len(buf)
    while pos + 8 <= total:
        lbox = struct.unpack_from(">I", buf, pos)[0]
        tbox_raw = buf[pos + 4 : pos + 8]
        if not _is_printable_fourcc(tbox_raw):
            break
        tbox = tbox_raw.decode("ascii")
        header_len = 8

        if lbox == 1:
            if pos + 16 > total:
                out.parse_warnings.append(f"Truncated 64-bit XLBox header at offset {base_offset + pos}.")
                break
            box_size = struct.unpack_from(">Q", buf, pos + 8)[0]
            header_len = 16
        elif lbox == 0:
            box_size = total - pos
        else:
            box_size = lbox

        if box_size < header_len:
            out.parse_warnings.append(f"Invalid BMFF/JUMBF box size {box_size} for '{tbox}' at {base_offset + pos}.")
            break
        if pos + box_size > total:
            out.parse_warnings.append(
                f"Truncated JUMBF box '{tbox}' at offset {base_offset + pos} (declared {box_size}B, available {total - pos}B)."
            )
            box_end = total
        else:
            box_end = pos + box_size

        payload = buf[pos + header_len : box_end]

        if tbox == "jumb":
            box_uuid = ""
            box_label = ""
            # Inspect immediate jumd description child if present
            if len(payload) >= 8 and payload[4:8] == b"jumd":
                jumd_len = struct.unpack_from(">I", payload, 0)[0]
                if 25 <= jumd_len <= len(payload):
                    raw_uuid = payload[8:24]
                    box_uuid = _format_uuid_bytes(raw_uuid)
                    _append_unique(out.uuids, box_uuid)
                    toggles = payload[24]
                    cursor = 25
                    if toggles & 0x02:
                        nul_idx = payload.find(b"\x00", cursor, jumd_len)
                        if nul_idx != -1:
                            box_label = payload[cursor:nul_idx].decode("utf-8", errors="replace")
                            cursor = nul_idx + 1
                        else:
                            box_label = payload[cursor:jumd_len].decode("utf-8", errors="replace")
                            cursor = jumd_len
                    if box_label:
                        _append_unique(out.labels, box_label)

            low_label = box_label.lower()
            if low_label == "c2pa" or box_uuid == C2PA_STORE_UUID_STR:
                out.has_c2pa_manifest_store = True
            if low_label.startswith("c2pa.assertions"):
                out.has_assertions = True
            if low_label.startswith("c2pa.actions"):
                out.has_actions = True
            if low_label.startswith("c2pa.claim"):
                out.has_claim = True
            if low_label.startswith("c2pa.signature") or box_uuid == C2PA_SIGNATURE_UUID_STR:
                # Verify child payload inside signature superbox is non-trivial
                sig_body = payload
                if len(payload) >= 8 and payload[4:8] == b"jumd":
                    jd_len = struct.unpack_from(">I", payload, 0)[0]
                    if jd_len <= len(payload):
                        sig_body = payload[jd_len:]
                # Strip nested box header if wrapped in c2cs/cbor/bfdb
                raw_sig = sig_body[8:] if len(sig_body) >= 8 and _is_printable_fourcc(sig_body[4:8]) else sig_body
                if len(raw_sig) >= 16:
                    out.has_signature = True
                    out.signature_byte_length = len(raw_sig)
                    if not out.signature_hex_preview:
                        out.signature_hex_preview = raw_sig[:16].hex()

            out.boxes.append(
                {
                    "box_type": "jumb",
                    "uuid": box_uuid,
                    "label": box_label,
                    "offset": base_offset + pos,
                    "length": box_end - pos,
                    "depth": depth,
                }
            )
            # Recurse into children inside `jumb`
            parse_jumbf_boxes(payload, base_offset=base_offset + pos + header_len, depth=depth + 1, result=out)
        elif tbox == "jumd":
            # Already recorded by parent `jumb`, or standalone `jumd`
            if depth == 0 and len(payload) >= 17:
                raw_uuid = payload[:16]
                box_uuid = _format_uuid_bytes(raw_uuid)
                _append_unique(out.uuids, box_uuid)
                toggles = payload[16]
                box_label = ""
                if toggles & 0x02:
                    nul_idx = payload.find(b"\x00", 17)
                    raw_lbl = payload[17:nul_idx] if nul_idx != -1 else payload[17:]
                    box_label = raw_lbl.decode("utf-8", errors="replace")
                    if box_label:
                        _append_unique(out.labels, box_label)
                out.boxes.append(
                    {
                        "box_type": "jumd",
                        "uuid": box_uuid,
                        "label": box_label,
                        "offset": base_offset + pos,
                        "length": box_end - pos,
                        "depth": depth,
                    }
                )
        else:
            out.boxes.append(
                {
                    "box_type": tbox,
                    "uuid": "",
                    "label": "",
                    "offset": base_offset + pos,
                    "length": box_end - pos,
                    "depth": depth,
                }
            )
            if tbox == "c2cs" and len(payload) >= 16:
                out.has_signature = True
                out.signature_byte_length = max(out.signature_byte_length, len(payload))
                if not out.signature_hex_preview:
                    out.signature_hex_preview = payload[:16].hex()
            _scan_payload_metadata(payload, out)

        pos = box_end

    return out


def _locate_jumbf_start_in_uuid_payload(uuid_payload: bytes) -> int | None:
    """Find the JUMBF `jumb` superbox inside an ISOBMFF C2PA `uuid` payload."""
    if len(uuid_payload) >= 8 and uuid_payload[4:8] == b"jumb":
        return 0
    # C2PA ISOBMFF v1/v2 FullBox header: 4B version/flags + null-terminated purpose ("manifest\0") + 8B merkle offset
    idx = uuid_payload.find(b"jumb")
    while idx != -1:
        if idx >= 4 and idx + 4 <= len(uuid_payload):
            declared = struct.unpack_from(">I", uuid_payload, idx - 4)[0]
            remaining = len(uuid_payload) - (idx - 4)
            if declared == 0 or declared == 1 or (8 <= declared <= remaining):
                return idx - 4
        idx = uuid_payload.find(b"jumb", idx + 4)
    return None


def inspect_media_bytes(data: bytes | bytearray | memoryview) -> ContainerInspection:
    """Inspect PNG, JPEG, WebP, MP4/ISOBMFF, or standalone JUMBF bytes for C2PA Content Credentials."""
    buf = bytes(data)
    byte_length = len(buf)
    digest_bytes = hashlib.sha256(buf).digest()
    sha256_hex = digest_bytes.hex()
    content_digest_header = "sha-256=:" + base64.b64encode(digest_bytes).decode("ascii") + ":"

    segments: list[ContainerSegment] = []
    crc_errors: list[str] = []
    jumbf_res = JumbfParseResult()
    container_format = "unknown"
    mime_type = "application/octet-stream"
    c2pa_carrier: str | None = None
    legacy_metadata_present = False
    has_c2pa_chunk = False

    if buf.startswith(PNG_SIGNATURE):
        container_format = "png"
        mime_type = "image/png"
        segments.append(ContainerSegment(kind="PNG_SIG", offset=0, length=8, detail="89 50 4E 47 0D 0A 1A 0A"))
        pos = 8
        while pos + 12 <= byte_length:
            chunk_len = struct.unpack_from(">I", buf, pos)[0]
            chunk_type_raw = buf[pos + 4 : pos + 8]
            chunk_type = _safe_fourcc(chunk_type_raw)
            total_chunk = 12 + chunk_len
            if pos + total_chunk > byte_length:
                jumbf_res.parse_warnings.append(
                    f"Truncated PNG chunk '{chunk_type}' at offset {pos} (declared {chunk_len}B data)."
                )
                segments.append(
                    ContainerSegment(
                        kind=chunk_type,
                        offset=pos,
                        length=byte_length - pos,
                        is_c2pa=(chunk_type == "caBX"),
                        crc_valid=False,
                        detail="truncated",
                    )
                )
                break

            chunk_data = buf[pos + 8 : pos + 8 + chunk_len]
            expected_crc = struct.unpack_from(">I", buf, pos + 8 + chunk_len)[0]
            computed_crc = zlib.crc32(buf[pos + 4 : pos + 8 + chunk_len]) & 0xFFFFFFFF
            crc_ok = expected_crc == computed_crc
            if not crc_ok:
                crc_errors.append(
                    f"PNG chunk '{chunk_type}' at offset {pos} failed CRC-32 (expected 0x{expected_crc:08x}, got 0x{computed_crc:08x})."
                )

            is_c2pa = chunk_type == "caBX"
            if chunk_type in ("eXIf", "tEXt", "iTXt", "zTXt"):
                legacy_metadata_present = True
            if is_c2pa:
                has_c2pa_chunk = True
                c2pa_carrier = "caBX"
                parse_jumbf_boxes(chunk_data, base_offset=pos + 8, result=jumbf_res)

            segments.append(
                ContainerSegment(
                    kind=chunk_type,
                    offset=pos,
                    length=total_chunk,
                    is_c2pa=is_c2pa,
                    crc_valid=crc_ok,
                    detail=f"data={chunk_len}B",
                )
            )
            pos += total_chunk
            if chunk_type == "IEND":
                break

    elif buf.startswith(JPEG_SOI):
        container_format = "jpeg"
        mime_type = "image/jpeg"
        segments.append(ContainerSegment(kind="SOI", offset=0, length=2, detail="0xFFD8"))
        pos = 2
        # Map of En -> list of (Z, offset_in_file, payload_slice) for multi-packet JPEG XT APP11 reassembly
        app11_packets: dict[int, list[tuple[int, int, bytes]]] = {}

        while pos + 2 <= byte_length:
            if buf[pos] != 0xFF:
                next_ff = buf.find(b"\xff", pos)
                if next_ff == -1:
                    break
                pos = next_ff
                continue

            # Skip fill 0xFF bytes
            marker_pos = pos
            while pos + 1 < byte_length and buf[pos + 1] == 0xFF:
                pos += 1
            if pos + 1 >= byte_length:
                break
            marker = buf[pos + 1]

            if marker == 0xD9:  # EOI
                segments.append(ContainerSegment(kind="EOI", offset=marker_pos, length=(pos + 2) - marker_pos, detail="0xFFD9"))
                break
            if marker == 0x00 or (0xD0 <= marker <= 0xD8) or marker == 0x01:
                pos += 2
                continue
            if pos + 4 > byte_length:
                jumbf_res.parse_warnings.append(f"Truncated JPEG marker 0xFF{marker:02X} at offset {marker_pos}.")
                break

            seg_len = struct.unpack_from(">H", buf, pos + 2)[0]
            if seg_len < 2 or pos + 2 + seg_len > byte_length:
                jumbf_res.parse_warnings.append(
                    f"Invalid or truncated JPEG marker 0xFF{marker:02X} length {seg_len} at offset {marker_pos}."
                )
                break

            seg_payload = buf[pos + 4 : pos + 2 + seg_len]
            total_seg_len = (pos + 2 + seg_len) - marker_pos

            if marker == 0xEB:  # APP11 (JPEG XT / JUMBF)
                has_c2pa_chunk = True
                c2pa_carrier = "APP11"
                if len(seg_payload) >= 8 and seg_payload[0:2] == b"JP":
                    en = struct.unpack_from(">H", seg_payload, 2)[0]
                    z_seq = struct.unpack_from(">I", seg_payload, 4)[0]
                    app11_packets.setdefault(en, []).append((z_seq, pos + 12, seg_payload[8:]))
                    detail = f"0xFFEB JP En={en} Z={z_seq}"
                else:
                    # Non-XT direct JUMBF fallback
                    parse_jumbf_boxes(seg_payload, base_offset=pos + 4, result=jumbf_res)
                    detail = "0xFFEB raw JUMBF"
                segments.append(
                    ContainerSegment(
                        kind="APP11",
                        offset=marker_pos,
                        length=total_seg_len,
                        is_c2pa=True,
                        detail=detail,
                    )
                )
            else:
                if marker == 0xE1 and (
                    seg_payload.startswith(b"Exif\x00\x00") or b"ns.adobe.com/xap" in seg_payload[:64]
                ):
                    legacy_metadata_present = True
                marker_name = f"APP{marker - 0xE0}" if 0xE0 <= marker <= 0xEF else (
                    "SOS" if marker == 0xDA else f"0xFF{marker:02X}"
                )
                segments.append(
                    ContainerSegment(
                        kind=marker_name,
                        offset=marker_pos,
                        length=total_seg_len,
                        is_c2pa=False,
                        detail=f"len={seg_len}B",
                    )
                )

            pos = pos + 2 + seg_len
            if marker == 0xDA:  # Start of Scan: entropy-coded image data follows until EOI
                eoi_pos = buf.rfind(b"\xff\xd9", pos)
                if eoi_pos != -1 and eoi_pos >= pos:
                    if eoi_pos > pos:
                        segments.append(
                            ContainerSegment(kind="SCAN", offset=pos, length=eoi_pos - pos, detail="entropy-coded scan")
                        )
                    segments.append(ContainerSegment(kind="EOI", offset=eoi_pos, length=2, detail="0xFFD9"))
                break

        for en in sorted(app11_packets.keys()):
            packets = sorted(app11_packets[en], key=lambda item: item[0])
            if len(packets) == 1:
                _, first_off, pkt_bytes = packets[0]
                parse_jumbf_boxes(pkt_bytes, base_offset=first_off, result=jumbf_res)
            else:
                # ISO/IEC 18477-3 / 19566-5: Z>1 packets may repeat the 8-byte LBox+TBox header; strip if repeated
                first_z, first_off, first_bytes = packets[0]
                combined = bytearray(first_bytes)
                first_header = first_bytes[:8] if len(first_bytes) >= 8 and first_bytes[4:8] == b"jumb" else b""
                for z_seq, _, pkt_bytes in packets[1:]:
                    if first_header and len(pkt_bytes) >= 8 and pkt_bytes[:8] == first_header:
                        combined.extend(pkt_bytes[8:])
                    else:
                        combined.extend(pkt_bytes)
                # Fix top-level LBox on reassembled superbox if needed
                if len(combined) >= 8 and combined[4:8] == b"jumb":
                    declared_lbox = struct.unpack_from(">I", combined, 0)[0]
                    if declared_lbox != 1 and declared_lbox != len(combined):
                        struct.pack_into(">I", combined, 0, len(combined))
                parse_jumbf_boxes(bytes(combined), base_offset=first_off, result=jumbf_res)

    elif byte_length >= 12 and buf[0:4] == b"RIFF" and buf[8:12] == b"WEBP":
        container_format = "webp"
        mime_type = "image/webp"
        riff_size = struct.unpack_from("<I", buf, 4)[0]
        segments.append(ContainerSegment(kind="RIFF_WEBP", offset=0, length=12, detail=f"riff_size={riff_size}B"))
        pos = 12
        while pos + 8 <= byte_length:
            fourcc = _safe_fourcc(buf[pos : pos + 4])
            chunk_size = struct.unpack_from("<I", buf, pos + 4)[0]
            data_end = pos + 8 + chunk_size
            padded_end = data_end + (chunk_size & 1)
            if data_end > byte_length:
                jumbf_res.parse_warnings.append(
                    f"Truncated WebP RIFF chunk '{fourcc}' at offset {pos} (declared {chunk_size}B)."
                )
                break

            chunk_data = buf[pos + 8 : data_end]
            is_c2pa = fourcc in ("C2PA", "caBX")
            if fourcc in ("EXIF", "XMP "):
                legacy_metadata_present = True
            if is_c2pa:
                has_c2pa_chunk = True
                c2pa_carrier = fourcc
                parse_jumbf_boxes(chunk_data, base_offset=pos + 8, result=jumbf_res)

            segments.append(
                ContainerSegment(
                    kind=fourcc,
                    offset=pos,
                    length=min(padded_end, byte_length) - pos,
                    is_c2pa=is_c2pa,
                    detail=f"data={chunk_size}B",
                )
            )
            pos = min(padded_end, byte_length)

    elif byte_length >= 8 and _is_printable_fourcc(buf[4:8]) and buf[4:8].decode("ascii") in _ISOBMFF_TOP_TYPES:
        container_format = "mp4"
        mime_type = "video/mp4"
        pos = 0
        while pos + 8 <= byte_length:
            size32 = struct.unpack_from(">I", buf, pos)[0]
            btype_raw = buf[pos + 4 : pos + 8]
            if not _is_printable_fourcc(btype_raw):
                break
            btype = btype_raw.decode("ascii")
            hdr_len = 8
            if size32 == 1:
                if pos + 16 > byte_length:
                    jumbf_res.parse_warnings.append(f"Truncated 64-bit ISOBMFF box '{btype}' at offset {pos}.")
                    break
                box_size = struct.unpack_from(">Q", buf, pos + 8)[0]
                hdr_len = 16
            elif size32 == 0:
                box_size = byte_length - pos
            else:
                box_size = size32

            if box_size < hdr_len:
                jumbf_res.parse_warnings.append(f"Invalid ISOBMFF box '{btype}' size {box_size} at offset {pos}.")
                break
            box_end = min(pos + box_size, byte_length)
            if pos + box_size > byte_length:
                jumbf_res.parse_warnings.append(
                    f"Truncated ISOBMFF box '{btype}' at offset {pos} (declared {box_size}B, available {byte_length - pos}B)."
                )

            payload = buf[pos + hdr_len : box_end]
            is_c2pa = False
            detail = f"size={box_end - pos}B"
            if btype == "uuid" and len(payload) >= 16:
                raw_uuid = payload[:16]
                uuid_str = _format_uuid_bytes(raw_uuid)
                detail = f"uuid={uuid_str}"
                if raw_uuid == C2PA_ISOBMFF_UUID_BYTES:
                    is_c2pa = True
                    has_c2pa_chunk = True
                    c2pa_carrier = "uuid"
                    uuid_inner = payload[16:]
                    jumb_rel = _locate_jumbf_start_in_uuid_payload(uuid_inner)
                    if jumb_rel is not None:
                        parse_jumbf_boxes(
                            uuid_inner[jumb_rel:],
                            base_offset=pos + hdr_len + 16 + jumb_rel,
                            result=jumbf_res,
                        )
                    else:
                        jumbf_res.parse_warnings.append(
                            "C2PA ISOBMFF uuid box present, but inner JUMBF 'jumb' box was not found."
                        )
            elif btype in ("meta", "udta"):
                legacy_metadata_present = True

            segments.append(
                ContainerSegment(
                    kind=btype,
                    offset=pos,
                    length=box_end - pos,
                    is_c2pa=is_c2pa,
                    detail=detail,
                )
            )
            pos = box_end

    elif byte_length >= 8 and buf[4:8] == b"jumb":
        container_format = "jumbf"
        mime_type = "application/x-c2pa-manifest-store"
        has_c2pa_chunk = True
        c2pa_carrier = "jumb"
        parse_jumbf_boxes(buf, base_offset=0, result=jumbf_res)
        segments.append(ContainerSegment(kind="jumb", offset=0, length=byte_length, is_c2pa=True, detail="standalone JUMBF"))
    else:
        jumbf_res.parse_warnings.append(
            "Unrecognized binary magic bytes (expected PNG, JPEG, WebP, MP4/ISOBMFF, or JUMBF stream)."
        )

    iptc_codes: list[str] = []
    for uri_or_code in jumbf_res.digital_source_types:
        code = _extract_iptc_code(uri_or_code)
        _append_unique(iptc_codes, code)

    ai_detected = any(code in IPTC_AI_SOURCE_CODES for code in iptc_codes)
    capture_asserted = any(code in IPTC_CAPTURE_SOURCE_CODES for code in iptc_codes)

    c2pa_present = bool(has_c2pa_chunk and (jumbf_res.has_c2pa_manifest_store or len(jumbf_res.labels) > 0))
    probable_stripped = bool(
        container_format in ("png", "jpeg", "webp", "mp4")
        and not c2pa_present
        and not legacy_metadata_present
    )

    return ContainerInspection(
        container_format=container_format,
        mime_type=mime_type,
        byte_length=byte_length,
        sha256_hex=sha256_hex,
        content_digest_header=content_digest_header,
        c2pa_carrier=c2pa_carrier,
        c2pa_present=c2pa_present,
        has_manifest_store=jumbf_res.has_c2pa_manifest_store,
        has_assertions=jumbf_res.has_assertions,
        has_actions=jumbf_res.has_actions,
        has_claim=jumbf_res.has_claim,
        has_signature=jumbf_res.has_signature,
        signature_byte_length=jumbf_res.signature_byte_length,
        signature_hex_preview=jumbf_res.signature_hex_preview,
        jumbf_labels=jumbf_res.labels,
        jumbf_boxes=jumbf_res.boxes,
        digital_source_types=jumbf_res.digital_source_types,
        canonical_iptc_uris=jumbf_res.canonical_iptc_uris,
        iptc_source_codes=iptc_codes,
        ai_source_type_detected=ai_detected,
        non_ai_capture_asserted=capture_asserted,
        claim_generators=jumbf_res.claim_generators,
        legacy_metadata_present=legacy_metadata_present,
        probable_metadata_stripped=probable_stripped,
        crc_errors=crc_errors,
        parse_warnings=jumbf_res.parse_warnings,
        segments=segments,
    )


# ---------------------------------------------------------------------------
# Deterministic Binary C2PA Container Synthesizers (Byte-Exact with JS Engine)
# ---------------------------------------------------------------------------


def _bmff_box(fourcc: str, payload: bytes) -> bytes:
    raw_type = fourcc.encode("ascii")
    if len(raw_type) != 4:
        raise ValueError(f"FourCC must be 4 ASCII chars, got {fourcc!r}")
    return struct.pack(">I", 8 + len(payload)) + raw_type + payload


def _jumbf_superbox(uuid16: bytes, label: str, children: list[bytes]) -> bytes:
    lbl_bytes = label.encode("utf-8") + b"\x00"
    # toggles = 0x03 (requestable + label_present)
    jumd_payload = uuid16 + b"\x03" + lbl_bytes
    jumd = _bmff_box("jumd", jumd_payload)
    return _bmff_box("jumb", jumd + b"".join(children))


def build_jumbf_c2pa_store(
    *,
    manifest_urn: str = "urn:uuid:2fc21dee-2026-4c50-9a50-c2pa00000050",
    digital_source_type: str = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    claim_generator: str = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    software_agent: str = "GenStudio-Diffusion/4.2",
    include_signature: bool = True,
    include_actions: bool = True,
) -> bytes:
    """Synthesize a spec-structured ISO/IEC 19566-5 C2PA v2.1 JUMBF Manifest Store byte buffer."""
    assertion_boxes: list[bytes] = []

    if include_actions:
        actions_doc: dict[str, Any] = {
            "actions": [
                {
                    "action": "c2pa.created",
                    "softwareAgent": software_agent,
                }
            ]
        }
        if digital_source_type:
            actions_doc["actions"][0]["digitalSourceType"] = digital_source_type
        actions_json = json.dumps(actions_doc, separators=(",", ":")).encode("utf-8")
        assertion_boxes.append(
            _jumbf_superbox(UUID_JUMBF_JSON, "c2pa.actions.v2", [_bmff_box("json", actions_json)])
        )

    creative_work_doc = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "author": [{"@type": "Organization", "name": "peco-compliance-lab"}],
    }
    cw_json = json.dumps(creative_work_doc, separators=(",", ":")).encode("utf-8")
    assertion_boxes.append(
        _jumbf_superbox(UUID_JUMBF_JSON, "stds.schema-org.CreativeWork", [_bmff_box("json", cw_json)])
    )

    assertions_store = _jumbf_superbox(UUID_C2PA_ASSERTIONS, "c2pa.assertions", assertion_boxes)

    claim_doc = {
        "instanceID": "xmp:iid:c2pa-eu-ai-act50-demo",
        "claim_generator": claim_generator,
        "claim_generator_info": [{"name": claim_generator.split(" ")[0], "version": "2.1"}],
        "alg": "sha256",
    }
    claim_json = json.dumps(claim_doc, separators=(",", ":")).encode("utf-8")
    claim_box = _jumbf_superbox(UUID_C2PA_CLAIM, "c2pa.claim.v2", [_bmff_box("json", claim_json)])

    manifest_children = [assertions_store, claim_box]
    if include_signature:
        # Deterministic 64-byte synthetic COSE_Sign1 ES256 envelope marker (`0xd284...`)
        cose_stub = (
            b"\xd2\x84\x43\xa1\x01\x26\xa0\x40\x58\x34"
            + b"C2PAGATE-COSE-ES256-DEMO-SIGNATURE-PAYLOAD-BYTES-001"
        )
        sig_box = _jumbf_superbox(UUID_C2PA_SIGNATURE, "c2pa.signature", [_bmff_box("c2cs", cose_stub)])
        manifest_children.append(sig_box)

    active_manifest = _jumbf_superbox(UUID_C2PA_MANIFEST, manifest_urn, manifest_children)
    return _jumbf_superbox(UUID_C2PA_STORE, "c2pa", [active_manifest])


def _png_chunk(chunk_type: str, chunk_data: bytes) -> bytes:
    raw_type = chunk_type.encode("ascii")
    crc = zlib.crc32(raw_type + chunk_data) & 0xFFFFFFFF
    return struct.pack(">I", len(chunk_data)) + raw_type + chunk_data + struct.pack(">I", crc)


def synthesize_png_bytes(
    *,
    include_c2pa: bool = True,
    digital_source_type: str = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    claim_generator: str = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    include_signature: bool = True,
    include_legacy_text: bool = False,
) -> bytes:
    """Build a valid 1x1 RGB PNG with or without an embedded `caBX` JUMBF C2PA Manifest Store."""
    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    chunks: list[bytes] = [PNG_SIGNATURE, _png_chunk("IHDR", ihdr_data)]

    if include_legacy_text:
        chunks.append(_png_chunk("tEXt", b"Software\x00ImagePipeline/1.0"))

    if include_c2pa:
        jumbf_bytes = build_jumbf_c2pa_store(
            digital_source_type=digital_source_type,
            claim_generator=claim_generator,
            include_signature=include_signature,
        )
        chunks.append(_png_chunk("caBX", jumbf_bytes))

    chunks.append(_png_chunk("IDAT", _PNG_1X1_IDAT_ZLIB))
    chunks.append(_png_chunk("IEND", b""))
    return b"".join(chunks)


def _jpeg_segment(marker_byte: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker_byte]) + struct.pack(">H", 2 + len(payload)) + payload


def synthesize_jpeg_bytes(
    *,
    include_c2pa: bool = True,
    multi_segment_app11: bool = False,
    digital_source_type: str = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    claim_generator: str = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    include_signature: bool = True,
) -> bytes:
    """Build a minimal valid JPEG stream with optional JPEG XT `APP11` (`0xFFEB`) JUMBF C2PA store."""
    parts: list[bytes] = [JPEG_SOI]
    # JFIF APP0
    parts.append(_jpeg_segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"))

    if include_c2pa:
        jumbf_bytes = build_jumbf_c2pa_store(
            digital_source_type=digital_source_type,
            claim_generator=claim_generator,
            include_signature=include_signature,
        )
        if multi_segment_app11 and len(jumbf_bytes) > 64:
            mid = len(jumbf_bytes) // 2
            pkt1 = b"JP" + struct.pack(">HI", 1, 1) + jumbf_bytes[:mid]
            pkt2 = b"JP" + struct.pack(">HI", 1, 2) + jumbf_bytes[:8] + jumbf_bytes[mid:]
            parts.append(_jpeg_segment(0xEB, pkt1))
            parts.append(_jpeg_segment(0xEB, pkt2))
        else:
            pkt = b"JP" + struct.pack(">HI", 1, 1) + jumbf_bytes
            parts.append(_jpeg_segment(0xEB, pkt))

    # Minimal SOF0 (1x1 grayscale) + SOS + 1 entropy byte + EOI
    parts.append(_jpeg_segment(0xC0, b"\x08\x00\x01\x00\x01\x01\x01\x11\x00"))
    parts.append(_jpeg_segment(0xDA, b"\x01\x01\x00\x00\x3f\x00"))
    parts.append(b"\x7f\xff\xd9")
    return b"".join(parts)


def _riff_chunk(fourcc: str, data: bytes) -> bytes:
    pad = b"\x00" if (len(data) & 1) else b""
    return fourcc.encode("ascii") + struct.pack("<I", len(data)) + data + pad


def synthesize_webp_bytes(
    *,
    include_c2pa: bool = True,
    digital_source_type: str = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    claim_generator: str = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    include_signature: bool = True,
) -> bytes:
    """Build a valid RIFF WebP container with optional `C2PA` chunk wrapping JUMBF."""
    # VP8X extended header (flags=0, canvas 1x1 encoded as 0,0,0)
    vp8x = _riff_chunk("VP8X", b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    # Minimal 1x1 VP8L lossless bitstream
    vp8l = _riff_chunk("VP8L", bytes.fromhex("2f000000000710fd8f00"))
    body_parts = [b"WEBP", vp8x, vp8l]

    if include_c2pa:
        jumbf_bytes = build_jumbf_c2pa_store(
            digital_source_type=digital_source_type,
            claim_generator=claim_generator,
            include_signature=include_signature,
        )
        body_parts.append(_riff_chunk("C2PA", jumbf_bytes))

    riff_body = b"".join(body_parts)
    return b"RIFF" + struct.pack("<I", len(riff_body)) + riff_body


def synthesize_mp4_bytes(
    *,
    include_c2pa: bool = True,
    digital_source_type: str = "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
    claim_generator: str = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    include_signature: bool = True,
) -> bytes:
    """Build a minimal ISOBMFF MP4 container with optional C2PA `uuid` (`d8fec3d6-...`) box."""
    ftyp = _bmff_box("ftyp", b"isom\x00\x00\x02\x00isomiso2mp41")
    boxes: list[bytes] = [ftyp]

    if include_c2pa:
        jumbf_bytes = build_jumbf_c2pa_store(
            digital_source_type=digital_source_type,
            claim_generator=claim_generator,
            software_agent="GenVideo-Diffusion/2.0",
            include_signature=include_signature,
        )
        # C2PA ISOBMFF uuid payload: 16B UUID + FullBox(0) + "manifest\0" + 8B offset + JUMBF superbox
        uuid_payload = C2PA_ISOBMFF_UUID_BYTES + b"\x00\x00\x00\x00manifest\x00" + struct.pack(">Q", 0) + jumbf_bytes
        boxes.append(_bmff_box("uuid", uuid_payload))

    moov = _bmff_box("moov", _bmff_box("mvhd", b"\x00" * 24))
    mdat = _bmff_box("mdat", b"\x00\x00\x00\x01\x09\x10\x00\x00")
    boxes.extend([moov, mdat])
    return b"".join(boxes)
