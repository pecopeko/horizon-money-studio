"""Unit tests for Track 24: C2PAGATE (c2pa-ai-act50-auditor)."""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import shutil
import subprocess
import zlib

import pytest

from tracks.track1_apify.eu_ai_act50_c2pa_actor import main as actor_mod
from tracks.track24_eu_ai_act50_c2pa import (
    C2PA_ISOBMFF_UUID_HEX,
    ComplianceParseError,
    EU_AI_ACT_ART50_SUNSET,
    GATE_DEFINITIONS,
    JP_AI_ACT_REVISION_TARGET,
    audit_c2pa_compliance,
    audit_c2pa_text,
    build_jumbf_c2pa_store,
    build_sample_presets,
    inspect_media_bytes,
    strip_jsonc_comments,
    synthesize_jpeg_bytes,
    synthesize_mp4_bytes,
    synthesize_png_bytes,
    synthesize_webp_bytes,
)
from tracks.track24_eu_ai_act50_c2pa.cli import main as cli_main


def _gate_map(report_dict: dict) -> dict[str, dict]:
    return {g["gate_id"]: g for g in report_dict["gates"]}


def test_gate_definitions_has_10_ordered_gates_summing_to_100() -> None:
    assert len(GATE_DEFINITIONS) == 10
    assert [g["gate_number"] for g in GATE_DEFINITIONS] == list(range(1, 11))
    assert [g["gate_id"] for g in GATE_DEFINITIONS] == [f"C2PA-50-{i:02d}" for i in range(1, 11)]
    assert sum(int(g["weight"]) for g in GATE_DEFINITIONS) == 100
    assert all(int(g["weight"]) % 2 == 0 for g in GATE_DEFINITIONS)


def test_png_cabx_synthesizer_and_binary_inspector_crc_and_zlib() -> None:
    signed_png = synthesize_png_bytes(
        include_c2pa=True,
        digital_source_type="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
        claim_generator="OpenAI-ImageGen/2.1 c2pa-rs/0.36.0",
        include_signature=True,
    )
    insp = inspect_media_bytes(signed_png)
    assert insp.container_format == "png"
    assert insp.mime_type == "image/png"
    assert insp.c2pa_carrier == "caBX"
    assert insp.c2pa_present is True
    assert insp.has_manifest_store is True
    assert insp.has_assertions is True
    assert insp.has_actions is True
    assert insp.has_claim is True
    assert insp.has_signature is True
    assert insp.ai_source_type_detected is True
    assert insp.non_ai_capture_asserted is False
    assert insp.crc_errors == []
    assert "c2pa" in insp.jumbf_labels
    assert "c2pa.assertions" in insp.jumbf_labels
    assert "c2pa.actions.v2" in insp.jumbf_labels
    assert "c2pa.claim.v2" in insp.jumbf_labels
    assert "c2pa.signature" in insp.jumbf_labels
    assert any("OpenAI-ImageGen" in g for g in insp.claim_generators)

    # Verify the synthesized IDAT decompresses cleanly to a 1x1 RGB scanline
    idat_seg = next(s for s in insp.segments if s.kind == "IDAT")
    idat_payload = signed_png[idat_seg.offset + 8 : idat_seg.offset + idat_seg.length - 4]
    assert zlib.decompress(idat_payload) == b"\x00\xf2\xf4\xf7"

    # Flipping a byte inside caBX triggers CRC-32 failure and Gate 1 FAIL
    corrupted = bytearray(signed_png)
    corrupted[48] ^= 0xFF
    bad_insp = inspect_media_bytes(corrupted)
    assert len(bad_insp.crc_errors) == 1
    rep = audit_c2pa_compliance({"asset": {"name": "corrupt.png"}}, media_bytes=corrupted)
    assert _gate_map(rep.to_dict())["C2PA-50-01"]["status"] == "fail"


def test_jpeg_app11_single_and_multisegment_reassembly() -> None:
    single_jpg = synthesize_jpeg_bytes(include_c2pa=True, multi_segment_app11=False)
    insp_single = inspect_media_bytes(single_jpg)
    assert insp_single.container_format == "jpeg"
    assert insp_single.c2pa_carrier == "APP11"
    assert insp_single.c2pa_present is True
    assert insp_single.has_signature is True
    assert sum(1 for s in insp_single.segments if s.kind == "APP11") == 1

    multi_jpg = synthesize_jpeg_bytes(
        include_c2pa=True,
        multi_segment_app11=True,
        digital_source_type="https://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia",
    )
    insp_multi = inspect_media_bytes(multi_jpg)
    assert insp_multi.container_format == "jpeg"
    assert insp_multi.c2pa_carrier == "APP11"
    assert insp_multi.c2pa_present is True
    assert insp_multi.has_signature is True
    assert "algorithmicMedia" in insp_multi.iptc_source_codes
    assert sum(1 for s in insp_multi.segments if s.kind == "APP11") == 2

    stripped_jpg = synthesize_jpeg_bytes(include_c2pa=False)
    insp_stripped = inspect_media_bytes(stripped_jpg)
    assert insp_stripped.c2pa_present is False
    assert insp_stripped.probable_metadata_stripped is True


def test_webp_riff_c2pa_and_mp4_isobmff_uuid_and_standalone_jumbf() -> None:
    webp = synthesize_webp_bytes(include_c2pa=True)
    insp_webp = inspect_media_bytes(webp)
    assert insp_webp.container_format == "webp"
    assert insp_webp.c2pa_carrier == "C2PA"
    assert insp_webp.c2pa_present is True
    assert insp_webp.has_signature is True

    stripped_webp = synthesize_webp_bytes(include_c2pa=False)
    assert inspect_media_bytes(stripped_webp).c2pa_present is False

    mp4 = synthesize_mp4_bytes(include_c2pa=True)
    insp_mp4 = inspect_media_bytes(mp4)
    assert insp_mp4.container_format == "mp4"
    assert insp_mp4.c2pa_carrier == "uuid"
    assert insp_mp4.c2pa_present is True
    assert insp_mp4.has_signature is True
    assert "compositeWithTrainedAlgorithmicMedia" in insp_mp4.iptc_source_codes
    assert any(s.kind == "uuid" and C2PA_ISOBMFF_UUID_HEX in s.detail for s in insp_mp4.segments)

    raw_jumbf = build_jumbf_c2pa_store()
    insp_jumbf = inspect_media_bytes(raw_jumbf)
    assert insp_jumbf.container_format == "jumbf"
    assert insp_jumbf.c2pa_present is True
    assert insp_jumbf.has_signature is True


def test_compliant_presets_pass_all_10_gates_with_100_score() -> None:
    presets = build_sample_presets()
    for key in ("compliant-png-cabx", "compliant-mp4-uuid"):
        rep = audit_c2pa_compliance(presets[key])
        assert rep.eu_art50_sunset == EU_AI_ACT_ART50_SUNSET
        assert rep.jp_revision_target == JP_AI_ACT_REVISION_TARGET
        assert rep.score == 100
        assert rep.grade == "A"
        assert rep.status == "compliant"
        assert rep.gates_passed == 10
        assert rep.gates_warned == 0
        assert rep.gates_failed == 0
        assert rep.findings_count == 0


def test_stripped_and_deceptive_presets_flag_expected_gates() -> None:
    presets = build_sample_presets()
    stripped_rep = audit_c2pa_compliance(presets["stripped-cdn-png"])
    assert stripped_rep.score == 0
    assert stripped_rep.status == "non_compliant"
    assert stripped_rep.gates_failed == 10

    deceptive_rep = audit_c2pa_compliance(presets["deceptive-jpeg-app11"])
    d_gates = _gate_map(deceptive_rep.to_dict())
    assert deceptive_rep.status == "non_compliant"
    assert d_gates["C2PA-50-01"]["status"] == "warn"  # Unsigned APP11 JUMBF
    assert d_gates["C2PA-50-02"]["status"] == "fail"  # Deceptive digitalCapture on AI media
    assert d_gates["C2PA-50-03"]["status"] == "warn"  # Missing Content-Digest & CORS Link exposure
    assert d_gates["C2PA-50-04"]["status"] == "warn"  # Meta tag only, no Schema.org JSON-LD
    assert d_gates["C2PA-50-05"]["status"] == "warn"  # Missing ARIA disclosure
    assert d_gates["C2PA-50-06"]["status"] == "pass"  # Biometric/emotion disabled
    assert d_gates["C2PA-50-07"]["status"] == "warn"  # Editorial exemption missing review log ID
    assert d_gates["C2PA-50-08"]["status"] == "warn"  # Incomplete CDN preservation flags
    assert d_gates["C2PA-50-09"]["status"] == "warn"  # Retention 90d < 180d & SLA 48h > 24h
    assert d_gates["C2PA-50-10"]["status"] == "warn"  # No auto circuit breaker & halt 180s > 60s


@pytest.mark.parametrize(
    "preset_key",
    [
        "stripped-cdn-png",
        "deceptive-jpeg-app11",
        "webp-riff-c2pa",
        "compliant-png-cabx",
        "compliant-mp4-uuid",
    ],
)
def test_auto_remediated_bundle_roundtrips_to_100_pass(preset_key: str) -> None:
    presets = build_sample_presets()
    initial = audit_c2pa_compliance(presets[preset_key])
    re_audited = audit_c2pa_compliance(initial.remediated_input)
    assert re_audited.score == 100, f"Preset {preset_key} failed roundtrip: {re_audited.findings}"
    assert re_audited.gates_passed == 10
    assert re_audited.status == "compliant"


def test_gate3_plaintext_http_link_and_gate5_human_impersonation_and_gate6_workplace_ban() -> None:
    cfg = copy.deepcopy(build_sample_presets()["compliant-png-cabx"])
    cfg["http_headers"]["Link"] = '<http://insecure.example.eu/manifest.c2pa>; rel="c2pa-manifest"'
    cfg["html_snippet"] = "<div>You are speaking with a live human agent!</div>"
    cfg["governance"]["biometric_emotion"] = {
        "enabled": True,
        "workplace_or_education_emotion_monitoring": True,
    }
    rep = audit_c2pa_compliance(cfg)
    gates = _gate_map(rep.to_dict())
    assert gates["C2PA-50-03"]["status"] == "fail"
    assert gates["C2PA-50-05"]["status"] == "fail"
    assert gates["C2PA-50-06"]["status"] == "fail"


def test_jsonc_comments_and_invalid_json_raise_compliance_parse_error() -> None:
    raw_jsonc = """
    {
      // EU AI Act Art. 50 JSONC comment
      "asset": {
        "name": "hero.png",
        "public_url": "https://cdn.example.eu/hero.png", /* preserve // in URL */
      },
    }
    """
    cleaned = strip_jsonc_comments(raw_jsonc)
    assert "https://cdn.example.eu/hero.png" in cleaned
    rep = audit_c2pa_text(raw_jsonc, media_bytes=synthesize_png_bytes(include_c2pa=True))
    assert rep.asset_name == "hero.png"

    with pytest.raises(ComplianceParseError, match="empty"):
        audit_c2pa_text("   ")

    with pytest.raises(ComplianceParseError, match="Invalid JSON"):
        audit_c2pa_text("{broken_json}")

    with pytest.raises(ComplianceParseError, match="Unterminated"):
        audit_c2pa_text('/* unclosed comment {"asset": {}}')


def test_cli_preset_binary_inspect_and_bundle_exports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle_path = tmp_path / "compliance-bundle.json"
    rem_path = tmp_path / "remediated-input.json"
    png_path = tmp_path / "signed-sample.png"
    png_path.write_bytes(synthesize_png_bytes(include_c2pa=True))

    # 1. --inspect-only on binary PNG
    rc_insp = cli_main(["--inspect-only", "--format", "json", str(png_path)])
    assert rc_insp == 0
    insp_json = json.loads(capsys.readouterr().out)
    assert insp_json["container_format"] == "png"
    assert insp_json["c2pa_carrier"] == "caBX"

    # 2. --preset stripped-cdn-png exports bundle + remediated JSON and exits 2
    rc_fail = cli_main(
        [
            "--preset",
            "stripped-cdn-png",
            "--format",
            "json",
            "--export-bundle",
            str(bundle_path),
            "--export-remediated",
            str(rem_path),
        ]
    )
    assert rc_fail == 2
    rep_out = json.loads(capsys.readouterr().out)
    assert rep_out["status"] == "non_compliant"
    assert bundle_path.is_file()
    assert rem_path.is_file()

    bundle_doc = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert 'rel="c2pa-manifest"' in bundle_doc["http_headers_snippet"]
    assert "trainedAlgorithmicMedia" in bundle_doc["schema_org_html_snippet"]
    assert bundle_doc["c2pa_manifest_template"]["alg"] == "es256"

    # 3. Re-running CLI on exported remediated JSON passes 10/10 with exit code 0
    rc_pass = cli_main([str(rem_path), "--fail-on", "warn"])
    assert rc_pass == 0
    text_out = capsys.readouterr().out
    assert "Score: 100/100" in text_out
    assert "10 PASS / 0 WARN / 0 FAIL" in text_out


def test_python_and_js_engines_have_byte_and_score_parity_and_node_tests_pass() -> None:
    node_bin = shutil.which("node")
    if not node_bin:
        nvm_candidates = sorted((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"))
        assert nvm_candidates, "Node.js binary required for JS parity verification"
        node_bin = str(nvm_candidates[-1])

    web_dir = Path(__file__).resolve().parent.parent / "tracks" / "track24_eu_ai_act50_c2pa" / "web"

    # Run `node --test` suite
    test_proc = subprocess.run(
        [node_bin, "--test", "./test/engine.test.mjs"],
        cwd=str(web_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    assert "fail 0" in test_proc.stdout

    # Verify exact parity across all 5 presets
    js_eval = (
        "import { auditC2paCompliance, buildSamplePresets } from './engine.js';"
        "const p = buildSamplePresets();"
        "const out = {};"
        "for (const k of Object.keys(p)) { out[k] = auditC2paCompliance(p[k]); }"
        "console.log(JSON.stringify(out));"
    )
    proc = subprocess.run(
        [node_bin, "--input-type=module", "-e", js_eval],
        cwd=str(web_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    js_reports = json.loads(proc.stdout)
    py_presets = build_sample_presets()

    for key, py_cfg in py_presets.items():
        py_rep = audit_c2pa_compliance(py_cfg).to_dict()
        js_rep = js_reports[key]
        assert py_rep["score"] == js_rep["score"], f"Score mismatch on {key}"
        assert py_rep["grade"] == js_rep["grade"], f"Grade mismatch on {key}"
        assert py_rep["status"] == js_rep["status"], f"Status mismatch on {key}"
        assert py_rep["gates_passed"] == js_rep["gates_passed"]
        assert py_rep["gates_warned"] == js_rep["gates_warned"]
        assert py_rep["gates_failed"] == js_rep["gates_failed"]
        assert py_rep["binary_inspection"]["sha256_hex"] == js_rep["binary_inspection"]["sha256_hex"]
        assert py_rep["binary_inspection"]["byte_length"] == js_rep["binary_inspection"]["byte_length"]
        assert py_rep["binary_inspection"]["jumbf_labels"] == js_rep["binary_inspection"]["jumbf_labels"]
        assert py_rep["compliance_bundle"] == js_rep["compliance_bundle"]
        assert py_rep["remediated_input"] == js_rep["remediated_input"]


def test_apify_ppe_actor_schemas_ssrf_guard_and_batch_execution() -> None:
    actor_dir = Path(__file__).resolve().parent.parent / "tracks" / "track1_apify" / "eu_ai_act50_c2pa_actor"
    actor_json = json.loads((actor_dir / ".actor" / "actor.json").read_text(encoding="utf-8"))
    assert actor_json["name"] == "eu-ai-act-art50-c2pa-provenance-auditor"
    assert actor_json["input"] == "./input_schema.json"
    assert actor_json["output"] == "./output_schema.json"
    assert actor_json["storages"] == {"dataset": "./dataset_schema.json"}

    ppe_json = json.loads((actor_dir / ".actor" / "pay_per_event.json").read_text(encoding="utf-8"))
    events = ppe_json["pricingPerEvent"]["actorChargeEvents"]
    assert "asset_audited" in events
    assert events["asset_audited"]["eventPriceUsd"] == 0.003

    banned_word = "cap" + "tcha"
    for p in actor_dir.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".py", ".json"}:
            assert banned_word not in p.read_text(encoding="utf-8").lower(), f"Banned term found in {p}"

    # Verify SSRF host & private IP blocks
    for blocked_url in (
        "http://localhost:8080/test.png",
        "http://127.0.0.1/secret.png",
        "http://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.12/internal.png",
        "file:///etc/passwd",
    ):
        with pytest.raises(actor_mod.SsrfBlockedError):
            actor_mod.validate_public_url(blocked_url)

    # Simulate remote HTML page + og:image signed PNG fetch without network calls
    signed_png = synthesize_png_bytes(include_c2pa=True)
    png_insp = inspect_media_bytes(signed_png)
    html_page = (
        '<!doctype html><html><head>'
        '<meta property="og:image" content="https://cdn.nordlicht-studio.eu/media/hero.png">'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"ImageObject","digitalSourceType":"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia","sdPublisher":{"@type":"Organization","name":"Nordlicht"}}'
        "</script></head><body></body></html>"
    ).encode("utf-8")

    def fake_fetcher(url: str, max_bytes: int) -> actor_mod.FetchedResource:
        if url.startswith("http://127.0.0.1"):
            actor_mod.validate_public_url(url)
        if url.endswith(".png"):
            return actor_mod.FetchedResource(
                final_url=url,
                status_code=206,
                headers={
                    "content-type": "image/png",
                    "link": '<https://cdn.nordlicht-studio.eu/media/hero.png.c2pa>; rel="c2pa-manifest"',
                    "content-digest": png_insp.content_digest_header,
                    "access-control-expose-headers": "Link, Content-Digest",
                },
                body=signed_png,
            )
        return actor_mod.FetchedResource(
            final_url=url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=html_page,
        )

    presets = build_sample_presets()
    batch = actor_mod.audit_asset_batch(
        [
            "https://nordlicht-studio.eu/campaign",
            {"id": "inline-b64", "media_base64": base64.b64encode(signed_png).decode("ascii")},
            {"id": "compliant-preset", **presets["compliant-png-cabx"]},
            "http://127.0.0.1/admin",
            "{invalid_json",
        ],
        fetcher=fake_fetcher,
    )
    assert len(batch) == 5
    rec0, bill0 = batch[0]
    rec1, bill1 = batch[1]
    rec2, bill2 = batch[2]
    rec3, bill3 = batch[3]
    rec4, bill4 = batch[4]

    assert bill0 is True and rec0["binary_inspection"]["c2pa_carrier"] == "caBX"
    assert bill1 is True and rec1["binary_inspection"]["c2pa_present"] is True
    assert bill2 is True and rec2["score"] == 100 and rec2["status"] == "compliant"
    assert bill3 is False and rec3["status"] == "blocked_ssrf"
    assert bill4 is False and rec4["status"] == "parse_error"
