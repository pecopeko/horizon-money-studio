/**
 * Pure-JS Zero-CDN Local PDF Text Extractor & Synthetic Japanese Invoice PDF Builder.
 *
 * Extracts text from:
 * - Uncompressed PDF content streams ((...) Tj, <...> Tj, [...] TJ, ', ")
 * - /FlateDecode compressed streams via standard Web/Node DecompressionStream("deflate")
 * - Embedded ToUnicode CMap tables (beginbfchar / beginbfrange) for Japanese CID fonts
 * - UTF-16BE / UniJIS-UTF16-H hex strings and UTF-8 / Latin-1 literal strings
 *
 * Never makes network calls and degrades safely on encrypted or scanned image PDFs.
 */

const LATIN1_DECODER = new TextDecoder("latin1");
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true });
const UTF8_LENIENT = new TextDecoder("utf-8", { fatal: false });
const TEXT_ENCODER = new TextEncoder();

const MAX_INFLATED_STREAM_BYTES = 8 * 1024 * 1024;
const MAX_CMAP_RANGE_EXPANSION = 4096;

function toUint8Array(input) {
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  if (ArrayBuffer.isView(input)) {
    return new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
  }
  throw new TypeError("PDF input must be Uint8Array, ArrayBuffer, or TypedArray");
}

async function runDecompressionStream(bytes, format) {
  if (typeof DecompressionStream !== "function") return null;
  let ds;
  try {
    ds = new DecompressionStream(format);
  } catch {
    return null;
  }

  const writer = ds.writable.getWriter();
  const reader = ds.readable.getReader();
  const chunks = [];
  let totalLength = 0;

  const writeTask = (async () => {
    try {
      await writer.write(bytes);
      await writer.close();
    } catch {
      // Corrupt stream errors are surfaced on the readable side.
    }
  })();

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value && value.byteLength > 0) {
        chunks.push(value);
        totalLength += value.byteLength;
        if (totalLength > MAX_INFLATED_STREAM_BYTES) {
          await reader.cancel();
          break;
        }
      }
    }
    await writeTask;
  } catch {
    try {
      await reader.cancel();
    } catch {
      // ignore cleanup error
    }
    return null;
  }

  if (totalLength === 0) return null;
  const out = new Uint8Array(totalLength);
  let pos = 0;
  for (const chunk of chunks) {
    out.set(chunk, pos);
    pos += chunk.byteLength;
  }
  return out;
}

/**
 * Inflate a PDF /FlateDecode stream (RFC 1950 zlib, falling back to raw deflate).
 * @param {Uint8Array} compressedBytes
 * @returns {Promise<Uint8Array | null>}
 */
export async function inflateFlateBytes(compressedBytes) {
  const zlibOut = await runDecompressionStream(compressedBytes, "deflate");
  if (zlibOut) return zlibOut;
  return runDecompressionStream(compressedBytes, "deflate-raw");
}

/**
 * Compress bytes with RFC 1950 zlib using CompressionStream("deflate") if available.
 * @param {Uint8Array} rawBytes
 * @returns {Promise<Uint8Array | null>}
 */
async function deflateFlateBytes(rawBytes) {
  if (typeof CompressionStream !== "function") return null;
  let cs;
  try {
    cs = new CompressionStream("deflate");
  } catch {
    return null;
  }
  const writer = cs.writable.getWriter();
  const reader = cs.readable.getReader();
  const chunks = [];
  let totalLength = 0;

  const writeTask = (async () => {
    try {
      await writer.write(rawBytes);
      await writer.close();
    } catch {
      // ignore
    }
  })();

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value && value.byteLength > 0) {
        chunks.push(value);
        totalLength += value.byteLength;
      }
    }
    await writeTask;
  } catch {
    return null;
  }

  const out = new Uint8Array(totalLength);
  let pos = 0;
  for (const chunk of chunks) {
    out.set(chunk, pos);
    pos += chunk.byteLength;
  }
  return out;
}

function decodeUtf16BeBytes(bytes, startOffset = 0) {
  let out = "";
  for (let i = startOffset; i + 1 < bytes.length; i += 2) {
    const codeUnit = (bytes[i] << 8) | bytes[i + 1];
    if (codeUnit === 0xfeff && i === startOffset) continue;
    if (codeUnit === 0) continue;
    out += String.fromCharCode(codeUnit);
  }
  return out;
}

function hexToBytes(hexStr) {
  const clean = hexStr.replace(/\s+/g, "");
  if (!clean) return new Uint8Array(0);
  const padded = clean.length % 2 === 1 ? `${clean}0` : clean;
  const out = new Uint8Array(padded.length / 2);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = parseInt(padded.slice(i * 2, i * 2 + 2), 16) || 0;
  }
  return out;
}

function decodeHexAsUtf16Be(hexStr) {
  const bytes = hexToBytes(hexStr);
  return decodeUtf16BeBytes(bytes, 0);
}

function isReadableJapaneseOrAsciiChar(cp) {
  if (cp === 0x09 || cp === 0x0a || cp === 0x0d) return true;
  if (cp >= 0x20 && cp <= 0x7e) return true; // ASCII
  if (cp === 0x00a5 || cp === 0x2010 || cp === 0x2014 || cp === 0x2212) return true; // ¥, dashes
  if (cp >= 0x3000 && cp <= 0x30ff) return true; // CJK punct, Hiragana, Katakana
  if (cp >= 0x4e00 && cp <= 0x9fff) return true; // CJK Unified Ideographs
  if (cp >= 0xff01 && cp <= 0xffef) return true; // Full-width ASCII / Half-width Kana
  return false;
}

function looksReadableText(str) {
  if (!str) return false;
  let good = 0;
  let total = 0;
  for (let i = 0; i < str.length; i += 1) {
    const cp = str.charCodeAt(i);
    total += 1;
    if (isReadableJapaneseOrAsciiChar(cp)) good += 1;
  }
  return total > 0 && good / total >= 0.72;
}

/**
 * Parse a ToUnicode CMap stream into a glyph-hex -> Unicode string map.
 * Supports both `beginbfchar` and `beginbfrange` (single base & array forms).
 */
function parseToUnicodeCMap(cmapText, cmapState) {
  const bfCharRe = /beginbfchar([\s\S]*?)endbfchar/g;
  let m;
  while ((m = bfCharRe.exec(cmapText)) !== null) {
    const pairRe = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g;
    let p;
    while ((p = pairRe.exec(m[1])) !== null) {
      const srcHex = p[1].toUpperCase();
      const dstStr = decodeHexAsUtf16Be(p[2]);
      if (dstStr) {
        cmapState.map.set(srcHex, dstStr);
        cmapState.keyLengths.add(srcHex.length);
      }
    }
  }

  const bfRangeRe = /beginbfrange([\s\S]*?)endbfrange/g;
  while ((m = bfRangeRe.exec(cmapText)) !== null) {
    const body = m[1];
    // Form 1: <start> <end> <dstStart>
    const directRe = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g;
    let r;
    while ((r = directRe.exec(body)) !== null) {
      const srcLen = r[1].length;
      const start = parseInt(r[1], 16);
      const end = parseInt(r[2], 16);
      const dstBytes = hexToBytes(r[3]);
      if (Number.isNaN(start) || Number.isNaN(end) || end < start || dstBytes.length < 2) {
        continue;
      }
      const span = Math.min(end - start + 1, MAX_CMAP_RANGE_EXPANSION);
      const baseLastCode = (dstBytes[dstBytes.length - 2] << 8) | dstBytes[dstBytes.length - 1];
      const prefix =
        dstBytes.length > 2 ? decodeUtf16BeBytes(dstBytes.subarray(0, dstBytes.length - 2)) : "";
      for (let i = 0; i < span; i += 1) {
        const key = (start + i).toString(16).toUpperCase().padStart(srcLen, "0");
        cmapState.map.set(key, `${prefix}${String.fromCharCode((baseLastCode + i) & 0xffff)}`);
      }
      cmapState.keyLengths.add(srcLen);
    }

    // Form 2: <start> <end> [<dst1> <dst2> ...]
    const arrayRe = /<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[([\s\S]*?)\]/g;
    while ((r = arrayRe.exec(body)) !== null) {
      const srcLen = r[1].length;
      const start = parseInt(r[1], 16);
      const end = parseInt(r[2], 16);
      if (Number.isNaN(start) || Number.isNaN(end) || end < start) continue;
      const entries = [...r[3].matchAll(/<([0-9A-Fa-f]+)>/g)].map((x) => x[1]);
      const count = Math.min(entries.length, end - start + 1, MAX_CMAP_RANGE_EXPANSION);
      for (let i = 0; i < count; i += 1) {
        const key = (start + i).toString(16).toUpperCase().padStart(srcLen, "0");
        const val = decodeHexAsUtf16Be(entries[i]);
        if (val) cmapState.map.set(key, val);
      }
      cmapState.keyLengths.add(srcLen);
    }
  }
}

/**
 * Unescape a PDF literal string body (between outer parentheses).
 */
function decodePdfLiteralString(rawBody) {
  const bytes = [];
  for (let i = 0; i < rawBody.length; i += 1) {
    const ch = rawBody[i];
    if (ch !== "\\") {
      bytes.push(rawBody.charCodeAt(i) & 0xff);
      continue;
    }
    i += 1;
    if (i >= rawBody.length) break;
    const esc = rawBody[i];
    if (esc === "n") bytes.push(0x0a);
    else if (esc === "r") bytes.push(0x0d);
    else if (esc === "t") bytes.push(0x09);
    else if (esc === "b") bytes.push(0x08);
    else if (esc === "f") bytes.push(0x0c);
    else if (esc === "(" || esc === ")" || esc === "\\") bytes.push(esc.charCodeAt(0));
    else if (esc === "\r") {
      if (rawBody[i + 1] === "\n") i += 1;
    } else if (esc === "\n") {
      // line continuation, skip
    } else if (esc >= "0" && esc <= "7") {
      let oct = esc;
      if (i + 1 < rawBody.length && rawBody[i + 1] >= "0" && rawBody[i + 1] <= "7") {
        oct += rawBody[++i];
      }
      if (i + 1 < rawBody.length && rawBody[i + 1] >= "0" && rawBody[i + 1] <= "7") {
        oct += rawBody[++i];
      }
      bytes.push(parseInt(oct, 8) & 0xff);
    } else {
      bytes.push(esc.charCodeAt(0) & 0xff);
    }
  }

  const u8 = new Uint8Array(bytes);
  if (u8.length >= 2 && u8[0] === 0xfe && u8[1] === 0xff) {
    return decodeUtf16BeBytes(u8, 2);
  }
  try {
    return UTF8_DECODER.decode(u8);
  } catch {
    return LATIN1_DECODER.decode(u8);
  }
}

function decodePdfHexString(rawHex, cmapState, hasUniJisUtf16) {
  const clean = rawHex.replace(/\s+/g, "").toUpperCase();
  if (!clean) return "";

  if (clean.startsWith("FEFF") && clean.length >= 8) {
    return decodeHexAsUtf16Be(clean.slice(4));
  }

  if (cmapState.map.size > 0) {
    const widths = [...cmapState.keyLengths].sort((a, b) => b - a);
    let out = "";
    let hits = 0;
    let units = 0;
    let pos = 0;
    while (pos < clean.length) {
      let matched = false;
      for (const w of widths) {
        if (pos + w <= clean.length) {
          const seg = clean.slice(pos, pos + w);
          const mapped = cmapState.map.get(seg);
          if (mapped !== undefined) {
            out += mapped;
            hits += 1;
            units += 1;
            pos += w;
            matched = true;
            break;
          }
        }
      }
      if (!matched) {
        const step = widths.includes(4) && pos + 4 <= clean.length ? 4 : 2;
        pos += step;
        units += 1;
      }
    }
    if (units > 0 && hits / units >= 0.45 && out.trim()) {
      return out;
    }
  }

  if (clean.length % 4 === 0 && clean.length >= 4) {
    const utf16Candidate = decodeHexAsUtf16Be(clean);
    if (hasUniJisUtf16 || looksReadableText(utf16Candidate)) {
      return utf16Candidate;
    }
  }

  const bytes = hexToBytes(clean);
  try {
    const utf8 = UTF8_DECODER.decode(bytes);
    if (looksReadableText(utf8)) return utf8;
  } catch {
    // fallback below
  }
  const latin = LATIN1_DECODER.decode(bytes);
  return looksReadableText(latin) ? latin : "";
}

/**
 * Extract readable text lines from a single decoded PDF content stream string.
 */
function extractTextFromContentStream(streamStr, cmapState, hasUniJisUtf16) {
  const len = streamStr.length;
  const output = [];
  const stack = [];
  let i = 0;
  let lastTmY = null;

  const pushNewline = () => {
    if (output.length > 0 && output[output.length - 1] !== "\n") {
      output.push("\n");
    }
  };

  while (i < len) {
    const ch = streamStr[i];

    // Skip whitespace
    if (ch <= " ") {
      i += 1;
      continue;
    }

    // Skip PDF comments
    if (ch === "%") {
      while (i < len && streamStr[i] !== "\n" && streamStr[i] !== "\r") i += 1;
      continue;
    }

    // Literal string (...)
    if (ch === "(") {
      let depth = 1;
      let body = "";
      i += 1;
      while (i < len && depth > 0) {
        const c = streamStr[i];
        if (c === "\\") {
          body += c;
          if (i + 1 < len) {
            i += 1;
            body += streamStr[i];
          }
          i += 1;
          continue;
        }
        if (c === "(") depth += 1;
        else if (c === ")") {
          depth -= 1;
          if (depth === 0) {
            i += 1;
            break;
          }
        }
        body += c;
        i += 1;
      }
      stack.push({ type: "str", value: decodePdfLiteralString(body) });
      continue;
    }

    // Dictionary << ... >> (skip) vs Hex string <...>
    if (ch === "<") {
      if (streamStr[i + 1] === "<") {
        i += 2;
        continue;
      }
      i += 1;
      const start = i;
      while (i < len && streamStr[i] !== ">") i += 1;
      const hexBody = streamStr.slice(start, i);
      if (i < len) i += 1;
      stack.push({
        type: "str",
        value: decodePdfHexString(hexBody, cmapState, hasUniJisUtf16),
      });
      continue;
    }

    if (ch === ">") {
      i += 1;
      continue;
    }

    // Array [...] for TJ operator
    if (ch === "[") {
      const items = [];
      i += 1;
      while (i < len) {
        const c = streamStr[i];
        if (c <= " ") {
          i += 1;
          continue;
        }
        if (c === "]") {
          i += 1;
          break;
        }
        if (c === "(") {
          let depth = 1;
          let body = "";
          i += 1;
          while (i < len && depth > 0) {
            const sc = streamStr[i];
            if (sc === "\\") {
              body += sc;
              if (i + 1 < len) {
                i += 1;
                body += streamStr[i];
              }
              i += 1;
              continue;
            }
            if (sc === "(") depth += 1;
            else if (sc === ")") {
              depth -= 1;
              if (depth === 0) {
                i += 1;
                break;
              }
            }
            body += sc;
            i += 1;
          }
          items.push({ type: "str", value: decodePdfLiteralString(body) });
          continue;
        }
        if (c === "<" && streamStr[i + 1] !== "<") {
          i += 1;
          const start = i;
          while (i < len && streamStr[i] !== ">") i += 1;
          const hexBody = streamStr.slice(start, i);
          if (i < len) i += 1;
          items.push({
            type: "str",
            value: decodePdfHexString(hexBody, cmapState, hasUniJisUtf16),
          });
          continue;
        }
        // Number (kerning adjustment) inside TJ array
        const start = i;
        while (
          i < len &&
          streamStr[i] > " " &&
          streamStr[i] !== "]" &&
          streamStr[i] !== "(" &&
          streamStr[i] !== "<"
        ) {
          i += 1;
        }
        const numVal = Number(streamStr.slice(start, i));
        if (Number.isFinite(numVal)) {
          items.push({ type: "num", value: numVal });
        }
      }
      stack.push({ type: "arr", value: items });
      continue;
    }

    // Name /Foo
    if (ch === "/") {
      const start = i;
      i += 1;
      while (
        i < len &&
        streamStr[i] > " " &&
        !"()<>[]{}/%".includes(streamStr[i])
      ) {
        i += 1;
      }
      stack.push({ type: "name", value: streamStr.slice(start, i) });
      continue;
    }

    // Number or operator token
    const start = i;
    while (
      i < len &&
      streamStr[i] > " " &&
      !"()<>[]{}/%".includes(streamStr[i])
    ) {
      i += 1;
    }
    const token = streamStr.slice(start, i);

    if (/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(token)) {
      stack.push({ type: "num", value: Number(token) });
      continue;
    }

    // Operator dispatch
    if (token === "Tj" || token === "'" || token === '"') {
      if (token === "'" || token === '"') pushNewline();
      const top = stack.length > 0 ? stack[stack.length - 1] : null;
      if (top && top.type === "str" && top.value) {
        output.push(top.value);
      }
      stack.length = 0;
    } else if (token === "TJ") {
      const top = stack.length > 0 ? stack[stack.length - 1] : null;
      if (top && top.type === "arr") {
        let line = "";
        for (const el of top.value) {
          if (el.type === "str") {
            line += el.value;
          } else if (el.type === "num" && el.value <= -150 && line && !line.endsWith(" ")) {
            line += " ";
          }
        }
        if (line) output.push(line);
      }
      stack.length = 0;
    } else if (token === "T*") {
      pushNewline();
      stack.length = 0;
    } else if (token === "Td" || token === "TD") {
      const ty = stack.length >= 1 && stack[stack.length - 1].type === "num"
        ? stack[stack.length - 1].value
        : 0;
      if (Math.abs(ty) >= 2) {
        pushNewline();
      } else if (output.length > 0 && !/\s$/.test(output[output.length - 1])) {
        output.push(" ");
      }
      stack.length = 0;
    } else if (token === "Tm") {
      const nums = stack.filter((x) => x.type === "num").map((x) => x.value);
      if (nums.length >= 6) {
        const y = nums[nums.length - 1];
        if (lastTmY !== null && Math.abs(y - lastTmY) >= 2) {
          pushNewline();
        } else if (output.length > 0 && !/\s$/.test(output[output.length - 1])) {
          output.push(" ");
        }
        lastTmY = y;
      }
      stack.length = 0;
    } else if (token === "ET") {
      pushNewline();
      lastTmY = null;
      stack.length = 0;
    } else if (token === "BT") {
      lastTmY = null;
      stack.length = 0;
    } else {
      stack.length = 0;
    }
  }

  return output.join("");
}

function extractPdfInfoMetadata(rawLatin1) {
  const fields = [];
  for (const key of ["Title", "Subject", "Author"]) {
    const litRe = new RegExp(`\\/${key}\\s*\\(([^)]{1,300})\\)`);
    const litMatch = rawLatin1.match(litRe);
    if (litMatch) {
      const val = decodePdfLiteralString(litMatch[1]).trim();
      if (val && looksReadableText(val)) fields.push(val);
      continue;
    }
    const hexRe = new RegExp(`\\/${key}\\s*<([0-9A-Fa-f\\s]{4,600})>`);
    const hexMatch = rawLatin1.match(hexRe);
    if (hexMatch) {
      const val = decodePdfHexString(hexMatch[1], { map: new Map(), keyLengths: new Set() }, true).trim();
      if (val && looksReadableText(val)) fields.push(val);
    }
  }
  return fields.join("\n");
}

/**
 * Pure-JS local PDF text extractor.
 * Scans uncompressed & /FlateDecode PDF streams, parses ToUnicode CMaps, and
 * extracts readable Japanese/ASCII text without any external library or network call.
 *
 * @param {Uint8Array | ArrayBuffer} pdfBytes
 * @returns {Promise<{
 *   text: string,
 *   pageCount: number,
 *   streamCount: number,
 *   decompressedCount: number,
 *   isEncrypted: boolean,
 *   isLikelyScanned: boolean,
 *   warnings: string[]
 * }>}
 */
export async function extractTextFromPdfBytes(pdfBytes) {
  const bytes = toUint8Array(pdfBytes);
  const warnings = [];
  if (bytes.length === 0) {
    return {
      text: "",
      pageCount: 0,
      streamCount: 0,
      decompressedCount: 0,
      isEncrypted: false,
      isLikelyScanned: false,
      warnings: ["空のPDFデータです。"],
    };
  }

  const rawLatin1 = LATIN1_DECODER.decode(bytes);
  const isEncrypted = /\/Encrypt\s+(?:\d+\s+\d+\s+R|<<)/.test(rawLatin1);
  const pageCount = (rawLatin1.match(/\/Type\s*\/Page\b(?!s)/g) || []).length;
  const imageCount = (rawLatin1.match(/\/Subtype\s*\/Image\b/g) || []).length;
  const hasUniJisUtf16 = /\/UniJIS-UTF16-(?:H|V)\b/.test(rawLatin1);

  if (isEncrypted) {
    warnings.push("暗号化・パスワード保護PDFのため本文抽出をスキップしました（手入力可）。");
    return {
      text: "",
      pageCount,
      streamCount: 0,
      decompressedCount: 0,
      isEncrypted: true,
      isLikelyScanned: false,
      warnings,
    };
  }

  // Locate all stream...endstream blocks
  const decodedStreams = [];
  let streamCount = 0;
  let decompressedCount = 0;
  let searchPos = 0;

  while (searchPos < rawLatin1.length) {
    const streamIdx = rawLatin1.indexOf("stream", searchPos);
    if (streamIdx === -1) break;

    // Ensure `stream` is not part of `endstream` or another identifier
    const prevChar = streamIdx > 0 ? rawLatin1[streamIdx - 1] : " ";
    if (/[A-Za-z0-9_]/.test(prevChar)) {
      searchPos = streamIdx + 6;
      continue;
    }

    let dataStart = streamIdx + 6;
    if (rawLatin1[dataStart] === "\r" && rawLatin1[dataStart + 1] === "\n") {
      dataStart += 2;
    } else if (rawLatin1[dataStart] === "\n") {
      dataStart += 1;
    } else if (rawLatin1[dataStart] === "\r") {
      dataStart += 1;
    } else {
      searchPos = streamIdx + 6;
      continue;
    }

    const endIdx = rawLatin1.indexOf("endstream", dataStart);
    if (endIdx === -1) break;
    searchPos = endIdx + 9;

    let dataEnd = endIdx;
    if (dataEnd > dataStart && rawLatin1[dataEnd - 1] === "\n") dataEnd -= 1;
    if (dataEnd > dataStart && rawLatin1[dataEnd - 1] === "\r") dataEnd -= 1;
    if (dataEnd <= dataStart) continue;

    // Inspect preceding object dictionary
    const dictStart = Math.max(0, streamIdx - 1024);
    const dictHeader = rawLatin1.slice(dictStart, streamIdx);
    const lastDictIdx = dictHeader.lastIndexOf("<<");
    const objDict = lastDictIdx >= 0 ? dictHeader.slice(lastDictIdx) : dictHeader;

    // Skip raster image / binary font streams
    if (
      /\/Subtype\s*\/Image\b/.test(objDict) ||
      /\/(?:DCTDecode|JPXDecode|CCITTFaxDecode|JBIG2Decode)\b/.test(objDict) ||
      /\/Length1\b/.test(objDict)
    ) {
      continue;
    }

    streamCount += 1;
    const isFlate = /\/FlateDecode\b|\/Fl\b/.test(objDict);
    const rawSlice = bytes.subarray(dataStart, dataEnd);

    if (isFlate) {
      if (typeof DecompressionStream !== "function") {
        if (!warnings.includes("DecompressionStream非対応環境のため圧縮ストリームをスキップしました。")) {
          warnings.push("DecompressionStream非対応環境のため圧縮ストリームをスキップしました。");
        }
        continue;
      }
      const inflated = await inflateFlateBytes(rawSlice);
      if (inflated) {
        decompressedCount += 1;
        decodedStreams.push(LATIN1_DECODER.decode(inflated));
      }
    } else if (!/\/(?:LZWDecode|ASCII85Decode|RunLengthDecode)\b/.test(objDict)) {
      decodedStreams.push(LATIN1_DECODER.decode(rawSlice));
    }
  }

  // Pass 1: Build merged ToUnicode CMap from any CMap streams
  const cmapState = { map: new Map(), keyLengths: new Set() };
  for (const s of decodedStreams) {
    if (s.includes("beginbfchar") || s.includes("beginbfrange")) {
      parseToUnicodeCMap(s, cmapState);
    }
  }

  // Pass 2: Extract text operators from content streams
  const extractedChunks = [];
  for (const s of decodedStreams) {
    if (s.includes("begincmap")) continue;
    if (/\b(?:Tj|TJ|BT)\b/.test(s) || /['"]\s*(?:\n|$)/.test(s)) {
      const piece = extractTextFromContentStream(s, cmapState, hasUniJisUtf16).trim();
      if (piece) extractedChunks.push(piece);
    }
  }

  // Fallback for minimal test PDFs containing raw UTF-8 text inside content streams without BT
  let text = extractedChunks
    .join("\n")
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!text) {
    const metaText = extractPdfInfoMetadata(rawLatin1);
    if (metaText) text = metaText;
  }

  // Ensure UTF-8 safety if raw text wasn't decoded properly
  if (text && text.includes("\uFFFD")) {
    text = UTF8_LENIENT.decode(TEXT_ENCODER.encode(text)).replace(/\uFFFD/g, "");
  }

  const isLikelyScanned = text.length < 12 && imageCount > 0;
  if (isLikelyScanned) {
    warnings.push("スキャン画像PDFの可能性があります（右側プレビューを見ながら手入力できます）。");
  }

  return {
    text,
    pageCount,
    streamCount,
    decompressedCount,
    isEncrypted: false,
    isLikelyScanned,
    warnings,
  };
}

function encodeUtf16BeHex(str) {
  let hex = "";
  for (let i = 0; i < str.length; i += 1) {
    hex += str.charCodeAt(i).toString(16).toUpperCase().padStart(4, "0");
  }
  return hex;
}

function escapePdfAscii(str) {
  return String(str || "")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}

/**
 * Generate a 100% spec-compliant synthetic Japanese invoice PDF locally in memory.
 * Renders cleanly in browser PDF viewers (CID HeiseiKakuGo-W5 + Helvetica) AND
 * extracts cleanly with `extractTextFromPdfBytes` (supports optional /FlateDecode compression).
 *
 * @param {{
 *   docType?: string,
 *   invoiceNumber?: string,
 *   issueDate?: string,
 *   partnerName?: string,
 *   recipientName?: string,
 *   amountYen?: number,
 *   subtotalYen?: number,
 *   taxYen?: number,
 *   invoiceId?: string,
 *   itemDescription?: string,
 *   compress?: boolean,
 * }} spec
 * @returns {Promise<Uint8Array>}
 */
export async function createSyntheticInvoicePdfBytes({
  docType = "御請求書",
  invoiceNumber = "INV-2026-1101",
  issueDate = "令和8年11月19日",
  partnerName = "株式会社サンプル商事",
  recipientName = "合同会社ホライゾンラボ 御中",
  amountYen = 110000,
  subtotalYen = null,
  taxYen = null,
  invoiceId = "T7000012050002",
  itemDescription = "クラウド業務基盤 月額利用料（11月分）",
  compress = true,
} = {}) {
  const sub = subtotalYen !== null ? subtotalYen : Math.round(amountYen / 1.1);
  const tax = taxYen !== null ? taxYen : amountYen - sub;
  const fmtAmt = (n) => Number(n).toLocaleString("en-US");

  const ops = [
    // White page background & border accents
    "0.96 0.96 0.95 rg 0 740 595 102 re f",
    "0.10 0.23 0.33 rg 42 738 511 2 re f",
    // Header title (Japanese CID font F1)
    "0.10 0.23 0.33 rg",
    "BT /F1 22 Tf 46 785 Td",
    `<${encodeUtf16BeHex(docType)}> Tj ET`,
    // Invoice number & issue date (top right)
    "0.25 0.30 0.35 rg",
    "BT /F2 10 Tf 370 798 Td",
    `(${escapePdfAscii(`No. ${invoiceNumber}`)}) Tj ET`,
    "BT /F1 10 Tf 370 778 Td",
    `<${encodeUtf16BeHex(`発行日：${issueDate}`)}> Tj ET`,
    // Recipient (left)
    "0.10 0.12 0.15 rg",
    "BT /F1 13 Tf 46 692 Td",
    `<${encodeUtf16BeHex(recipientName)}> Tj ET`,
    "0.75 0.78 0.80 RG 0.8 w 46 682 m 290 682 l S",
    // Issuer block (right)
    "BT /F1 12 Tf 335 692 Td",
    `<${encodeUtf16BeHex(`発行元：${partnerName}`)}> Tj ET`,
    "BT /F1 9.5 Tf 335 672 Td",
    `<${encodeUtf16BeHex(`登録番号：${invoiceId}`)}> Tj ET`,
    "BT /F1 9 Tf 335 655 Td",
    `<${encodeUtf16BeHex("東京都港区虎ノ門1-2-3 ホライゾンビル5F")}> Tj ET`,
    // Grand Total Callout Box
    "0.95 0.97 0.98 rg 46 588 503 44 re f",
    "0.10 0.23 0.33 RG 1.2 w 46 588 503 44 re S",
    "0.10 0.23 0.33 rg",
    "BT /F1 12 Tf 60 605 Td",
    `<${encodeUtf16BeHex("ご請求金額（税込）")}> Tj ET`,
    "BT /F1 18 Tf 260 603 Td",
    `<${encodeUtf16BeHex(`¥${fmtAmt(amountYen)}-`)}> Tj ET`,
    // Table Header
    "0.10 0.23 0.33 rg 46 530 503 24 re f",
    "1 1 1 rg",
    "BT /F1 10 Tf 56 538 Td",
    `<${encodeUtf16BeHex("品目・摘要")}> Tj ET`,
    "BT /F1 10 Tf 440 538 Td",
    `<${encodeUtf16BeHex("金額（税抜）")}> Tj ET`,
    // Line Item Row
    "0.12 0.14 0.18 rg",
    "BT /F1 10.5 Tf 56 504 Td",
    `<${encodeUtf16BeHex(itemDescription)}> Tj ET`,
    "BT /F1 10.5 Tf 440 504 Td",
    `<${encodeUtf16BeHex(`${fmtAmt(sub)}円`)}> Tj ET`,
    "0.82 0.85 0.88 RG 0.6 w 46 490 m 549 490 l S",
    // Subtotal & Tax Summary
    "BT /F1 10 Tf 340 462 Td",
    `<${encodeUtf16BeHex(`小計：${fmtAmt(sub)}円`)}> Tj ET`,
    "BT /F1 10 Tf 340 442 Td",
    `<${encodeUtf16BeHex(`消費税（10%）：${fmtAmt(tax)}円`)}> Tj ET`,
    "BT /F1 11.5 Tf 340 416 Td",
    `<${encodeUtf16BeHex(`合計金額：${fmtAmt(amountYen)}円`)}> Tj ET`,
    // Footer note
    "0.40 0.45 0.50 rg",
    "BT /F1 8.5 Tf 46 92 Td",
    `<${encodeUtf16BeHex("※本PDFはDENCHOGATE Studioローカル動作確認用の合成サンプル請求書です。")}> Tj ET`,
  ];

  const rawContentBytes = TEXT_ENCODER.encode(`${ops.join("\n")}\n`);
  const compressed = compress ? await deflateFlateBytes(rawContentBytes) : null;
  const streamBytes = compressed || rawContentBytes;
  const streamFilter = compressed ? " /Filter /FlateDecode" : "";

  const objects = [
    // 1: Catalog
    TEXT_ENCODER.encode("<< /Type /Catalog /Pages 2 0 R >>"),
    // 2: Pages
    TEXT_ENCODER.encode("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    // 3: Page
    TEXT_ENCODER.encode(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 6 0 R >> >> /Contents 7 0 R >>",
    ),
    // 4: Type0 Japanese CID Font
    TEXT_ENCODER.encode(
      "<< /Type /Font /Subtype /Type0 /BaseFont /HeiseiKakuGo-W5 /Encoding /UniJIS-UTF16-H /DescendantFonts [5 0 R] >>",
    ),
    // 5: CIDFontType0 Descendant
    TEXT_ENCODER.encode(
      "<< /Type /Font /Subtype /CIDFontType0 /BaseFont /HeiseiKakuGo-W5 /CIDSystemInfo << /Registry (Adobe) /Ordering (Japan1) /Supplement 6 >> /DW 1000 >>",
    ),
    // 6: Helvetica ASCII fallback font
    TEXT_ENCODER.encode("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
  ];

  // Build binary PDF with accurate xref byte offsets
  const chunks = [];
  let cursor = 0;
  const pushBytes = (u8) => {
    chunks.push(u8);
    cursor += u8.byteLength;
  };
  const pushStr = (s) => pushBytes(TEXT_ENCODER.encode(s));

  pushBytes(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]));

  const offsets = [0]; // obj 0 free entry
  for (let i = 0; i < objects.length; i += 1) {
    offsets.push(cursor);
    pushStr(`${i + 1} 0 obj\n`);
    pushBytes(objects[i]);
    pushStr("\nendobj\n");
  }

  // Object 7: Content Stream
  offsets.push(cursor);
  pushStr(`7 0 obj\n<< /Length ${streamBytes.byteLength}${streamFilter} >>\nstream\n`);
  pushBytes(streamBytes);
  pushStr("\nendstream\nendobj\n");

  const xrefStart = cursor;
  pushStr(`xref\n0 ${offsets.length}\n`);
  pushStr("0000000000 65535 f \n");
  for (let i = 1; i < offsets.length; i += 1) {
    pushStr(`${String(offsets[i]).padStart(10, "0")} 00000 n \n`);
  }
  pushStr(`trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`);

  const finalPdf = new Uint8Array(cursor);
  let pos = 0;
  for (const c of chunks) {
    finalPdf.set(c, pos);
    pos += c.byteLength;
  }
  return finalPdf;
}
