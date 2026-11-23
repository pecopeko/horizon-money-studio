import assert from "node:assert/strict";
import test from "node:test";

import {
  C2PA_ISOBMFF_UUID_HEX,
  ComplianceParseError,
  EU_AI_ACT_ART50_SUNSET,
  GATE_DEFINITIONS,
  IPTC_URI_PREFIX_HTTP,
  auditC2paCompliance,
  auditC2paText,
  buildSamplePresets,
  inspectMediaBytes,
  stripJsoncComments,
  synthesizeJpegBytes,
  synthesizeMp4Bytes,
  synthesizePngBytes,
  synthesizeWebpBytes,
} from "../engine.js";

test("GATE_DEFINITIONS defines 10 ordered gates summing to 100 points", () => {
  assert.equal(GATE_DEFINITIONS.length, 10);
  const sum = GATE_DEFINITIONS.reduce((acc, g) => acc + g.weight, 0);
  assert.equal(sum, 100);
  assert.deepEqual(
    GATE_DEFINITIONS.map((g) => g.gate_id),
    Array.from({ length: 10 }, (_, idx) => `C2PA-50-${String(idx + 1).padStart(2, "0")}`) /* taste-skill-ignore: gate ID assertion */
  );
});

test("inspectMediaBytes parses signed PNG caBX JUMBF labels, IPTC URI, and CRC-32", () => {
  const pngBytes = synthesizePngBytes({
    includeC2pa: true,
    digitalSourceType: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
    claimGenerator: "C2PAGATE-Test/2.1",
    includeSignature: true,
  });
  const insp = inspectMediaBytes(pngBytes);
  assert.equal(insp.container_format, "png");
  assert.equal(insp.c2pa_carrier, "caBX");
  assert.equal(insp.c2pa_present, true);
  assert.equal(insp.has_manifest_store, true);
  assert.equal(insp.has_assertions, true);
  assert.equal(insp.has_actions, true);
  assert.equal(insp.has_claim, true);
  assert.equal(insp.has_signature, true);
  assert.equal(insp.ai_source_type_detected, true);
  assert.equal(insp.crc_errors.length, 0);
  assert.ok(insp.jumbf_labels.includes("c2pa"));
  assert.ok(insp.jumbf_labels.includes("c2pa.assertions"));
  assert.ok(insp.jumbf_labels.includes("c2pa.actions.v2"));
  assert.ok(insp.jumbf_labels.includes("c2pa.signature"));
});

test("inspectMediaBytes detects corrupted PNG caBX CRC-32", () => {
  const pngBytes = synthesizePngBytes({ includeC2pa: true });
  const corrupted = new Uint8Array(pngBytes);
  // Flip one byte inside the caBX chunk payload
  corrupted[50] ^= 0xff;
  const insp = inspectMediaBytes(corrupted);
  assert.equal(insp.container_format, "png");
  assert.ok(insp.crc_errors.length >= 1);

  const report = auditC2paCompliance({ asset: { name: "tampered.png" } }, { mediaBytes: corrupted });
  const gate1 = report.gates.find((g) => g.gate_id === "C2PA-50-01");
  assert.equal(gate1.status, "fail");
});

test("inspectMediaBytes reassembles multi-segment JPEG XT APP11 0xFFEB JUMBF packets", () => {
  const jpegBytes = synthesizeJpegBytes({
    includeC2pa: true,
    multiSegmentApp11: true,
    digitalSourceType: `${IPTC_URI_PREFIX_HTTP}algorithmicMedia`,
    includeSignature: true,
  });
  const insp = inspectMediaBytes(jpegBytes);
  assert.equal(insp.container_format, "jpeg");
  assert.equal(insp.c2pa_carrier, "APP11");
  assert.equal(insp.c2pa_present, true);
  assert.equal(insp.has_signature, true);
  assert.ok(insp.iptc_source_codes.includes("algorithmicMedia"));
  const app11Segments = insp.segments.filter((s) => s.kind === "APP11");
  assert.equal(app11Segments.length, 2);
});

test("inspectMediaBytes parses WebP RIFF C2PA chunk and MP4 ISOBMFF uuid C2PA box", () => {
  const webpBytes = synthesizeWebpBytes({ includeC2pa: true });
  const webpInsp = inspectMediaBytes(webpBytes);
  assert.equal(webpInsp.container_format, "webp");
  assert.equal(webpInsp.c2pa_carrier, "C2PA");
  assert.equal(webpInsp.c2pa_present, true);
  assert.equal(webpInsp.has_signature, true);

  const mp4Bytes = synthesizeMp4Bytes({ includeC2pa: true });
  const mp4Insp = inspectMediaBytes(mp4Bytes);
  assert.equal(mp4Insp.container_format, "mp4");
  assert.equal(mp4Insp.c2pa_carrier, "uuid");
  assert.equal(mp4Insp.c2pa_present, true);
  assert.equal(mp4Insp.has_signature, true);
  assert.ok(mp4Insp.segments.some((s) => s.kind === "uuid" && s.detail.includes(C2PA_ISOBMFF_UUID_HEX)));
});

test("compliant-png-cabx and compliant-mp4-uuid presets score 100/100 Grade A", () => {
  const presets = buildSamplePresets();
  for (const key of ["compliant-png-cabx", "compliant-mp4-uuid"]) {
    const rep = auditC2paCompliance(presets[key]);
    assert.equal(rep.eu_art50_sunset, EU_AI_ACT_ART50_SUNSET);
    assert.equal(rep.score, 100);
    assert.equal(rep.grade, "A");
    assert.equal(rep.status, "compliant");
    assert.equal(rep.gates_passed, 10);
    assert.equal(rep.gates_failed, 0);
    assert.equal(rep.findings_count, 0);
  }
});

test("auto-remediation round-trips all 5 presets to 100/100 compliant", () => {
  const presets = buildSamplePresets();
  for (const [key, cfg] of Object.entries(presets)) {
    const initial = auditC2paCompliance(cfg);
    const reAudited = auditC2paCompliance(initial.remediated_input);
    assert.equal(reAudited.score, 100, `Expected 100 after remediation on ${key}, got ${reAudited.score}`);
    assert.equal(reAudited.gates_passed, 10);
    assert.equal(reAudited.status, "compliant");
  }
});

test("JSONC comments and trailing commas parse cleanly; invalid JSON throws ComplianceParseError", () => {
  const rawJsonc = `{
    // EU AI Act Art. 50 test bundle
    "asset": {
      "name": "banner.png",
      "public_url": "https://cdn.example.eu/banner.png", /* keep // inside URL */
    },
  }`;
  const cleaned = stripJsoncComments(rawJsonc);
  assert.ok(cleaned.includes("https://cdn.example.eu/banner.png"));
  const rep = auditC2paText(rawJsonc, { mediaBytes: synthesizePngBytes({ includeC2pa: true }) });
  assert.equal(rep.asset_name, "banner.png");

  assert.throws(() => auditC2paText("   "), ComplianceParseError);
  assert.throws(() => auditC2paText("{bad_json}"), ComplianceParseError);
});
