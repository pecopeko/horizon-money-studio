"""10-Gate EU AI Act Article 50 (2026-12-02) & Japan Nov-2026 AI Promotion Act Auditor.

Evaluates binary media containers (PNG `caBX`, JPEG `APP11`, WebP `C2PA`, MP4 `uuid`, `.c2pa`),
HTTP provenance headers, HTML / Schema.org JSON-LD markup, and AI service governance controls
across 10 deterministic compliance gates, and generates a 4-part exportable compliance bundle.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import json
import re
from typing import Any

try:
    from .c2pa_inspector import (
        ContainerInspection,
        IPTC_AI_SOURCE_CODES,
        IPTC_URI_PREFIX_HTTP,
        inspect_media_bytes,
        synthesize_jpeg_bytes,
        synthesize_mp4_bytes,
        synthesize_png_bytes,
        synthesize_webp_bytes,
    )
except ImportError:
    from c2pa_inspector import (  # type: ignore[no-redef]
        ContainerInspection,
        IPTC_AI_SOURCE_CODES,
        IPTC_URI_PREFIX_HTTP,
        inspect_media_bytes,
        synthesize_jpeg_bytes,
        synthesize_mp4_bytes,
        synthesize_png_bytes,
        synthesize_webp_bytes,
    )

EU_AI_ACT_ART50_SUNSET = "2026-12-02"
JP_AI_ACT_REVISION_TARGET = "2026-11"

GATE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "gate_number": 1,
        "gate_id": "C2PA-50-01",
        "title": "Art. 50(2) Embedded C2PA JUMBF Content Credentials",
        "statutory_ref": "EU AI Act Art. 50(2) (2026-12-02) · ISO/IEC 19566-5 JUMBF",
        "weight": 14,
        "default_severity": "critical",
    },
    {
        "gate_number": 2,
        "gate_id": "C2PA-50-02",
        "title": "Art. 50(2) IPTC digitalSourceType Machine-Readable URI",
        "statutory_ref": "EU AI Act Art. 50(2) · C2PA v2.1 · IPTC NewsCodes",
        "weight": 12,
        "default_severity": "critical",
    },
    {
        "gate_number": 3,
        "gate_id": "C2PA-50-03",
        "title": 'HTTP Link rel="c2pa-manifest" & Detached Provenance Headers',
        "statutory_ref": "C2PA v2.1 Soft Binding · RFC 8288 Link · RFC 9530 Digest",
        "weight": 10,
        "default_severity": "high",
    },
    {
        "gate_number": 4,
        "gate_id": "C2PA-50-04",
        "title": "HTML / Schema.org JSON-LD AI Provenance Markup",
        "statutory_ref": "EU AI Act Art. 50(2) Web Interoperability · Schema.org",
        "weight": 10,
        "default_severity": "high",
    },
    {
        "gate_number": 5,
        "gate_id": "C2PA-50-05",
        "title": "Art. 50(1) Interactive AI / Chatbot Pre-Interaction Notice",
        "statutory_ref": "EU AI Act Art. 50(1) Natural-Person Interaction Disclosure",
        "weight": 10,
        "default_severity": "high",
    },
    {
        "gate_number": 6,
        "gate_id": "C2PA-50-06",
        "title": "Art. 50(3) Emotion Recognition & Biometric Categorization Gate",
        "statutory_ref": "EU AI Act Art. 50(3) & Art. 5(1)(f) · GDPR / Japan APPI",
        "weight": 10,
        "default_severity": "critical",
    },
    {
        "gate_number": 7,
        "gate_id": "C2PA-50-07",
        "title": "Art. 50(4) Deepfake & Public-Interest Text Editorial Gate",
        "statutory_ref": "EU AI Act Art. 50(4) Synthetic Likeness & Editorial Review",
        "weight": 10,
        "default_severity": "high",
    },
    {
        "gate_number": 8,
        "gate_id": "C2PA-50-08",
        "title": "CDN & Image Optimizer Provenance Stripping Resilience",
        "statutory_ref": "EU AI Act Art. 50(2) Technical Robustness · C2PA Binding",
        "weight": 8,
        "default_severity": "high",
    },
    {
        "gate_number": 9,
        "gate_id": "C2PA-50-09",
        "title": "Japan AI Promotion Act Immutable Traceability & Incident Log",
        "statutory_ref": "Japan AI Promotion Act (Nov 2026 Tightening) · METI/MIC v1.1",
        "weight": 8,
        "default_severity": "high",
    },
    {
        "gate_number": 10,
        "gate_id": "C2PA-50-10",
        "title": "Japan AI Safety Autonomous Kill-Switch & Compliance Bundle",
        "statutory_ref": "Japan AISI Evaluation · Nov 2026 Autonomous Control",
        "weight": 8,
        "default_severity": "high",
    },
)

_LINK_C2PA_RE = re.compile(
    r'<([^>]+)>\s*;\s*[^,]*\brel\s*=\s*"?(?:c2pa-manifest|https?://c2pa\.org/manifest)"?',
    re.IGNORECASE,
)
_SCRIPT_LD_JSON_RE = re.compile(
    r'<script\b[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)
_META_AI_RE = re.compile(
    r'(?:<meta\b[^>]+name\s*=\s*["\'](?:ai-generated|digital-source-type|c2pa-manifest)["\']|itemprop\s*=\s*["\']digitalSourceType["\']|data-ai-generated\s*=\s*["\']true["\'])',
    re.IGNORECASE,
)
_HUMAN_IMPERSONATION_RE = re.compile(
    r"(?:you are speaking with a live human|100%\s*human\s*agent|not an ai assistant|人間が直接対応しています|AIではありません)",
    re.IGNORECASE,
)
_IPTC_CANONICAL_RE = re.compile(
    r"^https?://cv\.iptc\.org/newscodes/digitalsourcetype/([A-Za-z0-9_-]+)$",
    re.IGNORECASE,
)


class ComplianceParseError(ValueError):
    """Raised when JSON/JSONC audit configuration input is empty or malformed."""


@dataclass(frozen=True)
class AuditFinding:
    """Single deterministic compliance finding attached to one of the 10 gates."""

    gate_id: str
    severity: str
    title: str
    evidence: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    """Complete 10-gate EU AI Act Art. 50 + Japan AI Safety audit report and bundle."""

    asset_name: str
    status: str
    score: int
    grade: str
    eu_art50_sunset: str
    jp_revision_target: str
    gates_passed: int
    gates_warned: int
    gates_failed: int
    findings_count: int
    binary_inspection: dict[str, Any] | None
    gates: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    compliance_bundle: dict[str, Any]
    remediated_input: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def strip_jsonc_comments(raw_text: str) -> str:
    """Strip `//` and `/* ... */` comments and trailing commas while preserving string literals."""
    out: list[str] = []
    i = 0
    n = len(raw_text)
    in_string = False
    escape = False

    while i < n:
        ch = raw_text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n and raw_text[i + 1] == "/":
            i += 2
            while i < n and raw_text[i] not in ("\n", "\r"):
                i += 1
            continue

        if ch == "/" and i + 1 < n and raw_text[i + 1] == "*":
            end_idx = raw_text.find("*/", i + 2)
            if end_idx == -1:
                raise ComplianceParseError("Unterminated block comment in JSONC input.")
            i = end_idx + 2
            continue

        out.append(ch)
        i += 1

    cleaned = "".join(out)
    # Remove trailing commas before `}` or `]` outside strings
    return _strip_trailing_commas(cleaned)


def _strip_trailing_commas(text: str) -> str:
    res: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            res.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            res.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in (" ", "\t", "\r", "\n"):
                j += 1
            if j < n and text[j] in ("}", "]"):
                i += 1
                continue
        res.append(ch)
        i += 1
    return "".join(res)


def _normalize_headers(raw_headers: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            key = str(k).strip().lower()
            if not key:
                continue
            val = ", ".join(str(x) for x in v) if isinstance(v, list) else str(v).strip()
            if key in normalized and normalized[key]:
                normalized[key] = normalized[key] + ", " + val
            else:
                normalized[key] = val
    elif isinstance(raw_headers, str):
        for line in raw_headers.splitlines():
            stripped = line.strip()
            if not stripped or stripped.upper().startswith("HTTP/"):
                continue
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                key = k.strip().lower()
                val = v.strip()
                if key in normalized and normalized[key]:
                    normalized[key] = normalized[key] + ", " + val
                else:
                    normalized[key] = val
    return normalized


def _synthesize_from_spec(spec: dict[str, Any]) -> bytes:
    fmt = str(spec.get("format") or "png").strip().lower()
    include_c2pa = bool(spec.get("include_c2pa", True))
    dst = str(
        spec.get(
            "digital_source_type",
            IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
        )
    )
    claim_gen = str(spec.get("claim_generator") or "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0")
    include_sig = bool(spec.get("include_signature", True))

    if fmt == "png":
        return synthesize_png_bytes(
            include_c2pa=include_c2pa,
            digital_source_type=dst,
            claim_generator=claim_gen,
            include_signature=include_sig,
            include_legacy_text=bool(spec.get("include_legacy_text", False)),
        )
    if fmt in ("jpeg", "jpg"):
        return synthesize_jpeg_bytes(
            include_c2pa=include_c2pa,
            multi_segment_app11=bool(spec.get("multi_segment_app11", False)),
            digital_source_type=dst,
            claim_generator=claim_gen,
            include_signature=include_sig,
        )
    if fmt == "webp":
        return synthesize_webp_bytes(
            include_c2pa=include_c2pa,
            digital_source_type=dst,
            claim_generator=claim_gen,
            include_signature=include_sig,
        )
    if fmt in ("mp4", "isobmff", "m4a", "mov"):
        return synthesize_mp4_bytes(
            include_c2pa=include_c2pa,
            digital_source_type=dst,
            claim_generator=claim_gen,
            include_signature=include_sig,
        )
    raise ComplianceParseError(f"Unsupported synthetic_media format: {fmt!r}")


def _extract_jsonld_objects(html_snippet: str, explicit_jsonld: Any) -> tuple[list[dict[str, Any]], list[str]]:
    docs: list[dict[str, Any]] = []
    errors: list[str] = []

    def _collect(parsed: Any) -> None:
        if isinstance(parsed, dict):
            if isinstance(parsed.get("@graph"), list):
                for node in parsed["@graph"]:
                    if isinstance(node, dict):
                        merged = dict(node)
                        if "@context" not in merged and "@context" in parsed:
                            merged["@context"] = parsed["@context"]
                        docs.append(merged)
            else:
                docs.append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    docs.append(item)

    if isinstance(explicit_jsonld, (dict, list)):
        _collect(explicit_jsonld)
    elif isinstance(explicit_jsonld, str) and explicit_jsonld.strip():
        try:
            _collect(json.loads(explicit_jsonld))
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid json_ld JSON syntax: {exc.msg}")

    if html_snippet:
        for m in _SCRIPT_LD_JSON_RE.finditer(html_snippet):
            raw_block = m.group(1).strip()
            if not raw_block:
                continue
            try:
                _collect(json.loads(raw_block))
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid <script type='application/ld+json'> syntax: {exc.msg}")

    return docs, errors


def build_compliance_bundle(
    *,
    asset_name: str,
    public_asset_url: str,
    manifest_sidecar_url: str,
    mime_type: str,
    content_digest: str,
    digital_source_type_uri: str,
    claim_generator: str,
    publisher_name: str,
) -> dict[str, Any]:
    """Generate ready-to-paste HTTP headers, Schema.org JSON-LD, c2patool manifest, and CDN config."""
    schema_type = "VideoObject" if mime_type.startswith("video/") else "ImageObject"

    http_headers_snippet = "\n".join(
        [
            f'Link: <{manifest_sidecar_url}>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
            f"Content-Digest: {content_digest}",
            "Access-Control-Expose-Headers: Link, Content-Digest, X-AI-Provenance",
            f'X-AI-Provenance: EU-AI-Act-Art50; digitalSourceType="{digital_source_type_uri}"',
            "Cache-Control: public, max-age=31536000, no-transform",
        ]
    )

    jsonld_obj = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": asset_name,
        "contentUrl": public_asset_url,
        "encodingFormat": mime_type,
        "digitalSourceType": digital_source_type_uri,
        "creditText": f"AI-generated media signed with C2PA Content Credentials ({publisher_name})",
        "creator": {
            "@type": "Organization",
            "name": publisher_name,
        },
        "sdPublisher": {
            "@type": "Organization",
            "name": publisher_name,
        },
    }
    schema_org_script = (
        '<script type="application/ld+json">\n'
        + json.dumps(jsonld_obj, indent=2, ensure_ascii=False)
        + "\n</script>"
    )

    c2pa_manifest_template = {
        "alg": "es256",
        "ta_url": "http://timestamp.digicert.com",
        "claim_generator_info": [
            {
                "name": claim_generator.split(" ")[0],
                "version": "2.1.0",
            }
        ],
        "title": asset_name,
        "format": mime_type,
        "assertions": [
            {
                "label": "c2pa.actions.v2",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "digitalSourceType": digital_source_type_uri,
                            "softwareAgent": {
                                "name": claim_generator,
                            },
                        }
                    ]
                },
            },
            {
                "label": "stds.schema-org.CreativeWork",
                "data": {
                    "@context": "https://schema.org",
                    "@type": "CreativeWork",
                    "author": [{"@type": "Organization", "name": publisher_name}],
                },
            },
        ],
    }

    edge_preservation_config = "\n".join(
        [
            "# 1. Cloudflare Rules / Workers: disable lossy metadata stripping & attach C2PA Link header",
            "# Polish: Off (or 'Preserve Metadata' enabled); Cache-Control: no-transform",
            "add_header Link '<" + manifest_sidecar_url + ">; rel=\"c2pa-manifest\"' always;",
            "add_header Access-Control-Expose-Headers 'Link, Content-Digest, X-AI-Provenance' always;",
            "add_header Cache-Control 'public, max-age=31536000, no-transform' always;",
            "",
            "# 2. Next.js / Node.js sharp pipeline: preserve caBX / APP11 / C2PA / uuid & re-sign derivatives",
            "# await sharp(inputBuffer).keepMetadata().png().toBuffer(); // then run c2patool --parent",
        ]
    )

    return {
        "target_deadline": EU_AI_ACT_ART50_SUNSET,
        "jp_safety_revision": JP_AI_ACT_REVISION_TARGET,
        "http_headers_snippet": http_headers_snippet,
        "schema_org_jsonld": jsonld_obj,
        "schema_org_html_snippet": schema_org_script,
        "c2pa_manifest_template": c2pa_manifest_template,
        "edge_preservation_config": edge_preservation_config,
    }


def build_remediated_bundle_input(
    raw_bundle: dict[str, Any] | None,
    inspection: ContainerInspection | None = None,
) -> dict[str, Any]:
    """Produce a 10/10 compliant configuration & synthetic C2PA profile from any input bundle."""
    remediated = copy.deepcopy(raw_bundle) if isinstance(raw_bundle, dict) else {}
    asset = dict(remediated.get("asset") or {})

    fmt = "png"
    if inspection is not None and inspection.container_format in ("png", "jpeg", "webp", "mp4"):
        fmt = inspection.container_format
    elif isinstance(remediated.get("synthetic_media"), dict):
        cand = str(remediated["synthetic_media"].get("format") or "png").lower()
        if cand in ("png", "jpeg", "jpg", "webp", "mp4"):
            fmt = "jpeg" if cand == "jpg" else cand

    default_ext = "mp4" if fmt == "mp4" else ("jpg" if fmt == "jpeg" else fmt)
    asset_name = str(asset.get("name") or f"campaign-hero.{default_ext}")
    public_url = str(asset.get("public_url") or f"https://cdn.nordlicht-studio.eu/media/{asset_name}")
    if public_url.startswith("http://"):
        public_url = "https://" + public_url[len("http://") :]
    sidecar_url = str(asset.get("manifest_sidecar_url") or (public_url + ".c2pa"))
    if sidecar_url.startswith("http://"):
        sidecar_url = "https://" + sidecar_url[len("http://") :]

    publisher = str(asset.get("publisher") or "Nordlicht Studio GmbH")
    default_dst = (
        IPTC_URI_PREFIX_HTTP + "compositeWithTrainedAlgorithmicMedia"
        if fmt == "mp4"
        else IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia"
    )
    if inspection is not None and inspection.ai_source_type_detected and inspection.canonical_iptc_uris:
        dst_uri = inspection.canonical_iptc_uris[0]
    else:
        dst_uri = default_dst

    asset["name"] = asset_name
    asset["is_ai_generated"] = True
    asset["public_url"] = public_url
    asset["manifest_sidecar_url"] = sidecar_url
    asset["publisher"] = publisher
    remediated["asset"] = asset

    # Ensure synthetic_media produces a valid signed C2PA container if re-audited standalone
    remediated["synthetic_media"] = {
        "format": fmt,
        "include_c2pa": True,
        "digital_source_type": dst_uri,
        "claim_generator": "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
        "include_signature": True,
    }
    synth_inspection = inspect_media_bytes(_synthesize_from_spec(remediated["synthetic_media"]))
    digest_hdr = (
        inspection.content_digest_header
        if (inspection is not None and inspection.c2pa_present and inspection.has_signature and not inspection.non_ai_capture_asserted)
        else synth_inspection.content_digest_header
    )
    mime_type = inspection.mime_type if (inspection is not None and inspection.container_format != "unknown") else synth_inspection.mime_type

    remediated["http_headers"] = {
        "Link": f'<{sidecar_url}>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
        "Content-Digest": digest_hdr,
        "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
        "Cache-Control": "public, max-age=31536000, no-transform",
    }

    schema_type = "VideoObject" if mime_type.startswith("video/") else "ImageObject"
    remediated["json_ld"] = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": asset_name,
        "contentUrl": public_url,
        "encodingFormat": mime_type,
        "digitalSourceType": dst_uri,
        "creditText": f"AI-generated media signed with C2PA Content Credentials ({publisher})",
        "creator": {"@type": "Organization", "name": publisher},
        "sdPublisher": {"@type": "Organization", "name": publisher},
    }
    remediated.pop("html_snippet", None)

    gov = dict(remediated.get("governance") or {})
    interactive = dict(gov.get("interactive_ai") or {})
    applies_interactive = bool(interactive.get("applies", True))
    gov["interactive_ai"] = {
        "applies": applies_interactive,
        "pre_interaction_notice": True,
        "clear_human_distinction": True,
        "accessible_aria_disclosure": True,
        "hidden_in_tos_only": False,
        "impersonates_human": False,
    }

    bio = dict(gov.get("biometric_emotion") or {})
    bio_enabled = bool(bio.get("enabled", False))
    if bio_enabled:
        gov["biometric_emotion"] = {
            "enabled": True,
            "workplace_or_education_emotion_monitoring": False,
            "explicit_prior_subject_notice": True,
            "dpia_reference": str(bio.get("dpia_reference") or "DPIA-2026-EU-ART50-03"),
            "gdpr_appi_lawful_basis": str(bio.get("gdpr_appi_lawful_basis") or "explicit_consent_art9_2_a"),
        }
    else:
        gov["biometric_emotion"] = {
            "enabled": False,
            "workplace_or_education_emotion_monitoring": False,
        }

    df = dict(gov.get("deepfake_and_text") or {})
    gov["deepfake_and_text"] = {
        "generates_synthetic_likeness_or_voice": bool(df.get("generates_synthetic_likeness_or_voice", fmt == "mp4")),
        "visible_deepfake_disclosure": True,
        "publishes_public_interest_text": bool(df.get("publishes_public_interest_text", True)),
        "visible_ai_text_disclosure": True,
        "human_editorial_review": True,
        "editorial_responsibility_holder": str(
            df.get("editorial_responsibility_holder") or f"{publisher} Editorial Board"
        ),
        "editorial_review_log_id": str(df.get("editorial_review_log_id") or "ed-rev-2026-1123"),
    }

    gov["cdn_preservation"] = {
        "strip_all_metadata": False,
        "preserve_c2pa_chunks": True,
        "re_sign_derivatives": True,
        "immutable_origin_passthrough": True,
        "soft_binding_sidecar_fallback": True,
    }

    jp = dict(gov.get("jp_ai_safety") or {})
    retention = int(jp.get("retention_days") or 365)
    if retention < 180:
        retention = 365
    sla_hours = int(jp.get("incident_reporting_sla_hours") or 12)
    if sla_hours < 1 or sla_hours > 24:
        sla_hours = 12
    halt_sec = int(jp.get("max_halt_latency_seconds") or 15)
    if halt_sec < 1 or halt_sec > 60:
        halt_sec = 15

    gov["jp_ai_safety"] = {
        "immutable_audit_log_enabled": True,
        "retention_days": retention,
        "incident_reporting_sla_hours": sla_hours,
        "safety_governance_role": str(jp.get("safety_governance_role") or "CAIO & AI Safety Response Office"),
        "kill_switch_enabled": True,
        "kill_switch_mechanism": str(
            jp.get("kill_switch_mechanism") or "edge-kv://ai-agent-circuit-breaker/global-halt"
        ),
        "auto_circuit_breaker": True,
        "max_halt_latency_seconds": halt_sec,
    }

    remediated["governance"] = gov
    return remediated


def audit_c2pa_text(raw_text: str, *, media_bytes: bytes | None = None) -> AuditReport:
    """Parse a JSON/JSONC audit bundle string and run the 10-gate auditor."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ComplianceParseError("Compliance configuration text is empty.")
    stripped = strip_jsonc_comments(raw_text)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ComplianceParseError(f"Invalid JSON at line {exc.lineno} col {exc.colno}: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ComplianceParseError("Root compliance configuration must be a JSON object.")
    return audit_c2pa_compliance(parsed, media_bytes=media_bytes)


def audit_c2pa_compliance(
    bundle: dict[str, Any] | None = None,
    *,
    media_bytes: bytes | bytearray | memoryview | None = None,
) -> AuditReport:
    """Run all 10 EU AI Act Art. 50 (2026-12-02) & Japan Nov-2026 AI Safety gates."""
    if bundle is not None and not isinstance(bundle, dict):
        raise ComplianceParseError("Audit bundle must be a dictionary or None.")

    cfg = bundle if bundle is not None else {}
    asset = cfg.get("asset") if isinstance(cfg.get("asset"), dict) else {}
    is_ai_generated = bool(asset.get("is_ai_generated", True))

    actual_bytes: bytes | None = None
    if media_bytes is not None:
        actual_bytes = bytes(media_bytes)
    elif isinstance(cfg.get("synthetic_media"), dict):
        actual_bytes = _synthesize_from_spec(cfg["synthetic_media"])

    inspection: ContainerInspection | None = inspect_media_bytes(actual_bytes) if actual_bytes is not None else None

    default_name = "uploaded-asset." + (inspection.container_format if inspection and inspection.container_format != "unknown" else "bin")
    asset_name = str(asset.get("name") or default_name)
    headers = _normalize_headers(cfg.get("http_headers"))
    html_snippet = str(cfg.get("html_snippet") or "")
    explicit_jsonld = cfg.get("json_ld")
    gov = cfg.get("governance") if isinstance(cfg.get("governance"), dict) else {}

    gate_results: list[dict[str, Any]] = []
    all_findings: list[AuditFinding] = []
    raw_score = 0

    def _record_gate(
        gate_def: dict[str, Any],
        status: str,
        summary: str,
        gate_findings: list[AuditFinding],
    ) -> None:
        nonlocal raw_score
        weight = int(gate_def["weight"])
        if status == "pass":
            raw_score += weight
        elif status == "warn":
            raw_score += weight // 2

        all_findings.extend(gate_findings)
        gate_results.append(
            {
                "gate_number": gate_def["gate_number"],
                "gate_id": gate_def["gate_id"],
                "title": gate_def["title"],
                "statutory_ref": gate_def["statutory_ref"],
                "weight": weight,
                "severity": gate_def["default_severity"],
                "status": status,
                "summary": summary,
                "findings_count": len(gate_findings),
                "findings": [f.to_dict() for f in gate_findings],
            }
        )

    # ------------------------------------------------------------------
    # Gate 1: Art. 50(2) Embedded C2PA JUMBF Content Credentials Presence
    # ------------------------------------------------------------------
    g1_findings: list[AuditFinding] = []
    if inspection is None:
        if bool(asset.get("detached_c2pa_only", False)):
            g1_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-01",
                    severity="medium",
                    title="Detached C2PA manifest mode without binary stream verification",
                    evidence=f"asset '{asset_name}' supplied no binary stream; detached_c2pa_only=true.",
                    remediation="Embed a JUMBF Manifest Store (`caBX`, `APP11`, `C2PA`, or ISOBMFF `uuid`) directly in the media container alongside detached headers.",
                )
            )
            _record_gate(GATE_DEFINITIONS[0], "warn", "No media bytes supplied; relying solely on detached manifest declaration.", g1_findings)
        else:
            g1_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-01",
                    severity="critical",
                    title="No embedded C2PA JUMBF media bytes provided or detected",
                    evidence=f"asset '{asset_name}' has no inspected binary container.",
                    remediation="Sign output media with `c2patool` or `c2pa-rs` to embed an ISO/IEC 19566-5 JUMBF superbox.",
                )
            )
            _record_gate(GATE_DEFINITIONS[0], "fail", "Missing media binary container with embedded C2PA Content Credentials.", g1_findings)
    else:
        if inspection.crc_errors:
            for crc_err in inspection.crc_errors:
                g1_findings.append(
                    AuditFinding(
                        gate_id="C2PA-50-01",
                        severity="critical",
                        title="Container chunk CRC-32 integrity failure",
                        evidence=crc_err,
                        remediation="Re-generate and re-sign the PNG `caBX` chunk so container CRCs and COSE hashes validate.",
                    )
                )
        if not inspection.c2pa_present or not inspection.has_manifest_store:
            g1_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-01",
                    severity="critical",
                    title="Missing embedded C2PA JUMBF Manifest Store in binary container",
                    evidence=(
                        f"format={inspection.container_format}, size={inspection.byte_length}B, "
                        f"segments={[s.kind for s in inspection.segments]}, c2pa_carrier={inspection.c2pa_carrier}."
                    ),
                    remediation="Embed a signed C2PA v2.1 JUMBF superbox (`caBX` for PNG, `APP11 0xFFEB` for JPEG, `C2PA` for WebP, or `uuid d8fec3d6-...` for MP4).",
                )
            )
            _record_gate(
                GATE_DEFINITIONS[0],
                "fail",
                f"No C2PA JUMBF superbox found in {inspection.container_format.upper()} stream ({inspection.byte_length} bytes).",
                g1_findings,
            )
        elif g1_findings:
            _record_gate(GATE_DEFINITIONS[0], "fail", "Corrupted container CRC detected in C2PA media stream.", g1_findings)
        elif not (inspection.has_assertions and inspection.has_claim and inspection.has_signature) or inspection.parse_warnings:
            missing_parts: list[str] = []
            if not inspection.has_assertions:
                missing_parts.append("c2pa.assertions")
            if not inspection.has_claim:
                missing_parts.append("c2pa.claim")
            if not inspection.has_signature:
                missing_parts.append("c2pa.signature")
            if inspection.parse_warnings:
                missing_parts.append("truncated_box")
            g1_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-01",
                    severity="high",
                    title="Incomplete or unsigned JUMBF C2PA Manifest Store",
                    evidence=f"labels={inspection.jumbf_labels}, missing_or_warn={missing_parts}.",
                    remediation="Ensure the active C2PA manifest contains `c2pa.assertions`, `c2pa.claim.v2`, and a valid COSE_Sign1 `c2pa.signature` box.",
                )
            )
            _record_gate(
                GATE_DEFINITIONS[0],
                "warn",
                f"Partial JUMBF store in {inspection.c2pa_carrier}: missing/warn {', '.join(missing_parts)}.",
                g1_findings,
            )
        else:
            _record_gate(
                GATE_DEFINITIONS[0],
                "pass",
                f"Verified {inspection.container_format.upper()} `{inspection.c2pa_carrier}` JUMBF store ({len(inspection.jumbf_boxes)} boxes, COSE sig {inspection.signature_byte_length}B).",
                g1_findings,
            )

    # ------------------------------------------------------------------
    # Gate 2: Art. 50(2) IPTC digitalSourceType Machine-Readable URI
    # ------------------------------------------------------------------
    g2_findings: list[AuditFinding] = []
    dst_values = list(inspection.digital_source_types) if inspection is not None else []
    declared_dst = str(asset.get("declared_digital_source_type") or "").strip()
    if declared_dst and declared_dst not in dst_values:
        dst_values.append(declared_dst)

    canonical_ai_uris = [
        u for u in dst_values if _IPTC_CANONICAL_RE.match(u) and _IPTC_CANONICAL_RE.match(u).group(1) in IPTC_AI_SOURCE_CODES  # type: ignore[union-attr]
    ]
    any_ai_code = bool(inspection and inspection.ai_source_type_detected) or any(
        (u.rsplit("/", 1)[-1] in IPTC_AI_SOURCE_CODES) for u in dst_values
    )
    capture_claimed = bool(inspection and inspection.non_ai_capture_asserted) or (
        "digitalCapture" in dst_values or (IPTC_URI_PREFIX_HTTP + "digitalCapture") in dst_values
    )

    if is_ai_generated:
        if capture_claimed:
            g2_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-02",
                    severity="critical",
                    title="Deceptive non-AI camera `digitalCapture` IPTC URI on synthetic AI output",
                    evidence=f"digitalSourceType={dst_values} while is_ai_generated=true.",
                    remediation="Replace `digitalCapture` with `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia`.",
                )
            )
            _record_gate(GATE_DEFINITIONS[1], "fail", "Deceptive `digitalCapture` source type asserted on AI-generated asset.", g2_findings)
        elif not any_ai_code or (inspection is not None and not inspection.ai_source_type_detected):
            g2_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-02",
                    severity="critical",
                    title="Missing machine-readable IPTC AI `digitalSourceType` in C2PA assertions",
                    evidence=f"embedded digital_source_types={inspection.digital_source_types if inspection else []}.",
                    remediation="Add `digitalSourceType: \"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia\"` inside `c2pa.actions.v2`.",
                )
            )
            _record_gate(GATE_DEFINITIONS[1], "fail", "No embedded IPTC algorithmic `digitalSourceType` assertion found.", g2_findings)
        elif not canonical_ai_uris or (inspection is not None and not inspection.canonical_iptc_uris):
            g2_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-02",
                    severity="medium",
                    title="Non-canonical shorthand `digitalSourceType` string",
                    evidence=f"digital_source_types={dst_values}.",
                    remediation="Use the full canonical IPTC NewsCodes URI (`http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`).",
                )
            )
            _record_gate(GATE_DEFINITIONS[1], "warn", "Shorthand IPTC code detected without canonical `cv.iptc.org` URI.", g2_findings)
        else:
            _record_gate(GATE_DEFINITIONS[1], "pass", f"Canonical IPTC AI URI verified: {canonical_ai_uris[0]}.", g2_findings)
    else:
        if capture_claimed:
            _record_gate(GATE_DEFINITIONS[1], "pass", "Non-AI capture provenance URI matches `is_ai_generated=false`.", g2_findings)
        else:
            g2_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-02",
                    severity="low",
                    title="Non-AI asset lacks explicit IPTC capture URI",
                    evidence=f"digital_source_types={dst_values}.",
                    remediation="Declare `http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture` if camera-originated.",
                )
            )
            _record_gate(GATE_DEFINITIONS[1], "warn", "Non-AI asset has no explicit IPTC capture source URI.", g2_findings)

    # ------------------------------------------------------------------
    # Gate 3: HTTP Link rel="c2pa-manifest" & Detached Provenance Headers
    # ------------------------------------------------------------------
    g3_findings: list[AuditFinding] = []
    link_val = headers.get("link", "")
    link_match = _LINK_C2PA_RE.search(link_val)
    digest_val = headers.get("content-digest") or headers.get("digest") or ""
    expose_val = headers.get("access-control-expose-headers", "").lower()

    if not link_match:
        g3_findings.append(
            AuditFinding(
                gate_id="C2PA-50-03",
                severity="high",
                title='Missing HTTP `Link: <...>; rel="c2pa-manifest"` response header',
                evidence=f"link={link_val!r}",
                remediation='Configure CDN/origin to emit `Link: <https://.../asset.c2pa>; rel="c2pa-manifest"` so provenance survives embeds and proxies.',
            )
        )
        _record_gate(GATE_DEFINITIONS[2], "fail", 'No `Link: rel="c2pa-manifest"` header configured.', g3_findings)
    else:
        target_uri = link_match.group(1).strip()
        if target_uri.lower().startswith("http://"):
            g3_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-03",
                    severity="high",
                    title="Plaintext `http://` C2PA sidecar manifest URI in HTTP Link header",
                    evidence=f"Link target={target_uri!r}",
                    remediation="Serve detached `.c2pa` sidecar manifests strictly over TLS (`https://`).",
                )
            )
            _record_gate(GATE_DEFINITIONS[2], "fail", "Detached C2PA Link header points to insecure `http://` URI.", g3_findings)
        else:
            has_sha256_digest = "sha-256=" in digest_val.lower()
            exposes_link = "link" in expose_val or "*" in expose_val
            if not has_sha256_digest or not exposes_link:
                missing_hdrs: list[str] = []
                if not has_sha256_digest:
                    missing_hdrs.append("Content-Digest (sha-256)")
                if not exposes_link:
                    missing_hdrs.append("Access-Control-Expose-Headers: Link")
                g3_findings.append(
                    AuditFinding(
                        gate_id="C2PA-50-03",
                        severity="medium",
                        title="C2PA Link header present without digest or CORS exposure",
                        evidence=f"missing={missing_hdrs}",
                        remediation="Add `Content-Digest: sha-256=:...:` (RFC 9530) and `Access-Control-Expose-Headers: Link, Content-Digest` for cross-origin verifiers.",
                    )
                )
                _record_gate(
                    GATE_DEFINITIONS[2],
                    "warn",
                    f"HTTPS C2PA Link present; missing {', '.join(missing_hdrs)}.",
                    g3_findings,
                )
            else:
                _record_gate(
                    GATE_DEFINITIONS[2],
                    "pass",
                    f"Verified HTTPS `rel=\"c2pa-manifest\"` ({target_uri}), SHA-256 Content-Digest, and CORS Link exposure.",
                    g3_findings,
                )

    # ------------------------------------------------------------------
    # Gate 4: HTML / Schema.org JSON-LD AI Provenance Markup
    # ------------------------------------------------------------------
    g4_findings: list[AuditFinding] = []
    ld_docs, ld_errors = _extract_jsonld_objects(html_snippet, explicit_jsonld)
    if ld_errors:
        for err in ld_errors:
            g4_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-04",
                    severity="high",
                    title="Malformed JSON-LD provenance block",
                    evidence=err,
                    remediation="Fix JSON syntax inside `<script type=\"application/ld+json\">`.",
                )
            )
        _record_gate(GATE_DEFINITIONS[3], "fail", "Malformed JSON-LD syntax prevents machine-readable provenance parsing.", g4_findings)
    else:
        valid_ld = False
        partial_ld = False
        for doc in ld_docs:
            ctx = str(doc.get("@context") or "").lower()
            dst = str(doc.get("digitalSourceType") or "").strip()
            has_attr = any(bool(doc.get(k)) for k in ("creator", "sdPublisher", "author", "creditText"))
            m_iptc = _IPTC_CANONICAL_RE.match(dst)
            if "schema.org" in ctx and m_iptc and m_iptc.group(1) in IPTC_AI_SOURCE_CODES and has_attr:
                valid_ld = True
                break
            if "schema.org" in ctx and dst:
                partial_ld = True

        if valid_ld:
            _record_gate(GATE_DEFINITIONS[3], "pass", "Schema.org JSON-LD declares canonical IPTC `digitalSourceType` and publisher attribution.", g4_findings)
        elif partial_ld or _META_AI_RE.search(html_snippet):
            g4_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-04",
                    severity="medium",
                    title="Informal or incomplete HTML AI provenance markup",
                    evidence=f"json_ld_objects={len(ld_docs)}, meta_tag_detected={bool(_META_AI_RE.search(html_snippet))}.",
                    remediation="Include Schema.org `ImageObject`/`VideoObject`/`CreativeWork` JSON-LD with canonical IPTC `digitalSourceType` and `sdPublisher`.",
                )
            )
            _record_gate(GATE_DEFINITIONS[3], "warn", "Partial HTML/JSON-LD markup found; missing canonical IPTC URI or `sdPublisher`.", g4_findings)
        else:
            g4_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-04",
                    severity="high",
                    title="No Schema.org JSON-LD or HTML machine-readable AI provenance markup",
                    evidence="0 JSON-LD provenance blocks and 0 AI meta/microdata tags detected.",
                    remediation="Embed `<script type=\"application/ld+json\">` with `digitalSourceType` so search engines and assistive agents detect AI provenance.",
                )
            )
            _record_gate(GATE_DEFINITIONS[3], "fail", "Missing Schema.org JSON-LD machine-readable provenance markup.", g4_findings)

    # ------------------------------------------------------------------
    # Gate 5: Art. 50(1) Interactive AI / Chatbot Human-Facing Disclosure
    # ------------------------------------------------------------------
    g5_findings: list[AuditFinding] = []
    interactive = gov.get("interactive_ai") if isinstance(gov.get("interactive_ai"), dict) else {}
    impersonates = bool(interactive.get("impersonates_human", False)) or bool(_HUMAN_IMPERSONATION_RE.search(html_snippet))

    if impersonates:
        g5_findings.append(
            AuditFinding(
                gate_id="C2PA-50-05",
                severity="critical",
                title="Deceptive human impersonation violates EU AI Act Art. 50(1)",
                evidence="impersonates_human=true or deceptive live-human copy detected.",
                remediation="Remove human-impersonation prompts/copy and display a clear AI system notice prior to first user turn.",
            )
        )
        _record_gate(GATE_DEFINITIONS[4], "fail", "AI system impersonates a natural person in violation of Art. 50(1).", g5_findings)
    elif interactive.get("applies") is False:
        _record_gate(GATE_DEFINITIONS[4], "pass", "Non-interactive pipeline explicitly scoped (`interactive_ai.applies=false`).", g5_findings)
    elif not bool(interactive.get("pre_interaction_notice", False)) or bool(interactive.get("hidden_in_tos_only", False)):
        g5_findings.append(
            AuditFinding(
                gate_id="C2PA-50-05",
                severity="high",
                title="Missing pre-interaction AI disclosure (or buried solely in Terms of Service)",
                evidence=(
                    f"pre_interaction_notice={interactive.get('pre_interaction_notice')}, "
                    f"hidden_in_tos_only={interactive.get('hidden_in_tos_only')}."
                ),
                remediation="Present an unmistakable surface banner/badge informing users they are interacting with an AI system before first message submission.",
            )
        )
        _record_gate(GATE_DEFINITIONS[4], "fail", "Missing clear Art. 50(1) pre-interaction human-facing AI disclosure.", g5_findings)
    elif not (bool(interactive.get("clear_human_distinction", False)) and bool(interactive.get("accessible_aria_disclosure", False))):
        g5_findings.append(
            AuditFinding(
                gate_id="C2PA-50-05",
                severity="medium",
                title="Interactive AI notice lacks accessibility / ARIA role clarity",
                evidence=(
                    f"clear_human_distinction={interactive.get('clear_human_distinction')}, "
                    f"accessible_aria_disclosure={interactive.get('accessible_aria_disclosure')}."
                ),
                remediation="Expose AI disclosure via `aria-label` / `role=\"status\"` in plain language per EU AI Act Art. 50(1) accessibility requirements.",
            )
        )
        _record_gate(GATE_DEFINITIONS[4], "warn", "Pre-interaction AI notice enabled, but ARIA accessibility flag is incomplete.", g5_findings)
    else:
        _record_gate(GATE_DEFINITIONS[4], "pass", "Clear, accessible pre-interaction AI disclosure verified (`Art. 50(1)`).", g5_findings)

    # ------------------------------------------------------------------
    # Gate 6: Art. 50(3) Emotion Recognition & Biometric Categorization
    # ------------------------------------------------------------------
    g6_findings: list[AuditFinding] = []
    bio = gov.get("biometric_emotion") if isinstance(gov.get("biometric_emotion"), dict) else None
    if bio is None:
        g6_findings.append(
            AuditFinding(
                gate_id="C2PA-50-06",
                severity="medium",
                title="Biometric categorization & emotion recognition scope undeclared",
                evidence="governance.biometric_emotion object is absent.",
                remediation="Explicitly set `biometric_emotion.enabled: false`, or configure prior subject notice and DPIA reference if applicable.",
            )
        )
        _record_gate(GATE_DEFINITIONS[5], "warn", "Emotion/biometric scope undeclared in governance manifest.", g6_findings)
    elif bool(bio.get("workplace_or_education_emotion_monitoring", False)):
        g6_findings.append(
            AuditFinding(
                gate_id="C2PA-50-06",
                severity="critical",
                title="Prohibited workplace or education emotion inference (EU AI Act Art. 5(1)(f))",
                evidence="workplace_or_education_emotion_monitoring=true.",
                remediation="Immediately disable workplace/educational emotion recognition unless strictly medical/safety-exempt and legally cleared.",
            )
        )
        _record_gate(GATE_DEFINITIONS[5], "fail", "Prohibited workplace/education emotion inference flagged (`Art. 5(1)(f)`).", g6_findings)
    elif bio.get("enabled") is False:
        _record_gate(GATE_DEFINITIONS[5], "pass", "Emotion recognition and biometric categorization explicitly disabled.", g6_findings)
    else:
        has_notice = bool(bio.get("explicit_prior_subject_notice", False))
        dpia_ref = str(bio.get("dpia_reference") or "").strip()
        lawful_basis = str(bio.get("gdpr_appi_lawful_basis") or "").strip()
        if not has_notice or not dpia_ref:
            g6_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-06",
                    severity="critical",
                    title="Active emotion/biometric AI missing explicit prior notice or DPIA",
                    evidence=f"explicit_prior_subject_notice={has_notice}, dpia_reference={dpia_ref!r}.",
                    remediation="Provide explicit prior notice to exposed natural persons and record a GDPR/APPI Data Protection Impact Assessment (`dpia_reference`).",
                )
            )
            _record_gate(GATE_DEFINITIONS[5], "fail", "Active biometric/emotion system lacks mandatory Art. 50(3) subject notice or DPIA.", g6_findings)
        elif not lawful_basis:
            g6_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-06",
                    severity="medium",
                    title="Biometric/emotion notice present without documented GDPR/APPI lawful basis",
                    evidence="gdpr_appi_lawful_basis is empty.",
                    remediation="Record the GDPR Art. 9 / Japan APPI special-care personal data lawful basis.",
                )
            )
            _record_gate(GATE_DEFINITIONS[5], "warn", "Art. 50(3) notice and DPIA present; lawful basis string unset.", g6_findings)
        else:
            _record_gate(GATE_DEFINITIONS[5], "pass", f"Art. 50(3) prior notice, DPIA ({dpia_ref}), and lawful basis verified.", g6_findings)

    # ------------------------------------------------------------------
    # Gate 7: Art. 50(4) Deepfake & Public-Interest Text Editorial Gate
    # ------------------------------------------------------------------
    g7_findings: list[AuditFinding] = []
    df = gov.get("deepfake_and_text") if isinstance(gov.get("deepfake_and_text"), dict) else None
    if df is None:
        g7_findings.append(
            AuditFinding(
                gate_id="C2PA-50-07",
                severity="medium",
                title="Art. 50(4) deepfake & public-interest text policy undeclared",
                evidence="governance.deepfake_and_text object is absent.",
                remediation="Declare synthetic likeness disclosure rules and human editorial responsibility for public-interest text.",
            )
        )
        _record_gate(GATE_DEFINITIONS[6], "warn", "Art. 50(4) synthetic likeness and public-interest text policy undeclared.", g7_findings)
    else:
        likeness_used = bool(df.get("generates_synthetic_likeness_or_voice", False))
        likeness_disclosed = bool(df.get("visible_deepfake_disclosure", False))
        pub_text = bool(df.get("publishes_public_interest_text", False))
        text_disclosed = bool(df.get("visible_ai_text_disclosure", False))
        human_review = bool(df.get("human_editorial_review", False))
        editor_holder = str(df.get("editorial_responsibility_holder") or "").strip()
        review_log = str(df.get("editorial_review_log_id") or "").strip()

        likeness_fail = likeness_used and not likeness_disclosed
        text_fail = pub_text and not (text_disclosed or (human_review and bool(editor_holder)))

        if likeness_fail or text_fail:
            if likeness_fail:
                g7_findings.append(
                    AuditFinding(
                        gate_id="C2PA-50-07",
                        severity="high",
                        title="Undisclosed synthetic likeness / voice / deepfake output (Art. 50(4))",
                        evidence="generates_synthetic_likeness_or_voice=true, visible_deepfake_disclosure=false.",
                        remediation="Display clear visible/audible synthetic media disclosure per EU AI Act Art. 50(4).",
                    )
                )
            if text_fail:
                g7_findings.append(
                    AuditFinding(
                        gate_id="C2PA-50-07",
                        severity="high",
                        title="AI public-interest text lacks both visible disclosure and human editorial responsibility",
                        evidence=(
                            f"visible_ai_text_disclosure={text_disclosed}, human_editorial_review={human_review}, "
                            f"editorial_responsibility_holder={editor_holder!r}."
                        ),
                        remediation="Disclose AI text generation OR document human editorial review plus a named legal/natural editorial responsibility holder.",
                    )
                )
            _record_gate(GATE_DEFINITIONS[6], "fail", "Art. 50(4) deepfake or public-interest text disclosure failure.", g7_findings)
        elif pub_text and not text_disclosed and human_review and not review_log:
            g7_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-07",
                    severity="medium",
                    title="Editorial exemption claimed without sign-off audit log reference",
                    evidence=f"editorial_responsibility_holder={editor_holder!r}, editorial_review_log_id=''.",
                    remediation="Record `editorial_review_log_id` to evidence human review under supervisory audit.",
                )
            )
            _record_gate(GATE_DEFINITIONS[6], "warn", "Art. 50(4) editorial exemption lacks `editorial_review_log_id`.", g7_findings)
        else:
            _record_gate(GATE_DEFINITIONS[6], "pass", "Art. 50(4) deepfake disclosure and editorial responsibility controls verified.", g7_findings)

    # ------------------------------------------------------------------
    # Gate 8: CDN & Image Optimizer Provenance Stripping Resilience
    # ------------------------------------------------------------------
    g8_findings: list[AuditFinding] = []
    cdn = gov.get("cdn_preservation") if isinstance(gov.get("cdn_preservation"), dict) else {}
    cf_polished = "cf-polished" in headers or "x-fastly-imageopto-api" in headers
    strips_all = bool(cdn.get("strip_all_metadata", False))
    stripped_binary = bool(inspection is not None and inspection.probable_metadata_stripped)

    if strips_all or (cf_polished and (inspection is None or not inspection.c2pa_present)) or (stripped_binary and not link_match):
        g8_findings.append(
            AuditFinding(
                gate_id="C2PA-50-08",
                severity="high",
                title="CDN / image optimizer strips C2PA JUMBF chunks without detached recovery",
                evidence=(
                    f"strip_all_metadata={strips_all}, cdn_transform_header={cf_polished}, "
                    f"probable_metadata_stripped={stripped_binary}, link_header_present={bool(link_match)}."
                ),
                remediation="Disable lossy metadata stripping (`Cache-Control: no-transform`, `sharp.keepMetadata()`), re-sign resized derivatives, and serve a `rel=\"c2pa-manifest\"` Link header.",
            )
        )
        _record_gate(GATE_DEFINITIONS[7], "fail", "Active metadata stripping detected across binary asset / CDN pipeline.", g8_findings)
    else:
        preserve_ok = bool(cdn.get("preserve_c2pa_chunks", False))
        deriv_ok = bool(cdn.get("re_sign_derivatives", False) or cdn.get("immutable_origin_passthrough", False))
        sidecar_ok = bool(cdn.get("soft_binding_sidecar_fallback", False))
        if preserve_ok and deriv_ok and sidecar_ok and not stripped_binary:
            _record_gate(GATE_DEFINITIONS[7], "pass", "CDN chunk preservation, derivative re-signing, and detached sidecar fallback verified.", g8_findings)
        else:
            g8_findings.append(
                AuditFinding(
                    gate_id="C2PA-50-08",
                    severity="medium",
                    title="CDN / resizer metadata preservation policy incomplete",
                    evidence=(
                        f"preserve_c2pa_chunks={preserve_ok}, derivative_policy={deriv_ok}, "
                        f"soft_binding_sidecar_fallback={sidecar_ok}."
                    ),
                    remediation="Verify Cloudflare/CloudFront/Next.js `sharp` preserves `caBX`/`APP11`/`C2PA`/`uuid` chunks and enable sidecar soft-binding fallback.",
                )
            )
            _record_gate(GATE_DEFINITIONS[7], "warn", "Origin C2PA present, but CDN/optimizer preservation flags are incomplete.", g8_findings)

    # ------------------------------------------------------------------
    # Gate 9: Japan AI Promotion Act Immutable Traceability & Incident Log
    # ------------------------------------------------------------------
    g9_findings: list[AuditFinding] = []
    jp = gov.get("jp_ai_safety") if isinstance(gov.get("jp_ai_safety"), dict) else {}
    worm_log = bool(jp.get("immutable_audit_log_enabled", False))
    retention_days = int(jp.get("retention_days") or 0) if isinstance(jp.get("retention_days"), (int, float)) else 0
    sla_hrs = int(jp.get("incident_reporting_sla_hours") or 0) if isinstance(jp.get("incident_reporting_sla_hours"), (int, float)) else 0
    gov_role = str(jp.get("safety_governance_role") or "").strip()

    if not worm_log:
        g9_findings.append(
            AuditFinding(
                gate_id="C2PA-50-09",
                severity="high",
                title="Immutable AI provenance & incident audit log disabled (Japan AI Promotion Act)",
                evidence=f"immutable_audit_log_enabled={worm_log}.",
                remediation="Enable append-only/WORM audit logging (>=180 days) and <=24h Cabinet Office / METI incident reporting workflow.",
            )
        )
        _record_gate(GATE_DEFINITIONS[8], "fail", "Missing immutable AI audit trail required for Japan statutory investigation readiness.", g9_findings)
    elif retention_days < 180 or sla_hrs < 1 or sla_hrs > 24 or not gov_role:
        g9_findings.append(
            AuditFinding(
                gate_id="C2PA-50-09",
                severity="medium",
                title="Japan AI audit log retention, SLA, or CAIO role below statutory benchmark",
                evidence=f"retention_days={retention_days}, incident_reporting_sla_hours={sla_hrs}, safety_governance_role={gov_role!r}.",
                remediation="Set `retention_days >= 180`, `incident_reporting_sla_hours <= 24`, and designate a `safety_governance_role` (CAIO / Safety Office).",
            )
        )
        _record_gate(GATE_DEFINITIONS[8], "warn", f"Audit log active, but retention ({retention_days}d), SLA ({sla_hrs}h), or CAIO role needs tightening.", g9_findings)
    else:
        _record_gate(
            GATE_DEFINITIONS[8],
            "pass",
            f"Immutable WORM trace log ({retention_days}d retention, {sla_hrs}h incident SLA, {gov_role}) verified.",
            g9_findings,
        )

    # ------------------------------------------------------------------
    # Gate 10: Japan AI Safety Autonomous Kill-Switch & Compliance Bundle
    # ------------------------------------------------------------------
    g10_findings: list[AuditFinding] = []
    ks_enabled = bool(jp.get("kill_switch_enabled", False))
    ks_mech = str(jp.get("kill_switch_mechanism") or "").strip()
    cb_enabled = bool(jp.get("auto_circuit_breaker", False))
    halt_sec = int(jp.get("max_halt_latency_seconds") or 0) if isinstance(jp.get("max_halt_latency_seconds"), (int, float)) else 0

    if not ks_enabled or not ks_mech:
        g10_findings.append(
            AuditFinding(
                gate_id="C2PA-50-10",
                severity="high",
                title="Missing autonomous AI emergency kill-switch mechanism",
                evidence=f"kill_switch_enabled={ks_enabled}, kill_switch_mechanism={ks_mech!r}.",
                remediation="Wire an out-of-band kill-switch flag/endpoint capable of halting autonomous generation/publishing within 60 seconds.",
            )
        )
        _record_gate(GATE_DEFINITIONS[9], "fail", "No emergency kill-switch configured for autonomous AI egress.", g10_findings)
    elif not cb_enabled or halt_sec < 1 or halt_sec > 60:
        g10_findings.append(
            AuditFinding(
                gate_id="C2PA-50-10",
                severity="medium",
                title="Kill-switch lacks automated anomaly circuit-breaker or <=60s halt SLA",
                evidence=f"auto_circuit_breaker={cb_enabled}, max_halt_latency_seconds={halt_sec}.",
                remediation="Enable `auto_circuit_breaker: true` and bound `max_halt_latency_seconds <= 60`.",
            )
        )
        _record_gate(GATE_DEFINITIONS[9], "warn", f"Kill-switch declared, but circuit-breaker ({cb_enabled}) or halt SLA ({halt_sec}s) is weak.", g10_findings)
    else:
        _record_gate(
            GATE_DEFINITIONS[9],
            "pass",
            f"Emergency kill-switch ({ks_mech}), circuit-breaker, and {halt_sec}s halt SLA verified.",
            g10_findings,
        )

    # Compute overall summary metrics
    score = max(0, min(100, raw_score))
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 55:
        grade = "D"
    else:
        grade = "F"

    gates_passed = sum(1 for g in gate_results if g["status"] == "pass")
    gates_warned = sum(1 for g in gate_results if g["status"] == "warn")
    gates_failed = sum(1 for g in gate_results if g["status"] == "fail")

    if gates_failed == 0 and gates_warned == 0:
        status = "compliant"
    elif gates_failed == 0:
        status = "action_required"
    else:
        status = "non_compliant"

    # Build exportable 4-part compliance bundle + remediated input
    remediated = build_remediated_bundle_input(cfg, inspection=inspection)
    rem_asset = remediated["asset"]
    bundle_mime = inspection.mime_type if (inspection and inspection.container_format != "unknown") else "image/png"
    bundle_digest = (
        inspection.content_digest_header
        if inspection is not None
        else str(remediated["http_headers"]["Content-Digest"])
    )
    bundle_dst = str(remediated["json_ld"]["digitalSourceType"])
    bundle_gen = (
        inspection.claim_generators[0]
        if (inspection and inspection.claim_generators)
        else "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0"
    )
    export_bundle = build_compliance_bundle(
        asset_name=str(rem_asset["name"]),
        public_asset_url=str(rem_asset["public_url"]),
        manifest_sidecar_url=str(rem_asset["manifest_sidecar_url"]),
        mime_type=bundle_mime,
        content_digest=bundle_digest,
        digital_source_type_uri=bundle_dst,
        claim_generator=bundle_gen,
        publisher_name=str(rem_asset["publisher"]),
    )

    return AuditReport(
        asset_name=asset_name,
        status=status,
        score=score,
        grade=grade,
        eu_art50_sunset=EU_AI_ACT_ART50_SUNSET,
        jp_revision_target=JP_AI_ACT_REVISION_TARGET,
        gates_passed=gates_passed,
        gates_warned=gates_warned,
        gates_failed=gates_failed,
        findings_count=len(all_findings),
        binary_inspection=inspection.to_dict() if inspection is not None else None,
        gates=gate_results,
        findings=[f.to_dict() for f in all_findings],
        compliance_bundle=export_bundle,
        remediated_input=remediated,
    )


def build_sample_presets() -> dict[str, dict[str, Any]]:
    """Return 5 deterministic presets covering PNG `caBX`, JPEG `APP11`, MP4 `uuid`, and WebP `C2PA`."""
    # Precompute deterministic digests for compliant presets so HTTP Content-Digest matches exact bytes
    compliant_png = inspect_media_bytes(
        synthesize_png_bytes(
            include_c2pa=True,
            digital_source_type=IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
            claim_generator="C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
            include_signature=True,
        )
    )
    compliant_mp4 = inspect_media_bytes(
        synthesize_mp4_bytes(
            include_c2pa=True,
            digital_source_type=IPTC_URI_PREFIX_HTTP + "compositeWithTrainedAlgorithmicMedia",
            claim_generator="C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
            include_signature=True,
        )
    )

    return {
        "stripped-cdn-png": {
            "asset": {
                "name": "autumn-campaign-hero.png",
                "is_ai_generated": True,
                "public_url": "https://cdn.velvet-retail.eu/assets/autumn-campaign-hero.png",
                "publisher": "Velvet Retail GmbH",
            },
            "synthetic_media": {
                "format": "png",
                "include_c2pa": False,
                "include_legacy_text": False,
            },
            "http_headers": {
                "Cache-Control": "public, max-age=86400",
                "Cf-Polished": "origSize=418200, status=webp_bigger",
            },
            "html_snippet": '<img src="/assets/autumn-campaign-hero.png" alt="Autumn knitwear campaign">',
            "governance": {
                "interactive_ai": {
                    "applies": True,
                    "pre_interaction_notice": False,
                    "hidden_in_tos_only": True,
                },
                "biometric_emotion": {
                    "enabled": True,
                    "workplace_or_education_emotion_monitoring": False,
                    "explicit_prior_subject_notice": False,
                    "dpia_reference": "",
                },
                "deepfake_and_text": {
                    "generates_synthetic_likeness_or_voice": True,
                    "visible_deepfake_disclosure": False,
                    "publishes_public_interest_text": True,
                    "visible_ai_text_disclosure": False,
                    "human_editorial_review": False,
                    "editorial_responsibility_holder": "",
                },
                "cdn_preservation": {
                    "strip_all_metadata": True,
                    "preserve_c2pa_chunks": False,
                    "re_sign_derivatives": False,
                    "soft_binding_sidecar_fallback": False,
                },
                "jp_ai_safety": {
                    "immutable_audit_log_enabled": False,
                    "retention_days": 14,
                    "incident_reporting_sla_hours": 72,
                    "safety_governance_role": "",
                    "kill_switch_enabled": False,
                    "kill_switch_mechanism": "",
                },
            },
        },
        "deceptive-jpeg-app11": {
            "asset": {
                "name": "editorial-portrait-synth.jpg",
                "is_ai_generated": True,
                "public_url": "https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg",
                "manifest_sidecar_url": "https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg.c2pa",
                "publisher": "Hanse Briefing Media",
            },
            "synthetic_media": {
                "format": "jpeg",
                "include_c2pa": True,
                "multi_segment_app11": True,
                "digital_source_type": IPTC_URI_PREFIX_HTTP + "digitalCapture",
                "claim_generator": "StudioExport/1.4",
                "include_signature": False,
            },
            "http_headers": {
                "Link": '<https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg.c2pa>; rel="c2pa-manifest"',
            },
            "html_snippet": '<meta name="ai-generated" content="true">',
            "governance": {
                "interactive_ai": {
                    "applies": True,
                    "pre_interaction_notice": True,
                    "clear_human_distinction": True,
                    "accessible_aria_disclosure": False,
                },
                "biometric_emotion": {
                    "enabled": False,
                    "workplace_or_education_emotion_monitoring": False,
                },
                "deepfake_and_text": {
                    "generates_synthetic_likeness_or_voice": False,
                    "publishes_public_interest_text": True,
                    "visible_ai_text_disclosure": False,
                    "human_editorial_review": True,
                    "editorial_responsibility_holder": "Hanse Editorial Desk",
                    "editorial_review_log_id": "",
                },
                "cdn_preservation": {
                    "strip_all_metadata": False,
                    "preserve_c2pa_chunks": True,
                    "re_sign_derivatives": False,
                    "soft_binding_sidecar_fallback": False,
                },
                "jp_ai_safety": {
                    "immutable_audit_log_enabled": True,
                    "retention_days": 90,
                    "incident_reporting_sla_hours": 48,
                    "safety_governance_role": "AI Risk Officer",
                    "kill_switch_enabled": True,
                    "kill_switch_mechanism": "admin-toggle://cms-halt",
                    "auto_circuit_breaker": False,
                    "max_halt_latency_seconds": 180,
                },
            },
        },
        "webp-riff-c2pa": {
            "asset": {
                "name": "product-packshot-gen.webp",
                "is_ai_generated": True,
                "public_url": "https://static.kuroshio-labs.jp/img/product-packshot-gen.webp",
                "manifest_sidecar_url": "https://static.kuroshio-labs.jp/img/product-packshot-gen.webp.c2pa",
                "publisher": "Kuroshio Commerce KK",
            },
            "synthetic_media": {
                "format": "webp",
                "include_c2pa": True,
                "digital_source_type": IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
                "claim_generator": "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
                "include_signature": True,
            },
            "http_headers": {
                "Link": '<https://static.kuroshio-labs.jp/img/product-packshot-gen.webp.c2pa>; rel="c2pa-manifest"',
            },
            "json_ld": {
                "@context": "https://schema.org",
                "@type": "ImageObject",
                "name": "product-packshot-gen.webp",
                "digitalSourceType": IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
                "sdPublisher": {"@type": "Organization", "name": "Kuroshio Commerce KK"},
            },
            "governance": {
                "interactive_ai": {
                    "applies": True,
                    "pre_interaction_notice": True,
                    "clear_human_distinction": True,
                    "accessible_aria_disclosure": True,
                },
                "biometric_emotion": {
                    "enabled": False,
                    "workplace_or_education_emotion_monitoring": False,
                },
                "deepfake_and_text": {
                    "generates_synthetic_likeness_or_voice": False,
                    "publishes_public_interest_text": False,
                },
                "cdn_preservation": {
                    "strip_all_metadata": False,
                    "preserve_c2pa_chunks": True,
                    "re_sign_derivatives": True,
                    "soft_binding_sidecar_fallback": False,
                },
                "jp_ai_safety": {
                    "immutable_audit_log_enabled": True,
                    "retention_days": 365,
                    "incident_reporting_sla_hours": 12,
                    "safety_governance_role": "CAIO & AI Safety Office",
                    "kill_switch_enabled": True,
                    "kill_switch_mechanism": "feature-flag://kuroshio-ai-halt",
                    "auto_circuit_breaker": True,
                    "max_halt_latency_seconds": 20,
                },
            },
        },
        "compliant-png-cabx": {
            "asset": {
                "name": "eu-launch-keyvisual.png",
                "is_ai_generated": True,
                "public_url": "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png",
                "manifest_sidecar_url": "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png.c2pa",
                "publisher": "Nordlicht Studio GmbH",
            },
            "synthetic_media": {
                "format": "png",
                "include_c2pa": True,
                "digital_source_type": IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
                "claim_generator": "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
                "include_signature": True,
            },
            "http_headers": {
                "Link": '<https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png.c2pa>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
                "Content-Digest": compliant_png.content_digest_header,
                "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
                "Cache-Control": "public, max-age=31536000, no-transform",
            },
            "json_ld": {
                "@context": "https://schema.org",
                "@type": "ImageObject",
                "name": "eu-launch-keyvisual.png",
                "contentUrl": "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png",
                "encodingFormat": "image/png",
                "digitalSourceType": IPTC_URI_PREFIX_HTTP + "trainedAlgorithmicMedia",
                "creditText": "AI-generated media signed with C2PA Content Credentials (Nordlicht Studio GmbH)",
                "creator": {"@type": "Organization", "name": "Nordlicht Studio GmbH"},
                "sdPublisher": {"@type": "Organization", "name": "Nordlicht Studio GmbH"},
            },
            "governance": {
                "interactive_ai": {
                    "applies": True,
                    "pre_interaction_notice": True,
                    "clear_human_distinction": True,
                    "accessible_aria_disclosure": True,
                    "hidden_in_tos_only": False,
                    "impersonates_human": False,
                },
                "biometric_emotion": {
                    "enabled": False,
                    "workplace_or_education_emotion_monitoring": False,
                },
                "deepfake_and_text": {
                    "generates_synthetic_likeness_or_voice": False,
                    "visible_deepfake_disclosure": True,
                    "publishes_public_interest_text": True,
                    "visible_ai_text_disclosure": True,
                    "human_editorial_review": True,
                    "editorial_responsibility_holder": "Nordlicht Studio Editorial Board",
                    "editorial_review_log_id": "ed-rev-2026-1120",
                },
                "cdn_preservation": {
                    "strip_all_metadata": False,
                    "preserve_c2pa_chunks": True,
                    "re_sign_derivatives": True,
                    "immutable_origin_passthrough": True,
                    "soft_binding_sidecar_fallback": True,
                },
                "jp_ai_safety": {
                    "immutable_audit_log_enabled": True,
                    "retention_days": 365,
                    "incident_reporting_sla_hours": 12,
                    "safety_governance_role": "CAIO & AI Safety Response Office",
                    "kill_switch_enabled": True,
                    "kill_switch_mechanism": "edge-kv://ai-agent-circuit-breaker/global-halt",
                    "auto_circuit_breaker": True,
                    "max_halt_latency_seconds": 15,
                },
            },
        },
        "compliant-mp4-uuid": {
            "asset": {
                "name": "avatar-keynote-localization.mp4",
                "is_ai_generated": True,
                "public_url": "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4",
                "manifest_sidecar_url": "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4.c2pa",
                "publisher": "Mirai Broadcast Corp.",
            },
            "synthetic_media": {
                "format": "mp4",
                "include_c2pa": True,
                "digital_source_type": IPTC_URI_PREFIX_HTTP + "compositeWithTrainedAlgorithmicMedia",
                "claim_generator": "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
                "include_signature": True,
            },
            "http_headers": {
                "Link": '<https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4.c2pa>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
                "Content-Digest": compliant_mp4.content_digest_header,
                "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
                "Cache-Control": "public, max-age=31536000, no-transform",
            },
            "json_ld": {
                "@context": "https://schema.org",
                "@type": "VideoObject",
                "name": "avatar-keynote-localization.mp4",
                "contentUrl": "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4",
                "encodingFormat": "video/mp4",
                "digitalSourceType": IPTC_URI_PREFIX_HTTP + "compositeWithTrainedAlgorithmicMedia",
                "creditText": "AI-localized keynote signed with C2PA ISOBMFF uuid Content Credentials",
                "creator": {"@type": "Organization", "name": "Mirai Broadcast Corp."},
                "sdPublisher": {"@type": "Organization", "name": "Mirai Broadcast Corp."},
            },
            "governance": {
                "interactive_ai": {
                    "applies": False,
                },
                "biometric_emotion": {
                    "enabled": False,
                    "workplace_or_education_emotion_monitoring": False,
                },
                "deepfake_and_text": {
                    "generates_synthetic_likeness_or_voice": True,
                    "visible_deepfake_disclosure": True,
                    "publishes_public_interest_text": True,
                    "visible_ai_text_disclosure": True,
                    "human_editorial_review": True,
                    "editorial_responsibility_holder": "Mirai Broadcast Standards Desk",
                    "editorial_review_log_id": "mb-ed-2026-0991",
                },
                "cdn_preservation": {
                    "strip_all_metadata": False,
                    "preserve_c2pa_chunks": True,
                    "re_sign_derivatives": True,
                    "immutable_origin_passthrough": True,
                    "soft_binding_sidecar_fallback": True,
                },
                "jp_ai_safety": {
                    "immutable_audit_log_enabled": True,
                    "retention_days": 730,
                    "incident_reporting_sla_hours": 6,
                    "safety_governance_role": "Chief AI Safety Officer (CAIO)",
                    "kill_switch_enabled": True,
                    "kill_switch_mechanism": "envoy-eds://mirai-ai-egress/emergency-stop",
                    "auto_circuit_breaker": True,
                    "max_halt_latency_seconds": 10,
                },
            },
        },
    }
