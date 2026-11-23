/**
 * C2PAGATE Browser-Local & Node.js Zero-Dependency Engine (ES2022).
 *
 * - Pure `Uint8Array` / `DataView` binary container & ISO/IEC 19566-5 JUMBF inspector
 *   (`PNG caBX`, `JPEG APP11 0xFFEB`, `WebP RIFF C2PA`, `MP4/ISOBMFF uuid`, `.c2pa`)
 * - Deterministic pure-JS SHA-256 (`Content-Digest` RFC 9530) & IEEE 802.3 CRC-32
 * - Byte-exact binary C2PA demo container synthesizers matching Python `c2pa_inspector.py`
 * - 10-gate EU AI Act Article 50 (`2026-12-02`) + Japan Nov-2026 AI Promotion Act auditor
 */

export const EU_AI_ACT_ART50_SUNSET = "2026-12-02";
export const JP_AI_ACT_REVISION_TARGET = "2026-11";
export const C2PA_ISOBMFF_UUID_HEX = "d8fec3d6-1b0e-483c-9297-5828877ec481";
export const IPTC_URI_PREFIX_HTTP = "http://cv.iptc.org/newscodes/digitalsourcetype/";

export const IPTC_AI_SOURCE_CODES = new Set([
  "trainedAlgorithmicMedia",
  "compositeWithTrainedAlgorithmicMedia",
  "algorithmicMedia",
  "trainedAlgorithmicData",
  "compositeSynthetic",
  "virtualRecording",
]);

export const IPTC_CAPTURE_SOURCE_CODES = new Set([
  "digitalCapture",
  "negativeFilm",
  "positiveFilm",
  "print",
  "humanEdits",
  "minorHumanEdits",
  "compositeCapture",
]);

export const GATE_DEFINITIONS = [
  {
    gate_number: 1,
    gate_id: "C2PA-50-01",
    title: "Art. 50(2) Embedded C2PA JUMBF Content Credentials",
    statutory_ref: "EU AI Act Art. 50(2) (2026-12-02) · ISO/IEC 19566-5 JUMBF",
    weight: 14,
    default_severity: "critical",
  },
  {
    gate_number: 2,
    gate_id: "C2PA-50-02",
    title: "Art. 50(2) IPTC digitalSourceType Machine-Readable URI",
    statutory_ref: "EU AI Act Art. 50(2) · C2PA v2.1 · IPTC NewsCodes",
    weight: 12,
    default_severity: "critical",
  },
  {
    gate_number: 3,
    gate_id: "C2PA-50-03",
    title: 'HTTP Link rel="c2pa-manifest" & Detached Provenance Headers',
    statutory_ref: "C2PA v2.1 Soft Binding · RFC 8288 Link · RFC 9530 Digest",
    weight: 10,
    default_severity: "high",
  },
  {
    gate_number: 4,
    gate_id: "C2PA-50-04",
    title: "HTML / Schema.org JSON-LD AI Provenance Markup",
    statutory_ref: "EU AI Act Art. 50(2) Web Interoperability · Schema.org",
    weight: 10,
    default_severity: "high",
  },
  {
    gate_number: 5,
    gate_id: "C2PA-50-05",
    title: "Art. 50(1) Interactive AI / Chatbot Pre-Interaction Notice",
    statutory_ref: "EU AI Act Art. 50(1) Natural-Person Interaction Disclosure",
    weight: 10,
    default_severity: "high",
  },
  {
    gate_number: 6,
    gate_id: "C2PA-50-06",
    title: "Art. 50(3) Emotion Recognition & Biometric Categorization Gate",
    statutory_ref: "EU AI Act Art. 50(3) & Art. 5(1)(f) · GDPR / Japan APPI",
    weight: 10,
    default_severity: "critical",
  },
  {
    gate_number: 7,
    gate_id: "C2PA-50-07",
    title: "Art. 50(4) Deepfake & Public-Interest Text Editorial Gate",
    statutory_ref: "EU AI Act Art. 50(4) Synthetic Likeness & Editorial Review",
    weight: 10,
    default_severity: "high",
  },
  {
    gate_number: 8,
    gate_id: "C2PA-50-08",
    title: "CDN & Image Optimizer Provenance Stripping Resilience",
    statutory_ref: "EU AI Act Art. 50(2) Technical Robustness · C2PA Binding",
    weight: 8,
    default_severity: "high",
  },
  {
    gate_number: 9,
    gate_id: "C2PA-50-09",
    title: "Japan AI Promotion Act Immutable Traceability & Incident Log",
    statutory_ref: "Japan AI Promotion Act (Nov 2026 Tightening) · METI/MIC v1.1",
    weight: 8,
    default_severity: "high",
  },
  {
    gate_number: 10,
    gate_id: "C2PA-50-10",
    title: "Japan AI Safety Autonomous Kill-Switch & Compliance Bundle",
    statutory_ref: "Japan AISI Evaluation · Nov 2026 Autonomous Control",
    weight: 8,
    default_severity: "high",
  },
];

export class ComplianceParseError extends Error {
  constructor(message) {
    super(message);
    this.name = "ComplianceParseError";
  }
}

const PNG_SIGNATURE = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const PNG_1X1_IDAT_ZLIB = hexToBytes("78da63f8f4e53b0005b902de");
const C2PA_ISOBMFF_UUID_BYTES = hexToBytes("d8fec3d61b0e483c92975828877ec481");

const UUID_C2PA_STORE = hexToBytes("6332706100110010800000aa00389b71");
const UUID_C2PA_MANIFEST = hexToBytes("63326d6100110010800000aa00389b71");
const UUID_C2PA_ASSERTIONS = hexToBytes("6332617300110010800000aa00389b71");
const UUID_C2PA_CLAIM = hexToBytes("6332636c00110010800000aa00389b71");
const UUID_C2PA_SIGNATURE = hexToBytes("6332637300110010800000aa00389b71");
const UUID_JUMBF_JSON = hexToBytes("6a736f6e00110010800000aa00389b71");

const C2PA_STORE_UUID_STR = "63327061-0011-0010-8000-00aa00389b71";
const C2PA_SIGNATURE_UUID_STR = "63326373-0011-0010-8000-00aa00389b71";

const ISOBMFF_TOP_TYPES = new Set([
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
]);

const UTF8_ENCODER = new TextEncoder();
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: false });

// ---------------------------------------------------------------------------
// Pure-JS Byte Utilities, CRC-32 (IEEE 802.3), and SHA-256 (FIPS 180-4)
// ---------------------------------------------------------------------------

export function hexToBytes(hex) {
  const clean = hex.replace(/[^0-9a-fA-F]/g, "");
  const out = new Uint8Array(clean.length >>> 1);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

export function bytesToHex(bytes) {
  let out = "";
  for (let i = 0; i < bytes.length; i += 1) {
    out += bytes[i].toString(16).padStart(2, "0"); /* taste-skill-ignore: hex byte encoding */
  }
  return out;
}

const B64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

export function bytesToBase64(bytes) {
  let out = "";
  const len = bytes.length;
  for (let i = 0; i < len; i += 3) {
    const b0 = bytes[i];
    const b1 = i + 1 < len ? bytes[i + 1] : 0;
    const b2 = i + 2 < len ? bytes[i + 2] : 0;
    const trip = (b0 << 16) | (b1 << 8) | b2;
    out += B64_CHARS[(trip >>> 18) & 63];
    out += B64_CHARS[(trip >>> 12) & 63];
    out += i + 1 < len ? B64_CHARS[(trip >>> 6) & 63] : "=";
    out += i + 2 < len ? B64_CHARS[trip & 63] : "=";
  }
  return out;
}

function concatBytes(arrays) {
  let total = 0;
  for (const a of arrays) total += a.length;
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32Bytes(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) {
    c = CRC32_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotr32(x, n) {
  return ((x >>> n) | (x << (32 - n))) >>> 0;
}

export function sha256Bytes(msgBytes) {
  const bitLenHi = Math.floor((msgBytes.length * 8) / 0x100000000) >>> 0;
  const bitLenLo = (msgBytes.length * 8) >>> 0;
  const padLen = (64 - ((msgBytes.length + 9) % 64)) % 64;
  const totalLen = msgBytes.length + 1 + padLen + 8;
  const padded = new Uint8Array(totalLen);
  padded.set(msgBytes, 0);
  padded[msgBytes.length] = 0x80;
  const dv = new DataView(padded.buffer);
  dv.setUint32(totalLen - 8, bitLenHi, false);
  dv.setUint32(totalLen - 4, bitLenLo, false);

  let h0 = 0x6a09e667;
  let h1 = 0xbb67ae85;
  let h2 = 0x3c6ef372;
  let h3 = 0xa54ff53a;
  let h4 = 0x510e527f;
  let h5 = 0x9b05688c;
  let h6 = 0x1f83d9ab;
  let h7 = 0x5be0cd19;

  const w = new Uint32Array(64);
  for (let off = 0; off < totalLen; off += 64) {
    for (let i = 0; i < 16; i += 1) {
      w[i] = dv.getUint32(off + i * 4, false);
    }
    for (let i = 16; i < 64; i += 1) {
      const s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }

    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    let f = h5;
    let g = h6;
    let h = h7;

    for (let i = 0; i < 64; i += 1) {
      const S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
      const ch = ((e & f) ^ (~e & g)) >>> 0;
      const temp1 = (h + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
      const S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
      const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const temp2 = (S0 + maj) >>> 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
    h5 = (h5 + f) >>> 0;
    h6 = (h6 + g) >>> 0;
    h7 = (h7 + h) >>> 0;
  }

  const digest = new Uint8Array(32);
  const outDv = new DataView(digest.buffer);
  outDv.setUint32(0, h0, false);
  outDv.setUint32(4, h1, false);
  outDv.setUint32(8, h2, false);
  outDv.setUint32(12, h3, false);
  outDv.setUint32(16, h4, false);
  outDv.setUint32(20, h5, false);
  outDv.setUint32(24, h6, false);
  outDv.setUint32(28, h7, false);
  return digest;
}

// ---------------------------------------------------------------------------
// ISO/IEC 19566-5 JUMBF & Media Container Binary Parser
// ---------------------------------------------------------------------------

function toUint8Array(input) {
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  if (ArrayBuffer.isView(input)) return new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
  throw new ComplianceParseError("Expected Uint8Array or ArrayBuffer for binary inspection.");
}

function bytesEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function startsWithBytes(buf, prefix) {
  if (buf.length < prefix.length) return false;
  for (let i = 0; i < prefix.length; i += 1) {
    if (buf[i] !== prefix[i]) return false;
  }
  return true;
}

function isPrintableFourcc(raw4) {
  if (raw4.length !== 4) return false;
  for (let i = 0; i < 4; i += 1) {
    if (raw4[i] < 32 || raw4[i] > 126) return false;
  }
  return true;
}

function safeFourcc(raw4) {
  let s = "";
  for (let i = 0; i < raw4.length; i += 1) {
    const b = raw4[i];
    s += b >= 32 && b <= 126 ? String.fromCharCode(b) : `\\x${b.toString(16).padStart(2, "0")}`; /* taste-skill-ignore: hex escape */
  }
  return s;
}

function formatUuidBytes(raw16) {
  const h = bytesToHex(raw16);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
}

function appendUnique(arr, val) {
  const cleaned = String(val || "").trim();
  if (cleaned && !arr.includes(cleaned)) {
    arr.push(cleaned);
  }
}

const IPTC_URI_GLOBAL_RE = /https?:\/\/cv\.iptc\.org\/newscodes\/digitalsourcetype\/([A-Za-z0-9_-]+)/gi;
const IPTC_CANONICAL_RE = /^https?:\/\/cv\.iptc\.org\/newscodes\/digitalsourcetype\/([A-Za-z0-9_-]+)$/i;
const BARE_DST_GLOBAL_RE = /"?digitalSourceType"?\s*[:=]\s*"([A-Za-z0-9_:/.-]+)"/gi;
const CLAIM_GEN_GLOBAL_RE = /"?(?:claim_generator|softwareAgent)"?\s*[:=]\s*"([^"\x00-\x1f]{2,120})"/gi;
const PRINTABLE_GEN_RE = /((?:OpenAI|Adobe_Firefly|Firefly|Midjourney|Google|Stability|Leica|Sony|Canon|Nikon|C2PAGATE|c2pa-rs|c2patool)[A-Za-z0-9_./ -]{1,80})/g;

function extractIptcCode(uriOrCode) {
  const val = String(uriOrCode || "").trim();
  const m = val.match(/https?:\/\/cv\.iptc\.org\/newscodes\/digitalsourcetype\/([A-Za-z0-9_-]+)/i);
  if (m) return m[1];
  const idx = val.lastIndexOf("/");
  return idx !== -1 ? val.slice(idx + 1) : val;
}

function walkJsonMetadata(node, out) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const elem of node) walkJsonMetadata(elem, out);
    return;
  }
  for (const [k, v] of Object.entries(node)) {
    const keyLow = k.toLowerCase();
    if ((keyLow === "digitalsourcetype" || keyLow === "digital_source_type") && typeof v === "string") {
      appendUnique(out.digital_source_types, v);
      if (IPTC_CANONICAL_RE.test(v.trim())) {
        appendUnique(out.canonical_iptc_uris, v.trim());
      }
    } else if ((keyLow === "claim_generator" || keyLow === "softwareagent") && typeof v === "string") {
      appendUnique(out.claim_generators, v);
    } else if (keyLow === "claim_generator_info") {
      const list = Array.isArray(v) ? v : [v];
      for (const item of list) {
        if (item && typeof item === "object" && typeof item.name === "string") {
          const ver = String(item.version || "").trim();
          appendUnique(out.claim_generators, ver ? `${item.name}/${ver}` : item.name);
        }
      }
    } else {
      walkJsonMetadata(v, out);
    }
  }
}

function scanPayloadMetadata(payload, out) {
  if (!payload || payload.length === 0) return;
  const text = UTF8_DECODER.decode(payload);

  for (const m of text.matchAll(IPTC_URI_GLOBAL_RE)) {
    appendUnique(out.digital_source_types, m[0]);
    appendUnique(out.canonical_iptc_uris, m[0]);
  }

  const trimmed = text.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      walkJsonMetadata(parsed, out);
    } catch {
      // CBOR or partial payload; regex scan below handles text strings
    }
  }

  for (const m of text.matchAll(BARE_DST_GLOBAL_RE)) {
    const cand = m[1].trim();
    if (cand) {
      appendUnique(out.digital_source_types, cand);
      if (IPTC_CANONICAL_RE.test(cand)) {
        appendUnique(out.canonical_iptc_uris, cand);
      }
    }
  }

  for (const m of text.matchAll(CLAIM_GEN_GLOBAL_RE)) {
    appendUnique(out.claim_generators, m[1]);
  }

  let asciiView = "";
  for (let i = 0; i < payload.length; i += 1) {
    const b = payload[i];
    asciiView += b >= 32 && b <= 126 ? String.fromCharCode(b) : "\n";
  }
  for (const m of asciiView.matchAll(PRINTABLE_GEN_RE)) {
    appendUnique(out.claim_generators, m[1].trim());
  }
}

function createEmptyJumbfResult() {
  return {
    boxes: [],
    labels: [],
    uuids: [],
    digital_source_types: [],
    canonical_iptc_uris: [],
    claim_generators: [],
    has_c2pa_manifest_store: false,
    has_assertions: false,
    has_actions: false,
    has_claim: false,
    has_signature: false,
    signature_byte_length: 0,
    signature_hex_preview: "",
    parse_warnings: [],
  };
}

export function parseJumbfBoxes(inputBuf, { baseOffset = 0, depth = 0, result = null } = {}) {
  const buf = toUint8Array(inputBuf);
  const out = result || createEmptyJumbfResult();
  if (depth > 12) {
    out.parse_warnings.push("Maximum JUMBF nesting depth (12) exceeded.");
    return out;
  }

  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let pos = 0;
  const total = buf.length;

  while (pos + 8 <= total) {
    const lbox = dv.getUint32(pos, false);
    const tboxRaw = buf.subarray(pos + 4, pos + 8);
    if (!isPrintableFourcc(tboxRaw)) break;
    const tbox = safeFourcc(tboxRaw);
    let headerLen = 8;
    let boxSize = lbox;

    if (lbox === 1) {
      if (pos + 16 > total) {
        out.parse_warnings.push(`Truncated 64-bit XLBox header at offset ${baseOffset + pos}.`);
        break;
      }
      const hi = dv.getUint32(pos + 8, false);
      const lo = dv.getUint32(pos + 12, false);
      boxSize = hi * 0x100000000 + lo;
      headerLen = 16;
    } else if (lbox === 0) {
      boxSize = total - pos;
    }

    if (boxSize < headerLen) {
      out.parse_warnings.push(`Invalid BMFF/JUMBF box size ${boxSize} for '${tbox}' at ${baseOffset + pos}.`);
      break;
    }

    let boxEnd = pos + boxSize;
    if (boxEnd > total) {
      out.parse_warnings.push(
        `Truncated JUMBF box '${tbox}' at offset ${baseOffset + pos} (declared ${boxSize}B, available ${total - pos}B).`
      );
      boxEnd = total;
    }

    const payload = buf.subarray(pos + headerLen, boxEnd);

    if (tbox === "jumb") {
      let boxUuid = "";
      let boxLabel = "";
      if (payload.length >= 8 && safeFourcc(payload.subarray(4, 8)) === "jumd") {
        const pDv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
        const jumdLen = pDv.getUint32(0, false);
        if (jumdLen >= 25 && jumdLen <= payload.length) {
          boxUuid = formatUuidBytes(payload.subarray(8, 24));
          appendUnique(out.uuids, boxUuid);
          const toggles = payload[24];
          if (toggles & 0x02) {
            let nulIdx = -1;
            for (let k = 25; k < jumdLen; k += 1) {
              if (payload[k] === 0) {
                nulIdx = k;
                break;
              }
            }
            const lblSlice = nulIdx !== -1 ? payload.subarray(25, nulIdx) : payload.subarray(25, jumdLen);
            boxLabel = UTF8_DECODER.decode(lblSlice);
          }
          if (boxLabel) appendUnique(out.labels, boxLabel);
        }
      }

      const lowLabel = boxLabel.toLowerCase();
      if (lowLabel === "c2pa" || boxUuid === C2PA_STORE_UUID_STR) {
        out.has_c2pa_manifest_store = true;
      }
      if (lowLabel.startsWith("c2pa.assertions")) out.has_assertions = true;
      if (lowLabel.startsWith("c2pa.actions")) out.has_actions = true;
      if (lowLabel.startsWith("c2pa.claim")) out.has_claim = true;
      if (lowLabel.startsWith("c2pa.signature") || boxUuid === C2PA_SIGNATURE_UUID_STR) {
        let sigBody = payload;
        if (payload.length >= 8 && safeFourcc(payload.subarray(4, 8)) === "jumd") {
          const pDv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
          const jdLen = pDv.getUint32(0, false);
          if (jdLen <= payload.length) sigBody = payload.subarray(jdLen);
        }
        const rawSig =
          sigBody.length >= 8 && isPrintableFourcc(sigBody.subarray(4, 8)) ? sigBody.subarray(8) : sigBody;
        if (rawSig.length >= 16) {
          out.has_signature = true;
          out.signature_byte_length = rawSig.length;
          if (!out.signature_hex_preview) {
            out.signature_hex_preview = bytesToHex(rawSig.subarray(0, 16));
          }
        }
      }

      out.boxes.push({
        box_type: "jumb",
        uuid: boxUuid,
        label: boxLabel,
        offset: baseOffset + pos,
        length: boxEnd - pos,
        depth,
      });

      parseJumbfBoxes(payload, {
        baseOffset: baseOffset + pos + headerLen,
        depth: depth + 1,
        result: out,
      });
    } else if (tbox === "jumd") {
      if (depth === 0 && payload.length >= 17) {
        const boxUuid = formatUuidBytes(payload.subarray(0, 16));
        appendUnique(out.uuids, boxUuid);
        const toggles = payload[16];
        let boxLabel = "";
        if (toggles & 0x02) {
          let nulIdx = -1;
          for (let k = 17; k < payload.length; k += 1) {
            if (payload[k] === 0) {
              nulIdx = k;
              break;
            }
          }
          const lblSlice = nulIdx !== -1 ? payload.subarray(17, nulIdx) : payload.subarray(17);
          boxLabel = UTF8_DECODER.decode(lblSlice);
          if (boxLabel) appendUnique(out.labels, boxLabel);
        }
        out.boxes.push({
          box_type: "jumd",
          uuid: boxUuid,
          label: boxLabel,
          offset: baseOffset + pos,
          length: boxEnd - pos,
          depth,
        });
      }
    } else {
      out.boxes.push({
        box_type: tbox,
        uuid: "",
        label: "",
        offset: baseOffset + pos,
        length: boxEnd - pos,
        depth,
      });
      if (tbox === "c2cs" && payload.length >= 16) {
        out.has_signature = true;
        out.signature_byte_length = Math.max(out.signature_byte_length, payload.length);
        if (!out.signature_hex_preview) {
          out.signature_hex_preview = bytesToHex(payload.subarray(0, 16));
        }
      }
      scanPayloadMetadata(payload, out);
    }

    pos = boxEnd;
  }

  return out;
}

function locateJumbfStartInUuidPayload(uuidPayload) {
  if (uuidPayload.length >= 8 && safeFourcc(uuidPayload.subarray(4, 8)) === "jumb") {
    return 0;
  }
  const dv = new DataView(uuidPayload.buffer, uuidPayload.byteOffset, uuidPayload.byteLength);
  for (let i = 4; i + 4 <= uuidPayload.length; i += 1) {
    if (
      uuidPayload[i] === 0x6a &&
      uuidPayload[i + 1] === 0x75 &&
      uuidPayload[i + 2] === 0x6d &&
      uuidPayload[i + 3] === 0x62
    ) {
      const declared = dv.getUint32(i - 4, false);
      const remaining = uuidPayload.length - (i - 4);
      if (declared === 0 || declared === 1 || (declared >= 8 && declared <= remaining)) {
        return i - 4;
      }
    }
  }
  return null;
}

export function inspectMediaBytes(rawInput) {
  const buf = toUint8Array(rawInput);
  const byteLength = buf.length;
  const digestBytes = sha256Bytes(buf);
  const sha256Hex = bytesToHex(digestBytes);
  const contentDigestHeader = `sha-256=:${bytesToBase64(digestBytes)}:`;

  const segments = [];
  const crcErrors = [];
  const jumbfRes = createEmptyJumbfResult();
  let containerFormat = "unknown";
  let mimeType = "application/octet-stream";
  let c2paCarrier = null;
  let legacyMetadataPresent = false;
  let hasC2paChunk = false;

  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);

  if (startsWithBytes(buf, PNG_SIGNATURE)) {
    containerFormat = "png";
    mimeType = "image/png";
    segments.push({
      kind: "PNG_SIG",
      offset: 0,
      length: 8,
      is_c2pa: false,
      crc_valid: null,
      detail: "89 50 4E 47 0D 0A 1A 0A",
    });
    let pos = 8;
    while (pos + 12 <= byteLength) {
      const chunkLen = dv.getUint32(pos, false);
      const chunkType = safeFourcc(buf.subarray(pos + 4, pos + 8));
      const totalChunk = 12 + chunkLen;
      if (pos + totalChunk > byteLength) {
        jumbfRes.parse_warnings.push(
          `Truncated PNG chunk '${chunkType}' at offset ${pos} (declared ${chunkLen}B data).`
        );
        segments.push({
          kind: chunkType,
          offset: pos,
          length: byteLength - pos,
          is_c2pa: chunkType === "caBX",
          crc_valid: false,
          detail: "truncated",
        });
        break;
      }

      const chunkData = buf.subarray(pos + 8, pos + 8 + chunkLen);
      const expectedCrc = dv.getUint32(pos + 8 + chunkLen, false);
      const computedCrc = crc32Bytes(buf.subarray(pos + 4, pos + 8 + chunkLen));
      const crcOk = expectedCrc === computedCrc;
      if (!crcOk) {
        crcErrors.push(
          `PNG chunk '${chunkType}' at offset ${pos} failed CRC-32 (expected 0x${expectedCrc.toString(16).padStart(8, "0")}, got 0x${computedCrc.toString(16).padStart(8, "0")}).` /* taste-skill-ignore: CRC hex formatting */
        );
      }

      const isC2pa = chunkType === "caBX";
      if (chunkType === "eXIf" || chunkType === "tEXt" || chunkType === "iTXt" || chunkType === "zTXt") {
        legacyMetadataPresent = true;
      }
      if (isC2pa) {
        hasC2paChunk = true;
        c2paCarrier = "caBX";
        parseJumbfBoxes(chunkData, { baseOffset: pos + 8, result: jumbfRes });
      }

      segments.push({
        kind: chunkType,
        offset: pos,
        length: totalChunk,
        is_c2pa: isC2pa,
        crc_valid: crcOk,
        detail: `data=${chunkLen}B`,
      });
      pos += totalChunk;
      if (chunkType === "IEND") break;
    }
  } else if (byteLength >= 2 && buf[0] === 0xff && buf[1] === 0xd8) {
    containerFormat = "jpeg";
    mimeType = "image/jpeg";
    segments.push({
      kind: "SOI",
      offset: 0,
      length: 2,
      is_c2pa: false,
      crc_valid: null,
      detail: "0xFFD8",
    });
    let pos = 2;
    const app11Packets = new Map();

    while (pos + 2 <= byteLength) {
      if (buf[pos] !== 0xff) {
        let nextFf = -1;
        for (let k = pos; k < byteLength; k += 1) {
          if (buf[k] === 0xff) {
            nextFf = k;
            break;
          }
        }
        if (nextFf === -1) break;
        pos = nextFf;
        continue;
      }

      const markerPos = pos;
      while (pos + 1 < byteLength && buf[pos + 1] === 0xff) pos += 1;
      if (pos + 1 >= byteLength) break;
      const marker = buf[pos + 1];

      if (marker === 0xd9) {
        segments.push({
          kind: "EOI",
          offset: markerPos,
          length: pos + 2 - markerPos,
          is_c2pa: false,
          crc_valid: null,
          detail: "0xFFD9",
        });
        break;
      }
      if (marker === 0x00 || (marker >= 0xd0 && marker <= 0xd8) || marker === 0x01) {
        pos += 2;
        continue;
      }
      if (pos + 4 > byteLength) {
        jumbfRes.parse_warnings.push(`Truncated JPEG marker 0xFF${marker.toString(16).toUpperCase()} at offset ${markerPos}.`);
        break;
      }

      const segLen = dv.getUint16(pos + 2, false);
      if (segLen < 2 || pos + 2 + segLen > byteLength) {
        jumbfRes.parse_warnings.push(
          `Invalid or truncated JPEG marker 0xFF${marker.toString(16).toUpperCase()} length ${segLen} at offset ${markerPos}.`
        );
        break;
      }

      const segPayload = buf.subarray(pos + 4, pos + 2 + segLen);
      const totalSegLen = pos + 2 + segLen - markerPos;

      if (marker === 0xeb) {
        hasC2paChunk = true;
        c2paCarrier = "APP11";
        let detail = "0xFFEB raw JUMBF";
        if (segPayload.length >= 8 && segPayload[0] === 0x4a && segPayload[1] === 0x50) {
          const pDv = new DataView(segPayload.buffer, segPayload.byteOffset, segPayload.byteLength);
          const en = pDv.getUint16(2, false);
          const zSeq = pDv.getUint32(4, false);
          if (!app11Packets.has(en)) app11Packets.set(en, []);
          app11Packets.get(en).push({ z: zSeq, offset: pos + 12, bytes: segPayload.subarray(8) });
          detail = `0xFFEB JP En=${en} Z=${zSeq}`;
        } else {
          parseJumbfBoxes(segPayload, { baseOffset: pos + 4, result: jumbfRes });
        }
        segments.push({
          kind: "APP11",
          offset: markerPos,
          length: totalSegLen,
          is_c2pa: true,
          crc_valid: null,
          detail,
        });
      } else {
        if (marker === 0xe1 && segPayload.length >= 6) {
          const headStr = UTF8_DECODER.decode(segPayload.subarray(0, Math.min(64, segPayload.length)));
          if (headStr.startsWith("Exif\x00\x00") || headStr.includes("ns.adobe.com/xap")) {
            legacyMetadataPresent = true;
          }
        }
        const markerName =
          marker >= 0xe0 && marker <= 0xef
            ? `APP${marker - 0xe0}`
            : marker === 0xda
              ? "SOS"
              : `0xFF${marker.toString(16).toUpperCase().padStart(2, "0")}`; /* taste-skill-ignore: hex marker */
        segments.push({
          kind: markerName,
          offset: markerPos,
          length: totalSegLen,
          is_c2pa: false,
          crc_valid: null,
          detail: `len=${segLen}B`,
        });
      }

      pos = pos + 2 + segLen;
      if (marker === 0xda) {
        let eoiPos = -1;
        for (let k = byteLength - 2; k >= pos; k -= 1) {
          if (buf[k] === 0xff && buf[k + 1] === 0xd9) {
            eoiPos = k;
            break;
          }
        }
        if (eoiPos !== -1) {
          if (eoiPos > pos) {
            segments.push({
              kind: "SCAN",
              offset: pos,
              length: eoiPos - pos,
              is_c2pa: false,
              crc_valid: null,
              detail: "entropy-coded scan",
            });
          }
          segments.push({
            kind: "EOI",
            offset: eoiPos,
            length: 2,
            is_c2pa: false,
            crc_valid: null,
            detail: "0xFFD9",
          });
        }
        break;
      }
    }

    const sortedEns = [...app11Packets.keys()].sort((a, b) => a - b);
    for (const en of sortedEns) {
      const packets = app11Packets.get(en).sort((a, b) => a.z - b.z);
      if (packets.length === 1) {
        parseJumbfBoxes(packets[0].bytes, { baseOffset: packets[0].offset, result: jumbfRes });
      } else {
        const firstBytes = packets[0].bytes;
        const hasJumbHdr = firstBytes.length >= 8 && safeFourcc(firstBytes.subarray(4, 8)) === "jumb";
        const firstHdr = hasJumbHdr ? firstBytes.subarray(0, 8) : null;
        const slices = [firstBytes];
        for (let idx = 1; idx < packets.length; idx += 1) {
          const pBytes = packets[idx].bytes;
          if (firstHdr && pBytes.length >= 8 && bytesEqual(pBytes.subarray(0, 8), firstHdr)) {
            slices.push(pBytes.subarray(8));
          } else {
            slices.push(pBytes);
          }
        }
        const combined = concatBytes(slices);
        if (combined.length >= 8 && safeFourcc(combined.subarray(4, 8)) === "jumb") {
          const cDv = new DataView(combined.buffer, combined.byteOffset, combined.byteLength);
          const declaredLbox = cDv.getUint32(0, false);
          if (declaredLbox !== 1 && declaredLbox !== combined.length) {
            cDv.setUint32(0, combined.length, false);
          }
        }
        parseJumbfBoxes(combined, { baseOffset: packets[0].offset, result: jumbfRes });
      }
    }
  } else if (
    byteLength >= 12 &&
    safeFourcc(buf.subarray(0, 4)) === "RIFF" &&
    safeFourcc(buf.subarray(8, 12)) === "WEBP"
  ) {
    containerFormat = "webp";
    mimeType = "image/webp";
    const riffSize = dv.getUint32(4, true);
    segments.push({
      kind: "RIFF_WEBP",
      offset: 0,
      length: 12,
      is_c2pa: false,
      crc_valid: null,
      detail: `riff_size=${riffSize}B`,
    });
    let pos = 12;
    while (pos + 8 <= byteLength) {
      const fourcc = safeFourcc(buf.subarray(pos, pos + 4));
      const chunkSize = dv.getUint32(pos + 4, true);
      const dataEnd = pos + 8 + chunkSize;
      const paddedEnd = dataEnd + (chunkSize & 1);
      if (dataEnd > byteLength) {
        jumbfRes.parse_warnings.push(`Truncated WebP RIFF chunk '${fourcc}' at offset ${pos} (declared ${chunkSize}B).`);
        break;
      }
      const chunkData = buf.subarray(pos + 8, dataEnd);
      const isC2pa = fourcc === "C2PA" || fourcc === "caBX";
      if (fourcc === "EXIF" || fourcc === "XMP ") legacyMetadataPresent = true;
      if (isC2pa) {
        hasC2paChunk = true;
        c2paCarrier = fourcc;
        parseJumbfBoxes(chunkData, { baseOffset: pos + 8, result: jumbfRes });
      }
      const nextPos = Math.min(paddedEnd, byteLength);
      segments.push({
        kind: fourcc,
        offset: pos,
        length: nextPos - pos,
        is_c2pa: isC2pa,
        crc_valid: null,
        detail: `data=${chunkSize}B`,
      });
      pos = nextPos;
    }
  } else if (
    byteLength >= 8 &&
    isPrintableFourcc(buf.subarray(4, 8)) &&
    ISOBMFF_TOP_TYPES.has(safeFourcc(buf.subarray(4, 8)))
  ) {
    containerFormat = "mp4";
    mimeType = "video/mp4";
    let pos = 0;
    while (pos + 8 <= byteLength) {
      const size32 = dv.getUint32(pos, false);
      const btypeRaw = buf.subarray(pos + 4, pos + 8);
      if (!isPrintableFourcc(btypeRaw)) break;
      const btype = safeFourcc(btypeRaw);
      let hdrLen = 8;
      let boxSize = size32;
      if (size32 === 1) {
        if (pos + 16 > byteLength) {
          jumbfRes.parse_warnings.push(`Truncated 64-bit ISOBMFF box '${btype}' at offset ${pos}.`);
          break;
        }
        const hi = dv.getUint32(pos + 8, false);
        const lo = dv.getUint32(pos + 12, false);
        boxSize = hi * 0x100000000 + lo;
        hdrLen = 16;
      } else if (size32 === 0) {
        boxSize = byteLength - pos;
      }

      if (boxSize < hdrLen) {
        jumbfRes.parse_warnings.push(`Invalid ISOBMFF box '${btype}' size ${boxSize} at offset ${pos}.`);
        break;
      }
      const boxEnd = Math.min(pos + boxSize, byteLength);
      if (pos + boxSize > byteLength) {
        jumbfRes.parse_warnings.push(
          `Truncated ISOBMFF box '${btype}' at offset ${pos} (declared ${boxSize}B, available ${byteLength - pos}B).`
        );
      }

      const payload = buf.subarray(pos + hdrLen, boxEnd);
      let isC2pa = false;
      let detail = `size=${boxEnd - pos}B`;
      if (btype === "uuid" && payload.length >= 16) {
        const rawUuid = payload.subarray(0, 16);
        detail = `uuid=${formatUuidBytes(rawUuid)}`;
        if (bytesEqual(rawUuid, C2PA_ISOBMFF_UUID_BYTES)) {
          isC2pa = true;
          hasC2paChunk = true;
          c2paCarrier = "uuid";
          const uuidInner = payload.subarray(16);
          const jumbRel = locateJumbfStartInUuidPayload(uuidInner);
          if (jumbRel !== null) {
            parseJumbfBoxes(uuidInner.subarray(jumbRel), {
              baseOffset: pos + hdrLen + 16 + jumbRel,
              result: jumbfRes,
            });
          } else {
            jumbfRes.parse_warnings.push(
              "C2PA ISOBMFF uuid box present, but inner JUMBF 'jumb' box was not found."
            );
          }
        }
      } else if (btype === "meta" || btype === "udta") {
        legacyMetadataPresent = true;
      }

      segments.push({
        kind: btype,
        offset: pos,
        length: boxEnd - pos,
        is_c2pa: isC2pa,
        crc_valid: null,
        detail,
      });
      pos = boxEnd;
    }
  } else if (byteLength >= 8 && safeFourcc(buf.subarray(4, 8)) === "jumb") {
    containerFormat = "jumbf";
    mimeType = "application/x-c2pa-manifest-store";
    hasC2paChunk = true;
    c2paCarrier = "jumb";
    parseJumbfBoxes(buf, { baseOffset: 0, result: jumbfRes });
    segments.push({
      kind: "jumb",
      offset: 0,
      length: byteLength,
      is_c2pa: true,
      crc_valid: null,
      detail: "standalone JUMBF",
    });
  } else {
    jumbfRes.parse_warnings.push(
      "Unrecognized binary magic bytes (expected PNG, JPEG, WebP, MP4/ISOBMFF, or JUMBF stream)."
    );
  }

  const iptcCodes = [];
  for (const uriOrCode of jumbfRes.digital_source_types) {
    appendUnique(iptcCodes, extractIptcCode(uriOrCode));
  }

  const aiDetected = iptcCodes.some((c) => IPTC_AI_SOURCE_CODES.has(c));
  const captureAsserted = iptcCodes.some((c) => IPTC_CAPTURE_SOURCE_CODES.has(c));
  const c2paPresent = Boolean(hasC2paChunk && (jumbfRes.has_c2pa_manifest_store || jumbfRes.labels.length > 0));
  const probableStripped = Boolean(
    ["png", "jpeg", "webp", "mp4"].includes(containerFormat) && !c2paPresent && !legacyMetadataPresent
  );

  return {
    container_format: containerFormat,
    mime_type: mimeType,
    byte_length: byteLength,
    sha256_hex: sha256Hex,
    content_digest_header: contentDigestHeader,
    c2pa_carrier: c2paCarrier,
    c2pa_present: c2paPresent,
    has_manifest_store: jumbfRes.has_c2pa_manifest_store,
    has_assertions: jumbfRes.has_assertions,
    has_actions: jumbfRes.has_actions,
    has_claim: jumbfRes.has_claim,
    has_signature: jumbfRes.has_signature,
    signature_byte_length: jumbfRes.signature_byte_length,
    signature_hex_preview: jumbfRes.signature_hex_preview,
    jumbf_labels: [...jumbfRes.labels],
    jumbf_boxes: [...jumbfRes.boxes],
    digital_source_types: [...jumbfRes.digital_source_types],
    canonical_iptc_uris: [...jumbfRes.canonical_iptc_uris],
    iptc_source_codes: iptcCodes,
    ai_source_type_detected: aiDetected,
    non_ai_capture_asserted: captureAsserted,
    claim_generators: [...jumbfRes.claim_generators],
    legacy_metadata_present: legacyMetadataPresent,
    probable_metadata_stripped: probableStripped,
    crc_errors: crcErrors,
    parse_warnings: [...jumbfRes.parse_warnings],
    segments,
  };
}

// ---------------------------------------------------------------------------
// Deterministic Binary C2PA Container Synthesizers (Byte-Exact with Python)
// ---------------------------------------------------------------------------

function uint32BE(val) {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, val >>> 0, false);
  return b;
}

function uint16BE(val) {
  const b = new Uint8Array(2);
  new DataView(b.buffer).setUint16(0, val & 0xffff, false);
  return b;
}

function uint32LE(val) {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, val >>> 0, true);
  return b;
}

function bmffBox(fourcc, payload) {
  const typeBytes = UTF8_ENCODER.encode(fourcc);
  return concatBytes([uint32BE(8 + payload.length), typeBytes, payload]);
}

function jumbfSuperbox(uuid16, label, children) {
  const lblBytes = UTF8_ENCODER.encode(label);
  const jumdPayload = concatBytes([uuid16, new Uint8Array([0x03]), lblBytes, new Uint8Array([0x00])]);
  const jumd = bmffBox("jumd", jumdPayload);
  return bmffBox("jumb", concatBytes([jumd, ...children]));
}

export function buildJumbfC2paStore({
  manifestUrn = "urn:uuid:2fc21dee-2026-4c50-9a50-c2pa00000050",
  digitalSourceType = `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
  claimGenerator = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
  softwareAgent = "GenStudio-Diffusion/4.2",
  includeSignature = true,
  includeActions = true,
} = {}) {
  const assertionBoxes = [];

  if (includeActions) {
    const actionEntry = {
      action: "c2pa.created",
      softwareAgent,
    };
    if (digitalSourceType) {
      actionEntry.digitalSourceType = digitalSourceType;
    }
    const actionsJson = UTF8_ENCODER.encode(JSON.stringify({ actions: [actionEntry] }));
    assertionBoxes.push(jumbfSuperbox(UUID_JUMBF_JSON, "c2pa.actions.v2", [bmffBox("json", actionsJson)]));
  }

  const cwDoc = {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    author: [{ "@type": "Organization", name: "peco-compliance-lab" }],
  };
  assertionBoxes.push(
    jumbfSuperbox(UUID_JUMBF_JSON, "stds.schema-org.CreativeWork", [bmffBox("json", UTF8_ENCODER.encode(JSON.stringify(cwDoc)))])
  );

  const assertionsStore = jumbfSuperbox(UUID_C2PA_ASSERTIONS, "c2pa.assertions", assertionBoxes);

  const claimDoc = {
    instanceID: "xmp:iid:c2pa-eu-ai-act50-demo",
    claim_generator: claimGenerator,
    claim_generator_info: [{ name: claimGenerator.split(" ")[0], version: "2.1" }],
    alg: "sha256",
  };
  const claimBox = jumbfSuperbox(UUID_C2PA_CLAIM, "c2pa.claim.v2", [
    bmffBox("json", UTF8_ENCODER.encode(JSON.stringify(claimDoc))),
  ]);

  const manifestChildren = [assertionsStore, claimBox];
  if (includeSignature) {
    const coseStub = concatBytes([
      hexToBytes("d28443a10126a0405834"),
      UTF8_ENCODER.encode("C2PAGATE-COSE-ES256-DEMO-SIGNATURE-PAYLOAD-BYTES-001"),
    ]);
    manifestChildren.push(jumbfSuperbox(UUID_C2PA_SIGNATURE, "c2pa.signature", [bmffBox("c2cs", coseStub)]));
  }

  const activeManifest = jumbfSuperbox(UUID_C2PA_MANIFEST, manifestUrn, manifestChildren);
  return jumbfSuperbox(UUID_C2PA_STORE, "c2pa", [activeManifest]);
}

function pngChunk(chunkType, chunkData) {
  const typeBytes = UTF8_ENCODER.encode(chunkType);
  const crcInput = concatBytes([typeBytes, chunkData]);
  const crc = crc32Bytes(crcInput);
  return concatBytes([uint32BE(chunkData.length), typeBytes, chunkData, uint32BE(crc)]);
}

export function synthesizePngBytes({
  includeC2pa = true,
  digitalSourceType = `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
  claimGenerator = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
  includeSignature = true,
  includeLegacyText = false,
} = {}) {
  const ihdr = new Uint8Array([0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0]);
  const parts = [PNG_SIGNATURE, pngChunk("IHDR", ihdr)];

  if (includeLegacyText) {
    parts.push(pngChunk("tEXt", UTF8_ENCODER.encode("Software\x00ImagePipeline/1.0")));
  }
  if (includeC2pa) {
    const jumbf = buildJumbfC2paStore({ digitalSourceType, claimGenerator, includeSignature });
    parts.push(pngChunk("caBX", jumbf));
  }
  parts.push(pngChunk("IDAT", PNG_1X1_IDAT_ZLIB));
  parts.push(pngChunk("IEND", new Uint8Array(0)));
  return concatBytes(parts);
}

function jpegSegment(markerByte, payload) {
  return concatBytes([new Uint8Array([0xff, markerByte]), uint16BE(2 + payload.length), payload]);
}

export function synthesizeJpegBytes({
  includeC2pa = true,
  multiSegmentApp11 = false,
  digitalSourceType = `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
  claimGenerator = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
  includeSignature = true,
} = {}) {
  const parts = [
    new Uint8Array([0xff, 0xd8]),
    jpegSegment(0xe0, hexToBytes("4a46494600010100000100010000")),
  ];

  if (includeC2pa) {
    const jumbf = buildJumbfC2paStore({ digitalSourceType, claimGenerator, includeSignature });
    if (multiSegmentApp11 && jumbf.length > 64) {
      const mid = Math.floor(jumbf.length / 2);
      const pkt1 = concatBytes([UTF8_ENCODER.encode("JP"), uint16BE(1), uint32BE(1), jumbf.subarray(0, mid)]);
      const pkt2 = concatBytes([
        UTF8_ENCODER.encode("JP"),
        uint16BE(1),
        uint32BE(2),
        jumbf.subarray(0, 8),
        jumbf.subarray(mid),
      ]);
      parts.push(jpegSegment(0xeb, pkt1));
      parts.push(jpegSegment(0xeb, pkt2));
    } else {
      const pkt = concatBytes([UTF8_ENCODER.encode("JP"), uint16BE(1), uint32BE(1), jumbf]);
      parts.push(jpegSegment(0xeb, pkt));
    }
  }

  parts.push(jpegSegment(0xc0, hexToBytes("080001000101011100")));
  parts.push(jpegSegment(0xda, hexToBytes("010100003f00")));
  parts.push(hexToBytes("7fffd9"));
  return concatBytes(parts);
}

function riffChunk(fourcc, data) {
  const pad = data.length & 1 ? new Uint8Array([0x00]) : new Uint8Array(0);
  return concatBytes([UTF8_ENCODER.encode(fourcc), uint32LE(data.length), data, pad]);
}

export function synthesizeWebpBytes({
  includeC2pa = true,
  digitalSourceType = `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
  claimGenerator = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
  includeSignature = true,
} = {}) {
  const vp8x = riffChunk("VP8X", new Uint8Array(10));
  const vp8l = riffChunk("VP8L", hexToBytes("2f000000000710fd8f00"));
  const bodyParts = [UTF8_ENCODER.encode("WEBP"), vp8x, vp8l];

  if (includeC2pa) {
    const jumbf = buildJumbfC2paStore({ digitalSourceType, claimGenerator, includeSignature });
    bodyParts.push(riffChunk("C2PA", jumbf));
  }

  const riffBody = concatBytes(bodyParts);
  return concatBytes([UTF8_ENCODER.encode("RIFF"), uint32LE(riffBody.length), riffBody]);
}

export function synthesizeMp4Bytes({
  includeC2pa = true,
  digitalSourceType = `${IPTC_URI_PREFIX_HTTP}compositeWithTrainedAlgorithmicMedia`,
  claimGenerator = "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
  includeSignature = true,
} = {}) {
  const ftyp = bmffBox(
    "ftyp",
    concatBytes([UTF8_ENCODER.encode("isom"), hexToBytes("00000200"), UTF8_ENCODER.encode("isomiso2mp41")])
  );
  const boxes = [ftyp];

  if (includeC2pa) {
    const jumbf = buildJumbfC2paStore({
      digitalSourceType,
      claimGenerator,
      softwareAgent: "GenVideo-Diffusion/2.0",
      includeSignature,
    });
    const uuidPayload = concatBytes([
      C2PA_ISOBMFF_UUID_BYTES,
      new Uint8Array(4),
      UTF8_ENCODER.encode("manifest\x00"),
      new Uint8Array(8),
      jumbf,
    ]);
    boxes.push(bmffBox("uuid", uuidPayload));
  }

  boxes.push(bmffBox("moov", bmffBox("mvhd", new Uint8Array(24))));
  boxes.push(bmffBox("mdat", hexToBytes("0000000109100000")));
  return concatBytes(boxes);
}

export function synthesizeMediaFromSpec(spec) {
  const fmt = String(spec?.format || "png").trim().toLowerCase();
  const includeC2pa = spec?.include_c2pa !== undefined ? Boolean(spec.include_c2pa) : true;
  const dst =
    spec?.digital_source_type !== undefined
      ? String(spec.digital_source_type)
      : `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`;
  const claimGen = String(spec?.claim_generator || "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0");
  const includeSig = spec?.include_signature !== undefined ? Boolean(spec.include_signature) : true;

  if (fmt === "png") {
    return synthesizePngBytes({
      includeC2pa,
      digitalSourceType: dst,
      claimGenerator: claimGen,
      includeSignature: includeSig,
      includeLegacyText: Boolean(spec?.include_legacy_text),
    });
  }
  if (fmt === "jpeg" || fmt === "jpg") {
    return synthesizeJpegBytes({
      includeC2pa,
      multiSegmentApp11: Boolean(spec?.multi_segment_app11),
      digitalSourceType: dst,
      claimGenerator: claimGen,
      includeSignature: includeSig,
    });
  }
  if (fmt === "webp") {
    return synthesizeWebpBytes({
      includeC2pa,
      digitalSourceType: dst,
      claimGenerator: claimGen,
      includeSignature: includeSig,
    });
  }
  if (fmt === "mp4" || fmt === "isobmff" || fmt === "m4a" || fmt === "mov") {
    return synthesizeMp4Bytes({
      includeC2pa,
      digitalSourceType: dst,
      claimGenerator: claimGen,
      includeSignature: includeSig,
    });
  }
  throw new ComplianceParseError(`Unsupported synthetic_media format: '${fmt}'`);
}

// ---------------------------------------------------------------------------
// JSONC Comment Stripping & 10-Gate EU AI Act Art. 50 + JP Safety Auditor
// ---------------------------------------------------------------------------

export function stripJsoncComments(rawText) {
  let out = "";
  let i = 0;
  const n = rawText.length;
  let inString = false;
  let escape = false;

  while (i < n) {
    const ch = rawText[i];
    if (inString) {
      out += ch;
      if (escape) {
        escape = false;
      } else if (ch === "\\") {
        escape = true;
      } else if (ch === '"') {
        inString = false;
      }
      i += 1;
      continue;
    }

    if (ch === '"') {
      inString = true;
      out += ch;
      i += 1;
      continue;
    }

    if (ch === "/" && i + 1 < n && rawText[i + 1] === "/") {
      i += 2;
      while (i < n && rawText[i] !== "\n" && rawText[i] !== "\r") i += 1;
      continue;
    }

    if (ch === "/" && i + 1 < n && rawText[i + 1] === "*") {
      const endIdx = rawText.indexOf("*/", i + 2);
      if (endIdx === -1) {
        throw new ComplianceParseError("Unterminated block comment in JSONC input.");
      }
      i = endIdx + 2;
      continue;
    }

    out += ch;
    i += 1;
  }

  let res = "";
  i = 0;
  inString = false;
  escape = false;
  while (i < out.length) {
    const ch = out[i];
    if (inString) {
      res += ch;
      if (escape) escape = false;
      else if (ch === "\\") escape = true;
      else if (ch === '"') inString = false;
      i += 1;
      continue;
    }
    if (ch === '"') {
      inString = true;
      res += ch;
      i += 1;
      continue;
    }
    if (ch === ",") {
      let j = i + 1;
      while (j < out.length && (out[j] === " " || out[j] === "\t" || out[j] === "\r" || out[j] === "\n")) j += 1;
      if (j < out.length && (out[j] === "}" || out[j] === "]")) {
        i += 1;
        continue;
      }
    }
    res += ch;
    i += 1;
  }
  return res;
}

function normalizeHeaders(rawHeaders) {
  const normalized = {};
  if (rawHeaders && typeof rawHeaders === "object" && !Array.isArray(rawHeaders)) {
    for (const [k, v] of Object.entries(rawHeaders)) {
      const key = String(k).trim().toLowerCase();
      if (!key) continue;
      const val = Array.isArray(v) ? v.map((x) => String(x)).join(", ") : String(v).trim();
      normalized[key] = normalized[key] ? `${normalized[key]}, ${val}` : val;
    }
  } else if (typeof rawHeaders === "string") {
    for (const line of rawHeaders.split(/\r?\n/)) {
      const stripped = line.trim();
      if (!stripped || stripped.toUpperCase().startsWith("HTTP/")) continue;
      const idx = stripped.indexOf(":");
      if (idx !== -1) {
        const key = stripped.slice(0, idx).trim().toLowerCase();
        const val = stripped.slice(idx + 1).trim();
        normalized[key] = normalized[key] ? `${normalized[key]}, ${val}` : val;
      }
    }
  }
  return normalized;
}

const LINK_C2PA_RE = /<([^>]+)>\s*;\s*[^,]*\brel\s*=\s*"?(?:c2pa-manifest|https?:\/\/c2pa\.org\/manifest)"?/i;
const SCRIPT_LD_JSON_RE = /<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
const META_AI_RE = /(?:<meta\b[^>]+name\s*=\s*["'](?:ai-generated|digital-source-type|c2pa-manifest)["']|itemprop\s*=\s*["']digitalSourceType["']|data-ai-generated\s*=\s*["']true["'])/i;
const HUMAN_IMPERSONATION_RE = /(?:you are speaking with a live human|100%\s*human\s*agent|not an ai assistant|人間が直接対応しています|AIではありません)/i;

function extractJsonldObjects(htmlSnippet, explicitJsonld) {
  const docs = [];
  const errors = [];

  const collect = (parsed) => {
    if (!parsed || typeof parsed !== "object") return;
    if (Array.isArray(parsed)) {
      for (const item of parsed) {
        if (item && typeof item === "object" && !Array.isArray(item)) docs.push(item);
      }
    } else if (Array.isArray(parsed["@graph"])) {
      for (const node of parsed["@graph"]) {
        if (node && typeof node === "object" && !Array.isArray(node)) {
          const merged = { ...node };
          if (!("@context" in merged) && "@context" in parsed) {
            merged["@context"] = parsed["@context"];
          }
          docs.push(merged);
        }
      }
    } else {
      docs.push(parsed);
    }
  };

  if (explicitJsonld && typeof explicitJsonld === "object") {
    collect(explicitJsonld);
  } else if (typeof explicitJsonld === "string" && explicitJsonld.trim()) {
    try {
      collect(JSON.parse(explicitJsonld));
    } catch (err) {
      errors.push(`Invalid json_ld JSON syntax: ${err.message}`);
    }
  }

  if (htmlSnippet) {
    for (const m of htmlSnippet.matchAll(SCRIPT_LD_JSON_RE)) {
      const rawBlock = m[1].trim();
      if (!rawBlock) continue;
      try {
        collect(JSON.parse(rawBlock));
      } catch (err) {
        errors.push(`Invalid <script type='application/ld+json'> syntax: ${err.message}`);
      }
    }
  }

  return { docs, errors };
}

export function buildComplianceBundle({
  assetName,
  publicAssetUrl,
  manifestSidecarUrl,
  mimeType,
  contentDigest,
  digitalSourceTypeUri,
  claimGenerator,
  publisherName,
}) {
  const schemaType = mimeType.startsWith("video/") ? "VideoObject" : "ImageObject";

  const httpHeadersSnippet = [
    `Link: <${manifestSidecarUrl}>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"`,
    `Content-Digest: ${contentDigest}`,
    "Access-Control-Expose-Headers: Link, Content-Digest, X-AI-Provenance",
    `X-AI-Provenance: EU-AI-Act-Art50; digitalSourceType="${digitalSourceTypeUri}"`,
    "Cache-Control: public, max-age=31536000, no-transform",
  ].join("\n");

  const jsonldObj = {
    "@context": "https://schema.org",
    "@type": schemaType,
    name: assetName,
    contentUrl: publicAssetUrl,
    encodingFormat: mimeType,
    digitalSourceType: digitalSourceTypeUri,
    creditText: `AI-generated media signed with C2PA Content Credentials (${publisherName})`,
    creator: {
      "@type": "Organization",
      name: publisherName,
    },
    sdPublisher: {
      "@type": "Organization",
      name: publisherName,
    },
  };

  const schemaOrgScript = `<script type="application/ld+json">\n${JSON.stringify(jsonldObj, null, 2)}\n</script>`;

  const c2paManifestTemplate = {
    alg: "es256",
    ta_url: "http://timestamp.digicert.com",
    claim_generator_info: [
      {
        name: claimGenerator.split(" ")[0],
        version: "2.1.0",
      },
    ],
    title: assetName,
    format: mimeType,
    assertions: [
      {
        label: "c2pa.actions.v2",
        data: {
          actions: [
            {
              action: "c2pa.created",
              digitalSourceType: digitalSourceTypeUri,
              softwareAgent: {
                name: claimGenerator,
              },
            },
          ],
        },
      },
      {
        label: "stds.schema-org.CreativeWork",
        data: {
          "@context": "https://schema.org",
          "@type": "CreativeWork",
          author: [{ "@type": "Organization", name: publisherName }],
        },
      },
    ],
  };

  const edgePreservationConfig = [
    "# 1. Cloudflare Rules / Workers: disable lossy metadata stripping & attach C2PA Link header",
    "# Polish: Off (or 'Preserve Metadata' enabled); Cache-Control: no-transform",
    `add_header Link '<${manifestSidecarUrl}>; rel="c2pa-manifest"' always;`,
    "add_header Access-Control-Expose-Headers 'Link, Content-Digest, X-AI-Provenance' always;",
    "add_header Cache-Control 'public, max-age=31536000, no-transform' always;",
    "",
    "# 2. Next.js / Node.js sharp pipeline: preserve caBX / APP11 / C2PA / uuid & re-sign derivatives",
    "# await sharp(inputBuffer).keepMetadata().png().toBuffer(); // then run c2patool --parent",
  ].join("\n");

  return {
    target_deadline: EU_AI_ACT_ART50_SUNSET,
    jp_safety_revision: JP_AI_ACT_REVISION_TARGET,
    http_headers_snippet: httpHeadersSnippet,
    schema_org_jsonld: jsonldObj,
    schema_org_html_snippet: schemaOrgScript,
    c2pa_manifest_template: c2paManifestTemplate,
    edge_preservation_config: edgePreservationConfig,
  };
}

export function buildRemediatedBundleInput(rawBundle, inspection = null) {
  const remediated =
    rawBundle && typeof rawBundle === "object" && !Array.isArray(rawBundle)
      ? JSON.parse(JSON.stringify(rawBundle))
      : {};
  const asset = remediated.asset && typeof remediated.asset === "object" ? { ...remediated.asset } : {};

  let fmt = "png";
  if (inspection && ["png", "jpeg", "webp", "mp4"].includes(inspection.container_format)) {
    fmt = inspection.container_format;
  } else if (remediated.synthetic_media && typeof remediated.synthetic_media === "object") {
    const cand = String(remediated.synthetic_media.format || "png").toLowerCase();
    if (["png", "jpeg", "jpg", "webp", "mp4"].includes(cand)) {
      fmt = cand === "jpg" ? "jpeg" : cand;
    }
  }

  const defaultExt = fmt === "mp4" ? "mp4" : fmt === "jpeg" ? "jpg" : fmt;
  const assetName = String(asset.name || `campaign-hero.${defaultExt}`);
  let publicUrl = String(asset.public_url || `https://cdn.nordlicht-studio.eu/media/${assetName}`);
  if (publicUrl.startsWith("http://")) {
    publicUrl = `https://${publicUrl.slice("http://".length)}`;
  }
  let sidecarUrl = String(asset.manifest_sidecar_url || `${publicUrl}.c2pa`);
  if (sidecarUrl.startsWith("http://")) {
    sidecarUrl = `https://${sidecarUrl.slice("http://".length)}`;
  }

  const publisher = String(asset.publisher || "Nordlicht Studio GmbH");
  const defaultDst =
    fmt === "mp4"
      ? `${IPTC_URI_PREFIX_HTTP}compositeWithTrainedAlgorithmicMedia`
      : `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`;
  const dstUri =
    inspection && inspection.ai_source_type_detected && inspection.canonical_iptc_uris.length > 0
      ? inspection.canonical_iptc_uris[0]
      : defaultDst;

  asset.name = assetName;
  asset.is_ai_generated = true;
  asset.public_url = publicUrl;
  asset.manifest_sidecar_url = sidecarUrl;
  asset.publisher = publisher;
  remediated.asset = asset;

  remediated.synthetic_media = {
    format: fmt,
    include_c2pa: true,
    digital_source_type: dstUri,
    claim_generator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
    include_signature: true,
  };
  const synthInsp = inspectMediaBytes(synthesizeMediaFromSpec(remediated.synthetic_media));
  const digestHdr =
    inspection && inspection.c2pa_present && inspection.has_signature && !inspection.non_ai_capture_asserted
      ? inspection.content_digest_header
      : synthInsp.content_digest_header;
  const mimeType =
    inspection && inspection.container_format !== "unknown" ? inspection.mime_type : synthInsp.mime_type;

  remediated.http_headers = {
    Link: `<${sidecarUrl}>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"`,
    "Content-Digest": digestHdr,
    "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
    "Cache-Control": "public, max-age=31536000, no-transform",
  };

  const schemaType = mimeType.startsWith("video/") ? "VideoObject" : "ImageObject";
  remediated.json_ld = {
    "@context": "https://schema.org",
    "@type": schemaType,
    name: assetName,
    contentUrl: publicUrl,
    encodingFormat: mimeType,
    digitalSourceType: dstUri,
    creditText: `AI-generated media signed with C2PA Content Credentials (${publisher})`,
    creator: { "@type": "Organization", name: publisher },
    sdPublisher: { "@type": "Organization", name: publisher },
  };
  delete remediated.html_snippet;

  const gov = remediated.governance && typeof remediated.governance === "object" ? { ...remediated.governance } : {};
  const interactive = gov.interactive_ai && typeof gov.interactive_ai === "object" ? gov.interactive_ai : {};
  const appliesInteractive = interactive.applies !== undefined ? Boolean(interactive.applies) : true;
  gov.interactive_ai = {
    applies: appliesInteractive,
    pre_interaction_notice: true,
    clear_human_distinction: true,
    accessible_aria_disclosure: true,
    hidden_in_tos_only: false,
    impersonates_human: false,
  };

  const bio = gov.biometric_emotion && typeof gov.biometric_emotion === "object" ? gov.biometric_emotion : {};
  if (bio.enabled) {
    gov.biometric_emotion = {
      enabled: true,
      workplace_or_education_emotion_monitoring: false,
      explicit_prior_subject_notice: true,
      dpia_reference: String(bio.dpia_reference || "DPIA-2026-EU-ART50-03"),
      gdpr_appi_lawful_basis: String(bio.gdpr_appi_lawful_basis || "explicit_consent_art9_2_a"),
    };
  } else {
    gov.biometric_emotion = {
      enabled: false,
      workplace_or_education_emotion_monitoring: false,
    };
  }

  const df = gov.deepfake_and_text && typeof gov.deepfake_and_text === "object" ? gov.deepfake_and_text : {};
  gov.deepfake_and_text = {
    generates_synthetic_likeness_or_voice:
      df.generates_synthetic_likeness_or_voice !== undefined
        ? Boolean(df.generates_synthetic_likeness_or_voice)
        : fmt === "mp4",
    visible_deepfake_disclosure: true,
    publishes_public_interest_text:
      df.publishes_public_interest_text !== undefined ? Boolean(df.publishes_public_interest_text) : true,
    visible_ai_text_disclosure: true,
    human_editorial_review: true,
    editorial_responsibility_holder: String(
      df.editorial_responsibility_holder || `${publisher} Editorial Board`
    ),
    editorial_review_log_id: String(df.editorial_review_log_id || "ed-rev-2026-1123"),
  };

  gov.cdn_preservation = {
    strip_all_metadata: false,
    preserve_c2pa_chunks: true,
    re_sign_derivatives: true,
    immutable_origin_passthrough: true,
    soft_binding_sidecar_fallback: true,
  };

  const jp = gov.jp_ai_safety && typeof gov.jp_ai_safety === "object" ? gov.jp_ai_safety : {};
  let retention = Number(jp.retention_days || 365);
  if (!Number.isFinite(retention) || retention < 180) retention = 365;
  let slaHours = Number(jp.incident_reporting_sla_hours || 12);
  if (!Number.isFinite(slaHours) || slaHours < 1 || slaHours > 24) slaHours = 12;
  let haltSec = Number(jp.max_halt_latency_seconds || 15);
  if (!Number.isFinite(haltSec) || haltSec < 1 || haltSec > 60) haltSec = 15;

  gov.jp_ai_safety = {
    immutable_audit_log_enabled: true,
    retention_days: Math.trunc(retention),
    incident_reporting_sla_hours: Math.trunc(slaHours),
    safety_governance_role: String(jp.safety_governance_role || "CAIO & AI Safety Response Office"),
    kill_switch_enabled: true,
    kill_switch_mechanism: String(
      jp.kill_switch_mechanism || "edge-kv://ai-agent-circuit-breaker/global-halt"
    ),
    auto_circuit_breaker: true,
    max_halt_latency_seconds: Math.trunc(haltSec),
  };

  remediated.governance = gov;
  return remediated;
}

export function auditC2paText(rawText, { mediaBytes = null } = {}) {
  if (typeof rawText !== "string" || !rawText.trim()) {
    throw new ComplianceParseError("Compliance configuration text is empty.");
  }
  const stripped = stripJsoncComments(rawText);
  let parsed;
  try {
    parsed = JSON.parse(stripped);
  } catch (err) {
    throw new ComplianceParseError(`Invalid JSON: ${err.message}`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new ComplianceParseError("Root compliance configuration must be a JSON object.");
  }
  return auditC2paCompliance(parsed, { mediaBytes });
}

export function auditC2paCompliance(bundle = null, { mediaBytes = null } = {}) {
  if (bundle !== null && (typeof bundle !== "object" || Array.isArray(bundle))) {
    throw new ComplianceParseError("Audit bundle must be an object or null.");
  }

  const cfg = bundle || {};
  const asset = cfg.asset && typeof cfg.asset === "object" && !Array.isArray(cfg.asset) ? cfg.asset : {};
  const isAiGenerated = asset.is_ai_generated !== undefined ? Boolean(asset.is_ai_generated) : true;

  let actualBytes = null;
  if (mediaBytes !== null && mediaBytes !== undefined) {
    actualBytes = toUint8Array(mediaBytes);
  } else if (cfg.synthetic_media && typeof cfg.synthetic_media === "object") {
    actualBytes = synthesizeMediaFromSpec(cfg.synthetic_media);
  }

  const inspection = actualBytes !== null ? inspectMediaBytes(actualBytes) : null;
  const defaultExt = inspection && inspection.container_format !== "unknown" ? inspection.container_format : "bin";
  const assetName = String(asset.name || `uploaded-asset.${defaultExt}`);
  const headers = normalizeHeaders(cfg.http_headers);
  const htmlSnippet = String(cfg.html_snippet || "");
  const explicitJsonld = cfg.json_ld;
  const gov = cfg.governance && typeof cfg.governance === "object" && !Array.isArray(cfg.governance) ? cfg.governance : {};

  const gateResults = [];
  const allFindings = [];
  let rawScore = 0;

  const recordGate = (gateDef, status, summary, gateFindings) => {
    const weight = gateDef.weight;
    if (status === "pass") rawScore += weight;
    else if (status === "warn") rawScore += Math.floor(weight / 2);

    for (const f of gateFindings) allFindings.push(f);
    gateResults.push({
      gate_number: gateDef.gate_number,
      gate_id: gateDef.gate_id,
      title: gateDef.title,
      statutory_ref: gateDef.statutory_ref,
      weight,
      severity: gateDef.default_severity,
      status,
      summary,
      findings_count: gateFindings.length,
      findings: gateFindings,
    });
  };

  // Gate 1: Embedded C2PA JUMBF
  const g1Findings = [];
  if (inspection === null) {
    if (asset.detached_c2pa_only) {
      g1Findings.push({
        gate_id: "C2PA-50-01",
        severity: "medium",
        title: "Detached C2PA manifest mode without binary stream verification",
        evidence: `asset '${assetName}' supplied no binary stream; detached_c2pa_only=true.`,
        remediation:
          "Embed a JUMBF Manifest Store (`caBX`, `APP11`, `C2PA`, or ISOBMFF `uuid`) directly in the media container alongside detached headers.",
      });
      recordGate(
        GATE_DEFINITIONS[0],
        "warn",
        "No media bytes supplied; relying solely on detached manifest declaration.",
        g1Findings
      );
    } else {
      g1Findings.push({
        gate_id: "C2PA-50-01",
        severity: "critical",
        title: "No embedded C2PA JUMBF media bytes provided or detected",
        evidence: `asset '${assetName}' has no inspected binary container.`,
        remediation: "Sign output media with `c2patool` or `c2pa-rs` to embed an ISO/IEC 19566-5 JUMBF superbox.",
      });
      recordGate(
        GATE_DEFINITIONS[0],
        "fail",
        "Missing media binary container with embedded C2PA Content Credentials.",
        g1Findings
      );
    }
  } else {
    for (const crcErr of inspection.crc_errors) {
      g1Findings.push({
        gate_id: "C2PA-50-01",
        severity: "critical",
        title: "Container chunk CRC-32 integrity failure",
        evidence: crcErr,
        remediation: "Re-generate and re-sign the PNG `caBX` chunk so container CRCs and COSE hashes validate.",
      });
    }
    if (!inspection.c2pa_present || !inspection.has_manifest_store) {
      g1Findings.push({
        gate_id: "C2PA-50-01",
        severity: "critical",
        title: "Missing embedded C2PA JUMBF Manifest Store in binary container",
        evidence: `format=${inspection.container_format}, size=${inspection.byte_length}B, segments=[${inspection.segments.map((s) => s.kind).join(", ")}], c2pa_carrier=${inspection.c2pa_carrier}.`,
        remediation:
          "Embed a signed C2PA v2.1 JUMBF superbox (`caBX` for PNG, `APP11 0xFFEB` for JPEG, `C2PA` for WebP, or `uuid d8fec3d6-...` for MP4).",
      });
      recordGate(
        GATE_DEFINITIONS[0],
        "fail",
        `No C2PA JUMBF superbox found in ${inspection.container_format.toUpperCase()} stream (${inspection.byte_length} bytes).`,
        g1Findings
      );
    } else if (g1Findings.length > 0) {
      recordGate(GATE_DEFINITIONS[0], "fail", "Corrupted container CRC detected in C2PA media stream.", g1Findings);
    } else if (
      !(inspection.has_assertions && inspection.has_claim && inspection.has_signature) ||
      inspection.parse_warnings.length > 0
    ) {
      const missingParts = [];
      if (!inspection.has_assertions) missingParts.push("c2pa.assertions");
      if (!inspection.has_claim) missingParts.push("c2pa.claim");
      if (!inspection.has_signature) missingParts.push("c2pa.signature");
      if (inspection.parse_warnings.length > 0) missingParts.push("truncated_box");
      g1Findings.push({
        gate_id: "C2PA-50-01",
        severity: "high",
        title: "Incomplete or unsigned JUMBF C2PA Manifest Store",
        evidence: `labels=[${inspection.jumbf_labels.join(", ")}], missing_or_warn=[${missingParts.join(", ")}].`,
        remediation:
          "Ensure the active C2PA manifest contains `c2pa.assertions`, `c2pa.claim.v2`, and a valid COSE_Sign1 `c2pa.signature` box.",
      });
      recordGate(
        GATE_DEFINITIONS[0],
        "warn",
        `Partial JUMBF store in ${inspection.c2pa_carrier}: missing/warn ${missingParts.join(", ")}.`,
        g1Findings
      );
    } else {
      recordGate(
        GATE_DEFINITIONS[0],
        "pass",
        `Verified ${inspection.container_format.toUpperCase()} \`${inspection.c2pa_carrier}\` JUMBF store (${inspection.jumbf_boxes.length} boxes, COSE sig ${inspection.signature_byte_length}B).`,
        g1Findings
      );
    }
  }

  // Gate 2: IPTC digitalSourceType
  const g2Findings = [];
  const dstValues = inspection ? [...inspection.digital_source_types] : [];
  const declaredDst = String(asset.declared_digital_source_type || "").trim();
  if (declaredDst && !dstValues.includes(declaredDst)) dstValues.push(declaredDst);

  const canonicalAiUris = dstValues.filter((u) => {
    const m = u.match(IPTC_CANONICAL_RE);
    return Boolean(m && IPTC_AI_SOURCE_CODES.has(m[1]));
  });
  const anyAiCode =
    Boolean(inspection && inspection.ai_source_type_detected) ||
    dstValues.some((u) => IPTC_AI_SOURCE_CODES.has(extractIptcCode(u)));
  const captureClaimed =
    Boolean(inspection && inspection.non_ai_capture_asserted) ||
    dstValues.includes("digitalCapture") ||
    dstValues.includes(`${IPTC_URI_PREFIX_HTTP}digitalCapture`);

  if (isAiGenerated) {
    if (captureClaimed) {
      g2Findings.push({
        gate_id: "C2PA-50-02",
        severity: "critical",
        title: "Deceptive non-AI camera `digitalCapture` IPTC URI on synthetic AI output",
        evidence: `digitalSourceType=[${dstValues.join(", ")}] while is_ai_generated=true.`,
        remediation:
          "Replace `digitalCapture` with `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` or `compositeWithTrainedAlgorithmicMedia`.",
      });
      recordGate(GATE_DEFINITIONS[1], "fail", "Deceptive `digitalCapture` source type asserted on AI-generated asset.", g2Findings);
    } else if (!anyAiCode || (inspection !== null && !inspection.ai_source_type_detected)) {
      g2Findings.push({
        gate_id: "C2PA-50-02",
        severity: "critical",
        title: "Missing machine-readable IPTC AI `digitalSourceType` in C2PA assertions",
        evidence: `embedded digital_source_types=[${inspection ? inspection.digital_source_types.join(", ") : ""}].`,
        remediation:
          'Add `digitalSourceType: "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"` inside `c2pa.actions.v2`.',
      });
      recordGate(GATE_DEFINITIONS[1], "fail", "No embedded IPTC algorithmic `digitalSourceType` assertion found.", g2Findings);
    } else if (canonicalAiUris.length === 0 || (inspection !== null && inspection.canonical_iptc_uris.length === 0)) {
      g2Findings.push({
        gate_id: "C2PA-50-02",
        severity: "medium",
        title: "Non-canonical shorthand `digitalSourceType` string",
        evidence: `digital_source_types=[${dstValues.join(", ")}].`,
        remediation:
          "Use the full canonical IPTC NewsCodes URI (`http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`).",
      });
      recordGate(GATE_DEFINITIONS[1], "warn", "Shorthand IPTC code detected without canonical `cv.iptc.org` URI.", g2Findings);
    } else {
      recordGate(GATE_DEFINITIONS[1], "pass", `Canonical IPTC AI URI verified: ${canonicalAiUris[0]}.`, g2Findings);
    }
  } else if (captureClaimed) {
    recordGate(GATE_DEFINITIONS[1], "pass", "Non-AI capture provenance URI matches `is_ai_generated=false`.", g2Findings);
  } else {
    g2Findings.push({
      gate_id: "C2PA-50-02",
      severity: "low",
      title: "Non-AI asset lacks explicit IPTC capture URI",
      evidence: `digital_source_types=[${dstValues.join(", ")}].`,
      remediation: "Declare `http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture` if camera-originated.",
    });
    recordGate(GATE_DEFINITIONS[1], "warn", "Non-AI asset has no explicit IPTC capture source URI.", g2Findings);
  }

  // Gate 3: HTTP Link rel="c2pa-manifest"
  const g3Findings = [];
  const linkVal = headers.link || "";
  const linkMatch = linkVal.match(LINK_C2PA_RE);
  const digestVal = headers["content-digest"] || headers.digest || "";
  const exposeVal = (headers["access-control-expose-headers"] || "").toLowerCase();

  if (!linkMatch) {
    g3Findings.push({
      gate_id: "C2PA-50-03",
      severity: "high",
      title: 'Missing HTTP `Link: <...>; rel="c2pa-manifest"` response header',
      evidence: `link='${linkVal}'`,
      remediation:
        'Configure CDN/origin to emit `Link: <https://.../asset.c2pa>; rel="c2pa-manifest"` so provenance survives embeds and proxies.',
    });
    recordGate(GATE_DEFINITIONS[2], "fail", 'No `Link: rel="c2pa-manifest"` header configured.', g3Findings);
  } else {
    const targetUri = linkMatch[1].trim();
    if (targetUri.toLowerCase().startsWith("http://")) {
      g3Findings.push({
        gate_id: "C2PA-50-03",
        severity: "high",
        title: "Plaintext `http://` C2PA sidecar manifest URI in HTTP Link header",
        evidence: `Link target='${targetUri}'`,
        remediation: "Serve detached `.c2pa` sidecar manifests strictly over TLS (`https://`).",
      });
      recordGate(GATE_DEFINITIONS[2], "fail", "Detached C2PA Link header points to insecure `http://` URI.", g3Findings);
    } else {
      const hasSha256 = digestVal.toLowerCase().includes("sha-256=");
      const exposesLink = exposeVal.includes("link") || exposeVal.includes("*");
      if (!hasSha256 || !exposesLink) {
        const missingHdrs = [];
        if (!hasSha256) missingHdrs.push("Content-Digest (sha-256)");
        if (!exposesLink) missingHdrs.push("Access-Control-Expose-Headers: Link");
        g3Findings.push({
          gate_id: "C2PA-50-03",
          severity: "medium",
          title: "C2PA Link header present without digest or CORS exposure",
          evidence: `missing=[${missingHdrs.join(", ")}]`,
          remediation:
            "Add `Content-Digest: sha-256=:...:` (RFC 9530) and `Access-Control-Expose-Headers: Link, Content-Digest` for cross-origin verifiers.",
        });
        recordGate(GATE_DEFINITIONS[2], "warn", `HTTPS C2PA Link present; missing ${missingHdrs.join(", ")}.`, g3Findings);
      } else {
        recordGate(
          GATE_DEFINITIONS[2],
          "pass",
          `Verified HTTPS \`rel="c2pa-manifest"\` (${targetUri}), SHA-256 Content-Digest, and CORS Link exposure.`,
          g3Findings
        );
      }
    }
  }

  // Gate 4: HTML / Schema.org JSON-LD
  const g4Findings = [];
  const { docs: ldDocs, errors: ldErrors } = extractJsonldObjects(htmlSnippet, explicitJsonld);
  if (ldErrors.length > 0) {
    for (const err of ldErrors) {
      g4Findings.push({
        gate_id: "C2PA-50-04",
        severity: "high",
        title: "Malformed JSON-LD provenance block",
        evidence: err,
        remediation: 'Fix JSON syntax inside `<script type="application/ld+json">`.',
      });
    }
    recordGate(GATE_DEFINITIONS[3], "fail", "Malformed JSON-LD syntax prevents machine-readable provenance parsing.", g4Findings);
  } else {
    let validLd = false;
    let partialLd = false;
    for (const doc of ldDocs) {
      const ctx = String(doc["@context"] || "").toLowerCase();
      const dst = String(doc.digitalSourceType || "").trim();
      const hasAttr = Boolean(doc.creator || doc.sdPublisher || doc.author || doc.creditText);
      const mIptc = dst.match(IPTC_CANONICAL_RE);
      if (ctx.includes("schema.org") && mIptc && IPTC_AI_SOURCE_CODES.has(mIptc[1]) && hasAttr) {
        validLd = true;
        break;
      }
      if (ctx.includes("schema.org") && dst) partialLd = true;
    }

    if (validLd) {
      recordGate(
        GATE_DEFINITIONS[3],
        "pass",
        "Schema.org JSON-LD declares canonical IPTC `digitalSourceType` and publisher attribution.",
        g4Findings
      );
    } else if (partialLd || META_AI_RE.test(htmlSnippet)) {
      g4Findings.push({
        gate_id: "C2PA-50-04",
        severity: "medium",
        title: "Informal or incomplete HTML AI provenance markup",
        evidence: `json_ld_objects=${ldDocs.length}, meta_tag_detected=${META_AI_RE.test(htmlSnippet)}.`,
        remediation:
          "Include Schema.org `ImageObject`/`VideoObject`/`CreativeWork` JSON-LD with canonical IPTC `digitalSourceType` and `sdPublisher`.",
      });
      recordGate(GATE_DEFINITIONS[3], "warn", "Partial HTML/JSON-LD markup found; missing canonical IPTC URI or `sdPublisher`.", g4Findings);
    } else {
      g4Findings.push({
        gate_id: "C2PA-50-04",
        severity: "high",
        title: "No Schema.org JSON-LD or HTML machine-readable AI provenance markup",
        evidence: "0 JSON-LD provenance blocks and 0 AI meta/microdata tags detected.",
        remediation:
          'Embed `<script type="application/ld+json">` with `digitalSourceType` so search engines and assistive agents detect AI provenance.',
      });
      recordGate(GATE_DEFINITIONS[3], "fail", "Missing Schema.org JSON-LD machine-readable provenance markup.", g4Findings);
    }
  }

  // Gate 5: Art. 50(1) Interactive AI / Chatbot
  const g5Findings = [];
  const interactive = gov.interactive_ai && typeof gov.interactive_ai === "object" ? gov.interactive_ai : {};
  const impersonates = Boolean(interactive.impersonates_human) || HUMAN_IMPERSONATION_RE.test(htmlSnippet);

  if (impersonates) {
    g5Findings.push({
      gate_id: "C2PA-50-05",
      severity: "critical",
      title: "Deceptive human impersonation violates EU AI Act Art. 50(1)",
      evidence: "impersonates_human=true or deceptive live-human copy detected.",
      remediation: "Remove human-impersonation prompts/copy and display a clear AI system notice prior to first user turn.",
    });
    recordGate(GATE_DEFINITIONS[4], "fail", "AI system impersonates a natural person in violation of Art. 50(1).", g5Findings);
  } else if (interactive.applies === false) {
    recordGate(GATE_DEFINITIONS[4], "pass", "Non-interactive pipeline explicitly scoped (`interactive_ai.applies=false`).", g5Findings);
  } else if (!interactive.pre_interaction_notice || Boolean(interactive.hidden_in_tos_only)) {
    g5Findings.push({
      gate_id: "C2PA-50-05",
      severity: "high",
      title: "Missing pre-interaction AI disclosure (or buried solely in Terms of Service)",
      evidence: `pre_interaction_notice=${interactive.pre_interaction_notice}, hidden_in_tos_only=${interactive.hidden_in_tos_only}.`,
      remediation:
        "Present an unmistakable surface banner/badge informing users they are interacting with an AI system before first message submission.",
    });
    recordGate(GATE_DEFINITIONS[4], "fail", "Missing clear Art. 50(1) pre-interaction human-facing AI disclosure.", g5Findings);
  } else if (!(interactive.clear_human_distinction && interactive.accessible_aria_disclosure)) {
    g5Findings.push({
      gate_id: "C2PA-50-05",
      severity: "medium",
      title: "Interactive AI notice lacks accessibility / ARIA role clarity",
      evidence: `clear_human_distinction=${interactive.clear_human_distinction}, accessible_aria_disclosure=${interactive.accessible_aria_disclosure}.`,
      remediation:
        'Expose AI disclosure via `aria-label` / `role="status"` in plain language per EU AI Act Art. 50(1) accessibility requirements.',
    });
    recordGate(GATE_DEFINITIONS[4], "warn", "Pre-interaction AI notice enabled, but ARIA accessibility flag is incomplete.", g5Findings);
  } else {
    recordGate(GATE_DEFINITIONS[4], "pass", "Clear, accessible pre-interaction AI disclosure verified (`Art. 50(1)`).", g5Findings);
  }

  // Gate 6: Art. 50(3) Emotion Recognition & Biometric Categorization
  const g6Findings = [];
  const bio = gov.biometric_emotion && typeof gov.biometric_emotion === "object" ? gov.biometric_emotion : null;
  if (bio === null) {
    g6Findings.push({
      gate_id: "C2PA-50-06",
      severity: "medium",
      title: "Biometric categorization & emotion recognition scope undeclared",
      evidence: "governance.biometric_emotion object is absent.",
      remediation: "Explicitly set `biometric_emotion.enabled: false`, or configure prior subject notice and DPIA reference if applicable.",
    });
    recordGate(GATE_DEFINITIONS[5], "warn", "Emotion/biometric scope undeclared in governance manifest.", g6Findings);
  } else if (bio.workplace_or_education_emotion_monitoring) {
    g6Findings.push({
      gate_id: "C2PA-50-06",
      severity: "critical",
      title: "Prohibited workplace or education emotion inference (EU AI Act Art. 5(1)(f))",
      evidence: "workplace_or_education_emotion_monitoring=true.",
      remediation: "Immediately disable workplace/educational emotion recognition unless strictly medical/safety-exempt and legally cleared.",
    });
    recordGate(GATE_DEFINITIONS[5], "fail", "Prohibited workplace/education emotion inference flagged (`Art. 5(1)(f)`).", g6Findings);
  } else if (bio.enabled === false) {
    recordGate(GATE_DEFINITIONS[5], "pass", "Emotion recognition and biometric categorization explicitly disabled.", g6Findings);
  } else {
    const hasNotice = Boolean(bio.explicit_prior_subject_notice);
    const dpiaRef = String(bio.dpia_reference || "").trim();
    const lawfulBasis = String(bio.gdpr_appi_lawful_basis || "").trim();
    if (!hasNotice || !dpiaRef) {
      g6Findings.push({
        gate_id: "C2PA-50-06",
        severity: "critical",
        title: "Active emotion/biometric AI missing explicit prior notice or DPIA",
        evidence: `explicit_prior_subject_notice=${hasNotice}, dpia_reference='${dpiaRef}'.`,
        remediation:
          "Provide explicit prior notice to exposed natural persons and record a GDPR/APPI Data Protection Impact Assessment (`dpia_reference`).",
      });
      recordGate(GATE_DEFINITIONS[5], "fail", "Active biometric/emotion system lacks mandatory Art. 50(3) subject notice or DPIA.", g6Findings);
    } else if (!lawfulBasis) {
      g6Findings.push({
        gate_id: "C2PA-50-06",
        severity: "medium",
        title: "Biometric/emotion notice present without documented GDPR/APPI lawful basis",
        evidence: "gdpr_appi_lawful_basis is empty.",
        remediation: "Record the GDPR Art. 9 / Japan APPI special-care personal data lawful basis.",
      });
      recordGate(GATE_DEFINITIONS[5], "warn", "Art. 50(3) notice and DPIA present; lawful basis string unset.", g6Findings);
    } else {
      recordGate(GATE_DEFINITIONS[5], "pass", `Art. 50(3) prior notice, DPIA (${dpiaRef}), and lawful basis verified.`, g6Findings);
    }
  }

  // Gate 7: Art. 50(4) Deepfake & Public-Interest Text
  const g7Findings = [];
  const df = gov.deepfake_and_text && typeof gov.deepfake_and_text === "object" ? gov.deepfake_and_text : null;
  if (df === null) {
    g7Findings.push({
      gate_id: "C2PA-50-07",
      severity: "medium",
      title: "Art. 50(4) deepfake & public-interest text policy undeclared",
      evidence: "governance.deepfake_and_text object is absent.",
      remediation: "Declare synthetic likeness disclosure rules and human editorial responsibility for public-interest text.",
    });
    recordGate(GATE_DEFINITIONS[6], "warn", "Art. 50(4) synthetic likeness and public-interest text policy undeclared.", g7Findings);
  } else {
    const likenessUsed = Boolean(df.generates_synthetic_likeness_or_voice);
    const likenessDisclosed = Boolean(df.visible_deepfake_disclosure);
    const pubText = Boolean(df.publishes_public_interest_text);
    const textDisclosed = Boolean(df.visible_ai_text_disclosure);
    const humanReview = Boolean(df.human_editorial_review);
    const editorHolder = String(df.editorial_responsibility_holder || "").trim();
    const reviewLog = String(df.editorial_review_log_id || "").trim();

    const likenessFail = likenessUsed && !likenessDisclosed;
    const textFail = pubText && !(textDisclosed || (humanReview && Boolean(editorHolder)));

    if (likenessFail || textFail) {
      if (likenessFail) {
        g7Findings.push({
          gate_id: "C2PA-50-07",
          severity: "high",
          title: "Undisclosed synthetic likeness / voice / deepfake output (Art. 50(4))",
          evidence: "generates_synthetic_likeness_or_voice=true, visible_deepfake_disclosure=false.",
          remediation: "Display clear visible/audible synthetic media disclosure per EU AI Act Art. 50(4).",
        });
      }
      if (textFail) {
        g7Findings.push({
          gate_id: "C2PA-50-07",
          severity: "high",
          title: "AI public-interest text lacks both visible disclosure and human editorial responsibility",
          evidence: `visible_ai_text_disclosure=${textDisclosed}, human_editorial_review=${humanReview}, editorial_responsibility_holder='${editorHolder}'.`,
          remediation:
            "Disclose AI text generation OR document human editorial review plus a named legal/natural editorial responsibility holder.",
        });
      }
      recordGate(GATE_DEFINITIONS[6], "fail", "Art. 50(4) deepfake or public-interest text disclosure failure.", g7Findings);
    } else if (pubText && !textDisclosed && humanReview && !reviewLog) {
      g7Findings.push({
        gate_id: "C2PA-50-07",
        severity: "medium",
        title: "Editorial exemption claimed without sign-off audit log reference",
        evidence: `editorial_responsibility_holder='${editorHolder}', editorial_review_log_id=''.`,
        remediation: "Record `editorial_review_log_id` to evidence human review under supervisory audit.",
      });
      recordGate(GATE_DEFINITIONS[6], "warn", "Art. 50(4) editorial exemption lacks `editorial_review_log_id`.", g7Findings);
    } else {
      recordGate(GATE_DEFINITIONS[6], "pass", "Art. 50(4) deepfake disclosure and editorial responsibility controls verified.", g7Findings);
    }
  }

  // Gate 8: CDN & Image Optimizer Provenance Stripping Resilience
  const g8Findings = [];
  const cdn = gov.cdn_preservation && typeof gov.cdn_preservation === "object" ? gov.cdn_preservation : {};
  const cfPolished = "cf-polished" in headers || "x-fastly-imageopto-api" in headers;
  const stripsAll = Boolean(cdn.strip_all_metadata);
  const strippedBinary = Boolean(inspection && inspection.probable_metadata_stripped);

  if (stripsAll || (cfPolished && (!inspection || !inspection.c2pa_present)) || (strippedBinary && !linkMatch)) {
    g8Findings.push({
      gate_id: "C2PA-50-08",
      severity: "high",
      title: "CDN / image optimizer strips C2PA JUMBF chunks without detached recovery",
      evidence: `strip_all_metadata=${stripsAll}, cdn_transform_header=${cfPolished}, probable_metadata_stripped=${strippedBinary}, link_header_present=${Boolean(linkMatch)}.`,
      remediation:
        'Disable lossy metadata stripping (`Cache-Control: no-transform`, `sharp.keepMetadata()`), re-sign resized derivatives, and serve a `rel="c2pa-manifest"` Link header.',
    });
    recordGate(GATE_DEFINITIONS[7], "fail", "Active metadata stripping detected across binary asset / CDN pipeline.", g8Findings);
  } else {
    const preserveOk = Boolean(cdn.preserve_c2pa_chunks);
    const derivOk = Boolean(cdn.re_sign_derivatives || cdn.immutable_origin_passthrough);
    const sidecarOk = Boolean(cdn.soft_binding_sidecar_fallback);
    if (preserveOk && derivOk && sidecarOk && !strippedBinary) {
      recordGate(
        GATE_DEFINITIONS[7],
        "pass",
        "CDN chunk preservation, derivative re-signing, and detached sidecar fallback verified.",
        g8Findings
      );
    } else {
      g8Findings.push({
        gate_id: "C2PA-50-08",
        severity: "medium",
        title: "CDN / resizer metadata preservation policy incomplete",
        evidence: `preserve_c2pa_chunks=${preserveOk}, derivative_policy=${derivOk}, soft_binding_sidecar_fallback=${sidecarOk}.`,
        remediation:
          "Verify Cloudflare/CloudFront/Next.js `sharp` preserves `caBX`/`APP11`/`C2PA`/`uuid` chunks and enable sidecar soft-binding fallback.",
      });
      recordGate(GATE_DEFINITIONS[7], "warn", "Origin C2PA present, but CDN/optimizer preservation flags are incomplete.", g8Findings);
    }
  }

  // Gate 9: Japan AI Promotion Act Immutable Traceability & Incident Log
  const g9Findings = [];
  const jp = gov.jp_ai_safety && typeof gov.jp_ai_safety === "object" ? gov.jp_ai_safety : {};
  const wormLog = Boolean(jp.immutable_audit_log_enabled);
  const retentionDays = typeof jp.retention_days === "number" ? Math.trunc(jp.retention_days) : 0;
  const slaHrs = typeof jp.incident_reporting_sla_hours === "number" ? Math.trunc(jp.incident_reporting_sla_hours) : 0;
  const govRole = String(jp.safety_governance_role || "").trim();

  if (!wormLog) {
    g9Findings.push({
      gate_id: "C2PA-50-09",
      severity: "high",
      title: "Immutable AI provenance & incident audit log disabled (Japan AI Promotion Act)",
      evidence: `immutable_audit_log_enabled=${wormLog}.`,
      remediation:
        "Enable append-only/WORM audit logging (>=180 days) and <=24h Cabinet Office / METI incident reporting workflow.",
    });
    recordGate(
      GATE_DEFINITIONS[8],
      "fail",
      "Missing immutable AI audit trail required for Japan statutory investigation readiness.",
      g9Findings
    );
  } else if (retentionDays < 180 || slaHrs < 1 || slaHrs > 24 || !govRole) {
    g9Findings.push({
      gate_id: "C2PA-50-09",
      severity: "medium",
      title: "Japan AI audit log retention, SLA, or CAIO role below statutory benchmark",
      evidence: `retention_days=${retentionDays}, incident_reporting_sla_hours=${slaHrs}, safety_governance_role='${govRole}'.`,
      remediation:
        "Set `retention_days >= 180`, `incident_reporting_sla_hours <= 24`, and designate a `safety_governance_role` (CAIO / Safety Office).",
    });
    recordGate(
      GATE_DEFINITIONS[8],
      "warn",
      `Audit log active, but retention (${retentionDays}d), SLA (${slaHrs}h), or CAIO role needs tightening.`,
      g9Findings
    );
  } else {
    recordGate(
      GATE_DEFINITIONS[8],
      "pass",
      `Immutable WORM trace log (${retentionDays}d retention, ${slaHrs}h incident SLA, ${govRole}) verified.`,
      g9Findings
    );
  }

  // Gate 10: Japan AI Safety Autonomous Kill-Switch & Compliance Bundle
  const g10Findings = [];
  const ksEnabled = Boolean(jp.kill_switch_enabled);
  const ksMech = String(jp.kill_switch_mechanism || "").trim();
  const cbEnabled = Boolean(jp.auto_circuit_breaker);
  const haltSec = typeof jp.max_halt_latency_seconds === "number" ? Math.trunc(jp.max_halt_latency_seconds) : 0;

  if (!ksEnabled || !ksMech) {
    g10Findings.push({
      gate_id: "C2PA-50-10",
      severity: "high",
      title: "Missing autonomous AI emergency kill-switch mechanism",
      evidence: `kill_switch_enabled=${ksEnabled}, kill_switch_mechanism='${ksMech}'.`,
      remediation:
        "Wire an out-of-band kill-switch flag/endpoint capable of halting autonomous generation/publishing within 60 seconds.",
    });
    recordGate(GATE_DEFINITIONS[9], "fail", "No emergency kill-switch configured for autonomous AI egress.", g10Findings);
  } else if (!cbEnabled || haltSec < 1 || haltSec > 60) {
    g10Findings.push({
      gate_id: "C2PA-50-10",
      severity: "medium",
      title: "Kill-switch lacks automated anomaly circuit-breaker or <=60s halt SLA",
      evidence: `auto_circuit_breaker=${cbEnabled}, max_halt_latency_seconds=${haltSec}.`,
      remediation: "Enable `auto_circuit_breaker: true` and bound `max_halt_latency_seconds <= 60`.",
    });
    recordGate(
      GATE_DEFINITIONS[9],
      "warn",
      `Kill-switch declared, but circuit-breaker (${cbEnabled}) or halt SLA (${haltSec}s) is weak.`,
      g10Findings
    );
  } else {
    recordGate(
      GATE_DEFINITIONS[9],
      "pass",
      `Emergency kill-switch (${ksMech}), circuit-breaker, and ${haltSec}s halt SLA verified.`,
      g10Findings
    );
  }

  const score = Math.max(0, Math.min(100, rawScore));
  const grade = score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : score >= 55 ? "D" : "F";
  const gatesPassed = gateResults.filter((g) => g.status === "pass").length;
  const gatesWarned = gateResults.filter((g) => g.status === "warn").length;
  const gatesFailed = gateResults.filter((g) => g.status === "fail").length;
  const status = gatesFailed === 0 && gatesWarned === 0 ? "compliant" : gatesFailed === 0 ? "action_required" : "non_compliant";

  const remediated = buildRemediatedBundleInput(cfg, inspection);
  const remAsset = remediated.asset;
  const bundleMime = inspection && inspection.container_format !== "unknown" ? inspection.mime_type : "image/png";
  const bundleDigest = inspection ? inspection.content_digest_header : String(remediated.http_headers["Content-Digest"]);
  const bundleDst = String(remediated.json_ld.digitalSourceType);
  const bundleGen =
    inspection && inspection.claim_generators.length > 0
      ? inspection.claim_generators[0]
      : "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0";

  const exportBundle = buildComplianceBundle({
    assetName: String(remAsset.name),
    publicAssetUrl: String(remAsset.public_url),
    manifestSidecarUrl: String(remAsset.manifest_sidecar_url),
    mimeType: bundleMime,
    contentDigest: bundleDigest,
    digitalSourceTypeUri: bundleDst,
    claimGenerator: bundleGen,
    publisherName: String(remAsset.publisher),
  });

  return {
    asset_name: assetName,
    status,
    score,
    grade,
    eu_art50_sunset: EU_AI_ACT_ART50_SUNSET,
    jp_revision_target: JP_AI_ACT_REVISION_TARGET,
    gates_passed: gatesPassed,
    gates_warned: gatesWarned,
    gates_failed: gatesFailed,
    findings_count: allFindings.length,
    binary_inspection: inspection,
    gates: gateResults,
    findings: allFindings,
    compliance_bundle: exportBundle,
    remediated_input: remediated,
  };
}

export function buildSamplePresets() {
  const compliantPng = inspectMediaBytes(
    synthesizePngBytes({
      includeC2pa: true,
      digitalSourceType: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
      claimGenerator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
      includeSignature: true,
    })
  );
  const compliantMp4 = inspectMediaBytes(
    synthesizeMp4Bytes({
      includeC2pa: true,
      digitalSourceType: `${IPTC_URI_PREFIX_HTTP}compositeWithTrainedAlgorithmicMedia`,
      claimGenerator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
      includeSignature: true,
    })
  );

  return {
    "stripped-cdn-png": {
      asset: {
        name: "autumn-campaign-hero.png",
        is_ai_generated: true,
        public_url: "https://cdn.velvet-retail.eu/assets/autumn-campaign-hero.png",
        publisher: "Velvet Retail GmbH",
      },
      synthetic_media: {
        format: "png",
        include_c2pa: false,
        include_legacy_text: false,
      },
      http_headers: {
        "Cache-Control": "public, max-age=86400",
        "Cf-Polished": "origSize=418200, status=webp_bigger",
      },
      html_snippet: '<img src="/assets/autumn-campaign-hero.png" alt="Autumn knitwear campaign">',
      governance: {
        interactive_ai: {
          applies: true,
          pre_interaction_notice: false,
          hidden_in_tos_only: true,
        },
        biometric_emotion: {
          enabled: true,
          workplace_or_education_emotion_monitoring: false,
          explicit_prior_subject_notice: false,
          dpia_reference: "",
        },
        deepfake_and_text: {
          generates_synthetic_likeness_or_voice: true,
          visible_deepfake_disclosure: false,
          publishes_public_interest_text: true,
          visible_ai_text_disclosure: false,
          human_editorial_review: false,
          editorial_responsibility_holder: "",
        },
        cdn_preservation: {
          strip_all_metadata: true,
          preserve_c2pa_chunks: false,
          re_sign_derivatives: false,
          soft_binding_sidecar_fallback: false,
        },
        jp_ai_safety: {
          immutable_audit_log_enabled: false,
          retention_days: 14,
          incident_reporting_sla_hours: 72,
          safety_governance_role: "",
          kill_switch_enabled: false,
          kill_switch_mechanism: "",
        },
      },
    },
    "deceptive-jpeg-app11": {
      asset: {
        name: "editorial-portrait-synth.jpg",
        is_ai_generated: true,
        public_url: "https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg",
        manifest_sidecar_url: "https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg.c2pa",
        publisher: "Hanse Briefing Media",
      },
      synthetic_media: {
        format: "jpeg",
        include_c2pa: true,
        multi_segment_app11: true,
        digital_source_type: `${IPTC_URI_PREFIX_HTTP}digitalCapture`,
        claim_generator: "StudioExport/1.4",
        include_signature: false,
      },
      http_headers: {
        Link: '<https://media.hanse-briefing.de/2026/editorial-portrait-synth.jpg.c2pa>; rel="c2pa-manifest"',
      },
      html_snippet: '<meta name="ai-generated" content="true">',
      governance: {
        interactive_ai: {
          applies: true,
          pre_interaction_notice: true,
          clear_human_distinction: true,
          accessible_aria_disclosure: false,
        },
        biometric_emotion: {
          enabled: false,
          workplace_or_education_emotion_monitoring: false,
        },
        deepfake_and_text: {
          generates_synthetic_likeness_or_voice: false,
          publishes_public_interest_text: true,
          visible_ai_text_disclosure: false,
          human_editorial_review: true,
          editorial_responsibility_holder: "Hanse Editorial Desk",
          editorial_review_log_id: "",
        },
        cdn_preservation: {
          strip_all_metadata: false,
          preserve_c2pa_chunks: true,
          re_sign_derivatives: false,
          soft_binding_sidecar_fallback: false,
        },
        jp_ai_safety: {
          immutable_audit_log_enabled: true,
          retention_days: 90,
          incident_reporting_sla_hours: 48,
          safety_governance_role: "AI Risk Officer",
          kill_switch_enabled: true,
          kill_switch_mechanism: "admin-toggle://cms-halt",
          auto_circuit_breaker: false,
          max_halt_latency_seconds: 180,
        },
      },
    },
    "webp-riff-c2pa": {
      asset: {
        name: "product-packshot-gen.webp",
        is_ai_generated: true,
        public_url: "https://static.kuroshio-labs.jp/img/product-packshot-gen.webp",
        manifest_sidecar_url: "https://static.kuroshio-labs.jp/img/product-packshot-gen.webp.c2pa",
        publisher: "Kuroshio Commerce KK",
      },
      synthetic_media: {
        format: "webp",
        include_c2pa: true,
        digital_source_type: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
        claim_generator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
        include_signature: true,
      },
      http_headers: {
        Link: '<https://static.kuroshio-labs.jp/img/product-packshot-gen.webp.c2pa>; rel="c2pa-manifest"',
      },
      json_ld: {
        "@context": "https://schema.org",
        "@type": "ImageObject",
        name: "product-packshot-gen.webp",
        digitalSourceType: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
        sdPublisher: { "@type": "Organization", name: "Kuroshio Commerce KK" },
      },
      governance: {
        interactive_ai: {
          applies: true,
          pre_interaction_notice: true,
          clear_human_distinction: true,
          accessible_aria_disclosure: true,
        },
        biometric_emotion: {
          enabled: false,
          workplace_or_education_emotion_monitoring: false,
        },
        deepfake_and_text: {
          generates_synthetic_likeness_or_voice: false,
          publishes_public_interest_text: false,
        },
        cdn_preservation: {
          strip_all_metadata: false,
          preserve_c2pa_chunks: true,
          re_sign_derivatives: true,
          soft_binding_sidecar_fallback: false,
        },
        jp_ai_safety: {
          immutable_audit_log_enabled: true,
          retention_days: 365,
          incident_reporting_sla_hours: 12,
          safety_governance_role: "CAIO & AI Safety Office",
          kill_switch_enabled: true,
          kill_switch_mechanism: "feature-flag://kuroshio-ai-halt",
          auto_circuit_breaker: true,
          max_halt_latency_seconds: 20,
        },
      },
    },
    "compliant-png-cabx": {
      asset: {
        name: "eu-launch-keyvisual.png",
        is_ai_generated: true,
        public_url: "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png",
        manifest_sidecar_url: "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png.c2pa",
        publisher: "Nordlicht Studio GmbH",
      },
      synthetic_media: {
        format: "png",
        include_c2pa: true,
        digital_source_type: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
        claim_generator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
        include_signature: true,
      },
      http_headers: {
        Link: '<https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png.c2pa>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
        "Content-Digest": compliantPng.content_digest_header,
        "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
        "Cache-Control": "public, max-age=31536000, no-transform",
      },
      json_ld: {
        "@context": "https://schema.org",
        "@type": "ImageObject",
        name: "eu-launch-keyvisual.png",
        contentUrl: "https://cdn.nordlicht-studio.eu/media/eu-launch-keyvisual.png",
        encodingFormat: "image/png",
        digitalSourceType: `${IPTC_URI_PREFIX_HTTP}trainedAlgorithmicMedia`,
        creditText: "AI-generated media signed with C2PA Content Credentials (Nordlicht Studio GmbH)",
        creator: { "@type": "Organization", name: "Nordlicht Studio GmbH" },
        sdPublisher: { "@type": "Organization", name: "Nordlicht Studio GmbH" },
      },
      governance: {
        interactive_ai: {
          applies: true,
          pre_interaction_notice: true,
          clear_human_distinction: true,
          accessible_aria_disclosure: true,
          hidden_in_tos_only: false,
          impersonates_human: false,
        },
        biometric_emotion: {
          enabled: false,
          workplace_or_education_emotion_monitoring: false,
        },
        deepfake_and_text: {
          generates_synthetic_likeness_or_voice: false,
          visible_deepfake_disclosure: true,
          publishes_public_interest_text: true,
          visible_ai_text_disclosure: true,
          human_editorial_review: true,
          editorial_responsibility_holder: "Nordlicht Studio Editorial Board",
          editorial_review_log_id: "ed-rev-2026-1120",
        },
        cdn_preservation: {
          strip_all_metadata: false,
          preserve_c2pa_chunks: true,
          re_sign_derivatives: true,
          immutable_origin_passthrough: true,
          soft_binding_sidecar_fallback: true,
        },
        jp_ai_safety: {
          immutable_audit_log_enabled: true,
          retention_days: 365,
          incident_reporting_sla_hours: 12,
          safety_governance_role: "CAIO & AI Safety Response Office",
          kill_switch_enabled: true,
          kill_switch_mechanism: "edge-kv://ai-agent-circuit-breaker/global-halt",
          auto_circuit_breaker: true,
          max_halt_latency_seconds: 15,
        },
      },
    },
    "compliant-mp4-uuid": {
      asset: {
        name: "avatar-keynote-localization.mp4",
        is_ai_generated: true,
        public_url: "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4",
        manifest_sidecar_url: "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4.c2pa",
        publisher: "Mirai Broadcast Corp.",
      },
      synthetic_media: {
        format: "mp4",
        include_c2pa: true,
        digital_source_type: `${IPTC_URI_PREFIX_HTTP}compositeWithTrainedAlgorithmicMedia`,
        claim_generator: "C2PAGATE-Reference-Signer/2.1 c2pa-rs/0.36.0",
        include_signature: true,
      },
      http_headers: {
        Link: '<https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4.c2pa>; rel="c2pa-manifest"; type="application/x-c2pa-manifest-store"',
        "Content-Digest": compliantMp4.content_digest_header,
        "Access-Control-Expose-Headers": "Link, Content-Digest, X-AI-Provenance",
        "Cache-Control": "public, max-age=31536000, no-transform",
      },
      json_ld: {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        name: "avatar-keynote-localization.mp4",
        contentUrl: "https://video.mirai-broadcast.jp/2026/avatar-keynote-localization.mp4",
        encodingFormat: "video/mp4",
        digitalSourceType: `${IPTC_URI_PREFIX_HTTP}compositeWithTrainedAlgorithmicMedia`,
        creditText: "AI-localized keynote signed with C2PA ISOBMFF uuid Content Credentials",
        creator: { "@type": "Organization", name: "Mirai Broadcast Corp." },
        sdPublisher: { "@type": "Organization", name: "Mirai Broadcast Corp." },
      },
      governance: {
        interactive_ai: {
          applies: false,
        },
        biometric_emotion: {
          enabled: false,
          workplace_or_education_emotion_monitoring: false,
        },
        deepfake_and_text: {
          generates_synthetic_likeness_or_voice: true,
          visible_deepfake_disclosure: true,
          publishes_public_interest_text: true,
          visible_ai_text_disclosure: true,
          human_editorial_review: true,
          editorial_responsibility_holder: "Mirai Broadcast Standards Desk",
          editorial_review_log_id: "mb-ed-2026-0991",
        },
        cdn_preservation: {
          strip_all_metadata: false,
          preserve_c2pa_chunks: true,
          re_sign_derivatives: true,
          immutable_origin_passthrough: true,
          soft_binding_sidecar_fallback: true,
        },
        jp_ai_safety: {
          immutable_audit_log_enabled: true,
          retention_days: 730,
          incident_reporting_sla_hours: 6,
          safety_governance_role: "Chief AI Safety Officer (CAIO)",
          kill_switch_enabled: true,
          kill_switch_mechanism: "envoy-eds://mirai-ai-egress/emergency-stop",
          auto_circuit_breaker: true,
          max_halt_latency_seconds: 10,
        },
      },
    },
  };
}
