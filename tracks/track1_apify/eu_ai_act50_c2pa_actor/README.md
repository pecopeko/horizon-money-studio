# EU AI Act Art. 50 C2PA JUMBF & Japan AI Safety Provenance Auditor (`eu-ai-act-art50-c2pa-provenance-auditor`)

Browserless, SSRF-hardened Pay-Per-Event Apify Actor inspecting public media/page URLs and CI/CD asset bundles against:

1. **EU AI Act Article 50 (`2026-12-02`) Machine-Readable Provenance & Transparency Obligations**:
   - Binary ISO/IEC 19566-5 JUMBF container parsing across **PNG (`caBX`)**, **JPEG (`APP11` `0xFFEB` JPEG XT)**, **WebP (`RIFF C2PA`)**, and **MP4 / ISOBMFF (`uuid` `d8fec3d6-1b0e-483c-9297-5828877ec481`)**.
   - IPTC NewsCodes `digitalSourceType` URI verification (`trainedAlgorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`, `algorithmicMedia`) and deceptive `digitalCapture` detection.
   - HTTP `Link: <...>; rel="c2pa-manifest"` + RFC 9530 `Content-Digest` + Schema.org JSON-LD web interoperability checks.
   - Art. 50(1) interactive chatbot notice, Art. 50(3) biometric/emotion notice, Art. 50(4) deepfake & public-interest text editorial review, and CDN metadata-stripping resilience.
2. **Japan AI Promotion Act (`2026-11` Statutory Tightening)**:
   - Immutable WORM audit logging (`>=180` days), `<=24h` incident reporting SLA, and `<=60s` autonomous agent emergency kill-switch / circuit-breaker verification.

## Pricing (`PAY_PER_EVENT`)

- `asset_audited`: **$0.003** per valid asset or URL audited (`$3.00` per 1,000 assets).
- Unreachable network errors, SSRF-blocked internal hosts, and malformed JSON parse errors return structured diagnostics at **$0.00**.

Crafted by peco · Apache-2.0
