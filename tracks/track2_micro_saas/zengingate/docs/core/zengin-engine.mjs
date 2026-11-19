/**
 * ZENGINGATE v2.0 (全銀門) — 100% Browser-Local Bank-Ready Zengin 120-Byte Shift-JIS (CP932) Engine
 *
 * Implements:
 *   1. Pure-JS Shift-JIS (CP932 / JIS X 0201) Binary Encoder (`encodeZenginShiftJis`) & Smart Decoder (`decodeZenginBytes`).
 *   2. Official Zengin 120-Byte Spec (総合振込 21 / 給与振込 11 / 賞与振込 12) + 7 Japanese Bank Presets.
 *   3. Official Zengin Positional Corporate Abbreviations (25+ entity types: 前株 ｶ) / 後株 (ｶ / 中株 (ｶ)) + Dakuten-Safe 30-Byte Truncation.
 *   4. Strict Unsupported Character (Kanji) Reporting — never silently hides kanji corruption.
 *   5. RFC-4180 CSV/TSV Parser + Auto Column Mapper (freee / MoneyForward / 弥生 / Excel / English).
 *   6. 1-Click Bank-Rejected Zengin File Diagnostics & Auto-Repair (`diagnoseAndRepairZenginFile`).
 *   7. NTA Modulo-9 Qualified Invoice ID (T+13 digits) & Corporate Number (13 digits) Verification.
 *
 * Zero external dependencies; zero network calls.
 */

const FULL_HIRAGANA_START = 0x3041;
const FULL_HIRAGANA_END = 0x3096;

/**
 * Official Zengin 120-Byte Transfer Types (種別コード Pos 2-3).
 */
export const TRANSFER_TYPES = {
  "21": { code: "21", label: "総合振込", shortLabel: "総合(21)", description: "取引先・買掛金などの一般振込" },
  "11": { code: "11", label: "給与振込", shortLabel: "給与(11)", description: "従業員への月次給与振込" },
  "12": { code: "12", label: "賞与振込", shortLabel: "賞与(12)", description: "従業員への賞与振込" },
};

/**
 * Bank Presets controlling CRLF vs continuous 120B, EOF (0x1A), and Clearing House Code (Pos 39-42).
 */
export const BANK_PRESETS = {
  standard: {
    id: "standard",
    label: "全銀標準（汎用）",
    bankCode: "",
    lineEnding: "CRLF",
    includeEof: false,
    clearingHouseCode: "    ",
    note: "全銀協標準仕様：Shift-JIS / 120バイト / CRLF改行 / EOFなし / 交換所スペース",
  },
  mufg: {
    id: "mufg",
    label: "三菱UFJ銀行（BizSTATION）",
    bankCode: "0005",
    lineEnding: "CRLF",
    includeEof: false,
    clearingHouseCode: "    ",
    note: "BizSTATION標準：Shift-JIS / 120バイト / CRLF改行 / EOFなし / 交換所スペース",
  },
  smbc: {
    id: "smbc",
    label: "三井住友銀行（Web21）",
    bankCode: "0009",
    lineEnding: "CRLF",
    includeEof: true,
    clearingHouseCode: "0000",
    note: "SMBC Web21標準：Shift-JIS / 120バイト / CRLF改行 / EOF(0x1A)付与 / 交換所0000",
  },
  mizuho: {
    id: "mizuho",
    label: "みずほ銀行（みずほe-ビジネス）",
    bankCode: "0001",
    lineEnding: "NONE",
    includeEof: false,
    clearingHouseCode: "0000",
    note: "みずほe-ビジネス固定長：Shift-JIS / 120バイト連続(改行なし) / 交換所0000（CRLF切替可）",
  },
  rakuten: {
    id: "rakuten",
    label: "楽天銀行（法人ビジネス口座）",
    bankCode: "0036",
    lineEnding: "CRLF",
    includeEof: false,
    clearingHouseCode: "    ",
    note: "楽天銀行法人標準：Shift-JIS / 120バイト / CRLF改行 / EOFなし / 交換所スペース",
  },
  sbi: {
    id: "sbi",
    label: "住信SBIネット銀行（法人口座）",
    bankCode: "0038",
    lineEnding: "CRLF",
    includeEof: false,
    clearingHouseCode: "    ",
    note: "住信SBIネット銀行標準：Shift-JIS / 120バイト / CRLF改行 / EOFなし / 交換所スペース",
  },
  gmo: {
    id: "gmo",
    label: "GMOあおぞらネット銀行",
    bankCode: "0310",
    lineEnding: "CRLF",
    includeEof: false,
    clearingHouseCode: "    ",
    note: "GMOあおぞらネット銀行標準：Shift-JIS / 120バイト / CRLF改行 / EOFなし / 交換所スペース",
  },
};

/**
 * Official Zengin bank kana lookup for major Japanese financial institutions (for optional Pos 6-20 convenience).
 */
export const MAJOR_BANKS = {
  "0001": "ﾐｽﾞﾎ",
  "0005": "ﾐﾂﾋﾞｼUFJ",
  "0009": "ﾐﾂｲｽﾐﾄﾓ",
  "0010": "ﾘｿﾅ",
  "0017": "ｻｲﾀﾏﾘｿﾅ",
  "0033": "PAYPAY",
  "0034": "ｾﾌﾞﾝ",
  "0035": "ｿﾆ-",
  "0036": "ﾗｸﾃﾝ",
  "0038": "ｽﾐｼﾝSBIﾈﾂﾄ",
  "0039": "AUｼﾞﾌﾞﾝ",
  "0040": "ｲｵﾝ",
  "0041": "ﾀﾞｲﾜﾈｸｽﾄ",
  "0042": "ﾛ-ｿﾝ",
  "0043": "ﾐﾝﾅﾉ",
  "0044": "UI",
  "0116": "ﾎﾂｶｲﾄﾞｳ",
  "0125": "ｼﾁｼﾞﾕｳｼﾁ",
  "0129": "ﾄｳﾎｳ",
  "0130": "ｼﾞﾖｳﾖｳ",
  "0134": "ﾁﾊﾞ",
  "0137": "ｷﾗﾎﾞｼ",
  "0138": "ﾖｺﾊﾏ",
  "0149": "ｼｽﾞｵｶ",
  "0153": "ｼﾞﾕｳﾛｸ",
  "0157": "ｼｶﾞ",
  "0158": "ｷﾖｳﾄ",
  "0159": "ｶﾝｻｲﾐﾗｲ",
  "0162": "ﾅﾝﾄ",
  "0168": "ﾁﾕｳｺﾞｸ",
  "0169": "ﾋﾛｼﾏ",
  "0170": "ﾔﾏｸﾞﾁ",
  "0174": "ｲﾖ",
  "0177": "ﾌｸｵｶ",
  "0190": "ﾆｼﾆﾎﾝｼﾃｲ",
  "0288": "ﾐﾂﾋﾞｼUFJｼﾝﾀｸ",
  "0289": "ﾐｽﾞﾎｼﾝﾀｸ",
  "0294": "ﾐﾂｲｽﾐﾄﾓｼﾝﾀｸ",
  "0310": "GMOｱｵｿﾞﾗﾈﾂﾄ",
  "0397": "SBIｼﾝｾｲ",
  "0398": "ｱｵｿﾞﾗ",
  "9900": "ﾕｳﾁﾖ",
};

const COMMON_BRANCH_KANJI_MAP = {
  本店: "ﾎﾝﾃﾝ",
  本店営業部: "ﾎﾝﾃﾝｴｲｷﾞﾖｳﾌﾞ",
  東京営業部: "ﾄｳｷﾖｳｴｲｷﾞﾖｳﾌﾞ",
  大阪営業部: "ｵｵｻｶｴｲｷﾞﾖｳﾌﾞ",
};

/**
 * Official Zengin Positional Legal Entity & Organization Abbreviations (28+ entity types).
 * Ordered longest-first so compound designations match cleanly before shorter substrings.
 * Positional rule:
 *   - Prefix (start of name):  ABBR)
 *   - Suffix (end of name):    (ABBR
 *   - Infix (middle or solo):  (ABBR)
 */
export const LEGAL_ENTITY_ABBREVIATIONS = [
  { pattern: "認定特定非営利活動法人", abbr: "ﾄｸﾋ" },
  { pattern: "特定非営利活動法人", abbr: "ﾄｸﾋ" },
  { pattern: "地方独立行政法人", abbr: "ﾁﾄﾞｸ" },
  { pattern: "社会保険労務士法人", abbr: "ｼﾔﾛｳ" },
  { pattern: "NPO法人", abbr: "ﾄｸﾋ" },
  { pattern: "独立行政法人", abbr: "ﾄﾞｸ" },
  { pattern: "一般社団法人", abbr: "ｼﾔ" },
  { pattern: "公益社団法人", abbr: "ｼﾔ" },
  { pattern: "一般財団法人", abbr: "ｻﾞｲ" },
  { pattern: "公益財団法人", abbr: "ｻﾞｲ" },
  { pattern: "医療法人社団", abbr: "ｲ" },
  { pattern: "医療法人財団", abbr: "ｲ" },
  { pattern: "社会医療法人", abbr: "ｲ" },
  { pattern: "社会福祉法人", abbr: "ﾌｸ" },
  { pattern: "健康保険組合", abbr: "ｹﾝﾎﾟ" },
  { pattern: "農業協同組合", abbr: "ﾉｳｷﾖｳ" },
  { pattern: "生活協同組合", abbr: "ｾｲｷﾖｳ" },
  { pattern: "事業協同組合", abbr: "ｸﾐ" },
  { pattern: "司法書士法人", abbr: "ｼﾎ" },
  { pattern: "行政書士法人", abbr: "ｷﾞﾖｳ" },
  { pattern: "税理士法人", abbr: "ｾﾞｲ" },
  { pattern: "弁護士法人", abbr: "ﾍﾞﾝ" },
  { pattern: "弁理士法人", abbr: "ﾍﾞﾝﾘ" },
  { pattern: "株式会社", abbr: "ｶ" },
  { pattern: "有限会社", abbr: "ﾕ" },
  { pattern: "合同会社", abbr: "ﾄﾞ" },
  { pattern: "合名会社", abbr: "ﾒ" },
  { pattern: "合資会社", abbr: "ｼ" },
  { pattern: "医療法人", abbr: "ｲ" },
  { pattern: "社団法人", abbr: "ｼﾔ" },
  { pattern: "財団法人", abbr: "ｻﾞｲ" },
  { pattern: "学校法人", abbr: "ｶﾞｸ" },
  { pattern: "宗教法人", abbr: "ｼﾕｳ" },
  { pattern: "監査法人", abbr: "ｶﾝｻ" },
  { pattern: "協同組合", abbr: "ｸﾐ" },
  { pattern: "労働組合", abbr: "ﾛｳｸﾐ" },
  { pattern: "信用金庫", abbr: "ｼﾝｷﾝ" },
  { pattern: "信用組合", abbr: "ｼﾝｸﾐ" },
  { pattern: "(特非)", abbr: "ﾄｸﾋ" },
  { pattern: "営業所", abbr: "ｴｲ" },
  { pattern: "出張所", abbr: "ｼﾕﾂ" },
  { pattern: "(株)", abbr: "ｶ" },
  { pattern: "(有)", abbr: "ﾕ" },
  { pattern: "(同)", abbr: "ﾄﾞ" },
  { pattern: "(名)", abbr: "ﾒ" },
  { pattern: "(資)", abbr: "ｼ" },
  { pattern: "(医)", abbr: "ｲ" },
  { pattern: "(社)", abbr: "ｼﾔ" },
  { pattern: "(財)", abbr: "ｻﾞｲ" },
  { pattern: "(福)", abbr: "ﾌｸ" },
  { pattern: "(学)", abbr: "ｶﾞｸ" },
  { pattern: "(宗)", abbr: "ｼﾕｳ" },
  { pattern: "(税)", abbr: "ｾﾞｲ" },
  { pattern: "(弁)", abbr: "ﾍﾞﾝ" },
  { pattern: "(司)", abbr: "ｼﾎ" },
  { pattern: "合名", abbr: "ﾒ" },
  { pattern: "合資", abbr: "ｼ" },
  { pattern: "組合", abbr: "ｸﾐ" },
  { pattern: "支店", abbr: "ｼﾃﾝ" },
  { pattern: "㈱", abbr: "ｶ" },
  { pattern: "㈲", abbr: "ﾕ" },
  { pattern: "㈹", abbr: "ﾀﾞｲ" },
];

const BASE_KANA_MAP = {
  ア: "ｱ", イ: "ｲ", ウ: "ｳ", エ: "ｴ", オ: "ｵ",
  ァ: "ｱ", ィ: "ｲ", ゥ: "ｳ", ェ: "ｴ", ォ: "ｵ",
  カ: "ｶ", キ: "ｷ", ク: "ｸ", ケ: "ｹ", コ: "ｺ",
  サ: "ｻ", シ: "ｼ", ス: "ｽ", セ: "ｾ", ソ: "ｿ",
  タ: "ﾀ", チ: "ﾁ", ツ: "ﾂ", テ: "ﾃ", ト: "ﾄ",
  ッ: "ﾂ",
  ナ: "ﾅ", ニ: "ﾆ", ヌ: "ﾇ", ネ: "ﾈ", ノ: "ﾉ",
  ハ: "ﾊ", ヒ: "ﾋ", フ: "ﾌ", ヘ: "ﾍ", ホ: "ﾎ",
  マ: "ﾏ", ミ: "ﾐ", ム: "ﾑ", メ: "ﾒ", モ: "ﾓ",
  ヤ: "ﾔ", ユ: "ﾕ", ヨ: "ﾖ",
  ャ: "ﾔ", ュ: "ﾕ", ョ: "ﾖ",
  ラ: "ﾗ", リ: "ﾘ", ル: "ﾙ", レ: "ﾚ", ロ: "ﾛ",
  ワ: "ﾜ", ヲ: "ｦ", ン: "ﾝ",
  ヮ: "ﾜ", ヵ: "ｶ", ヶ: "ｹ", ヰ: "ｲ", ヱ: "ｴ",
  ガ: "ｶﾞ", ギ: "ｷﾞ", グ: "ｸﾞ", ゲ: "ｹﾞ", ゴ: "ｺﾞ",
  ザ: "ｻﾞ", ジ: "ｼﾞ", ズ: "ｽﾞ", ゼ: "ｾﾞ", ゾ: "ｿﾞ",
  ダ: "ﾀﾞ", ヂ: "ﾁﾞ", ヅ: "ﾂﾞ", デ: "ﾃﾞ", ド: "ﾄﾞ",
  バ: "ﾊﾞ", ビ: "ﾋﾞ", ブ: "ﾌﾞ", ベ: "ﾍﾞ", ボ: "ﾎﾞ",
  パ: "ﾊﾟ", ピ: "ﾋﾟ", プ: "ﾌﾟ", ペ: "ﾍﾟ", ポ: "ﾎﾟ",
  ヴ: "ｳﾞ",
  // Half-width small katakana promoted to full half-width per Zengin spec
  ｧ: "ｱ", ｨ: "ｲ", ｩ: "ｳ", ｪ: "ｴ", ｫ: "ｵ", ｯ: "ﾂ", ｬ: "ﾔ", ｭ: "ﾕ", ｮ: "ﾖ",
  // Prolonged vowel / spaces / punctuation
  ー: "-", ｰ: "-", "－": "-", "―": "-", "−": "-", "‐": "-", "–": "-", "—": "-",
  "　": " ", "．": ".", "（": "(", "）": ")", "／": "/", "，": ",", "、": ",", "・": ".",
  "「": "｢", "」": "｣", "¥": "\\", "￥": "\\",
};

// Official Zengin character set: A-Z, 0-9, ｦ, ｱ-ﾝ, ﾞ, ﾟ, space, -, ., (, ), /, ,, \, ｢, ｣
const ZENGIN_LEGAL_RE = /^[A-Z0-9ｦｱ-ﾝﾞﾟ \-\.\(\)\/,\\｢｣]*$/;
const ZENGIN_LEGAL_CHAR_RE = /^[A-Z0-9ｦｱ-ﾝﾞﾟ \-\.\(\)\/,\\｢｣]$/;

/**
 * Normalize full-width ASCII digits/letters/symbols into half-width ASCII.
 */
export function normalizeIdentifierWidth(raw) {
  return String(raw ?? "").replace(/[！-～]/g, (ch) =>
    String.fromCharCode(ch.charCodeAt(0) - 0xfee0),
  );
}

/**
 * Pure-JS Shift-JIS (CP932 / JIS X 0201) binary encoder for Zengin 120-byte records.
 * Maps:
 *   - ASCII 0x20-0x7E -> exact single byte 0x20-0x7E
 *   - Yen sign U+00A5 -> 0x5C
 *   - Half-width Katakana U+FF61-U+FF9F -> exact single Shift-JIS byte 0xA1-0xDF (e.g. ｱ=0xB1, ｶ=0xB6, ﾞ=0xDE, ﾟ=0xDF)
 *   - Control chars CR (0x0D), LF (0x0A), SUB/EOF (0x1A) -> exact control byte
 * Throws on any non-single-byte / illegal character so byte alignment can never silently drift.
 */
export function encodeZenginShiftJis(text, { includeEof = false, lineEnding = null } = {}) {
  let payload = String(text ?? "");
  if (lineEnding === "CRLF") {
    payload = payload.replace(/\r?\n/g, "\r\n");
  } else if (lineEnding === "NONE") {
    payload = payload.replace(/\r?\n/g, "");
  }

  const out = [];
  for (let i = 0; i < payload.length; i += 1) {
    const code = payload.charCodeAt(i);
    if (code === 0x0d || code === 0x0a || code === 0x1a) {
      out.push(code);
    } else if (code >= 0x20 && code <= 0x7e) {
      out.push(code);
    } else if (code === 0x00a5) {
      out.push(0x5c);
    } else if (code >= 0xff61 && code <= 0xff9f) {
      out.push(code - 0xff61 + 0xa1);
    } else {
      const hex = code.toString(16).toUpperCase().padStart(4, "0");
      throw new Error(
        `Shift-JIS(全銀1バイト規格)でエンコードできない文字です: "${payload[i]}" (U+${hex}, 位置 ${i + 1})`,
      );
    }
  }

  if (includeEof && (out.length === 0 || out[out.length - 1] !== 0x1a)) {
    out.push(0x1a);
  }
  return new Uint8Array(out);
}

/**
 * Inspect raw bytes (Shift-JIS CP932 or UTF-8 with/without BOM) and decode cleanly into text + forensics.
 */
export function decodeZenginBytes(input) {
  if (typeof input === "string") {
    const hasBom = input.startsWith("\uFEFF");
    const strippedBom = hasBom ? input.slice(1) : input;
    const hasEofMarker = strippedBom.endsWith("\x1a");
    const text = hasEofMarker ? strippedBom.slice(0, -1) : strippedBom;
    const lineEnding = text.includes("\r\n") ? "CRLF" : text.includes("\n") ? "LF" : "NONE";
    return {
      text,
      encoding: hasBom ? "utf-8-bom" : "string",
      hasBom,
      hasEofMarker,
      lineEnding,
      byteLength: new TextEncoder().encode(input).length,
    };
  }

  const rawBytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const rawByteLength = rawBytes.length;

  const hasBom =
    rawBytes.length >= 3 && rawBytes[0] === 0xef && rawBytes[1] === 0xbb && rawBytes[2] === 0xbf;
  let body = hasBom ? rawBytes.subarray(3) : rawBytes;

  const hasEofMarker = body.length > 0 && body[body.length - 1] === 0x1a;
  if (hasEofMarker) {
    body = body.subarray(0, body.length - 1);
  }

  // Detect line ending from raw bytes
  let hasCrLf = false;
  let hasBareLf = false;
  for (let i = 0; i < body.length; i += 1) {
    if (body[i] === 0x0a) {
      if (i > 0 && body[i - 1] === 0x0d) hasCrLf = true;
      else hasBareLf = true;
    }
  }
  const lineEnding = hasCrLf ? "CRLF" : hasBareLf ? "LF" : "NONE";

  let hasHighByte = false;
  let allHighInHalfKana = true;
  for (let i = 0; i < body.length; i += 1) {
    const b = body[i];
    if (b >= 0x80) {
      hasHighByte = true;
      if (b < 0xa1 || b > 0xdf) {
        allHighInHalfKana = false;
      }
    }
  }

  if (hasBom) {
    return {
      text: new TextDecoder("utf-8").decode(body),
      encoding: "utf-8-bom",
      hasBom: true,
      hasEofMarker,
      lineEnding,
      byteLength: rawByteLength,
    };
  }

  if (!hasHighByte) {
    return {
      text: new TextDecoder("ascii").decode(body),
      encoding: "ascii",
      hasBom: false,
      hasEofMarker,
      lineEnding,
      byteLength: rawByteLength,
    };
  }

  // Guard against Shift-JIS half-width katakana bytes (0xA1-0xDF) coincidentally matching valid 2-byte UTF-8
  // (e.g. ﾅｶ = 0xC5 0xB6 = valid UTF-8 "Ŷ") when the payload already has exact 120-byte Zengin record geometry!
  if (allHighInHalfKana && looksLikeFixed120ByteZengin(body)) {
    return {
      text: new TextDecoder("shift_jis").decode(body),
      encoding: "shift_jis",
      hasBom: false,
      hasEofMarker,
      lineEnding,
      byteLength: rawByteLength,
    };
  }

  try {
    const utf8Text = new TextDecoder("utf-8", { fatal: true }).decode(body);
    // If UTF-8 decoded cleanly, verify whether it actually contains Japanese/CJK/full-width chars
    // rather than mojibake Latin Extended characters produced from Shift-JIS katakana pairs.
    const hasJapaneseUnicode = /[\u3000-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]/.test(utf8Text);
    if (!hasJapaneseUnicode && allHighInHalfKana) {
      return {
        text: new TextDecoder("shift_jis").decode(body),
        encoding: "shift_jis",
        hasBom: false,
        hasEofMarker,
        lineEnding,
        byteLength: rawByteLength,
      };
    }
    return {
      text: utf8Text,
      encoding: "utf-8",
      hasBom: false,
      hasEofMarker,
      lineEnding,
      byteLength: rawByteLength,
    };
  } catch {
    return {
      text: new TextDecoder("shift_jis").decode(body),
      encoding: "shift_jis",
      hasBom: false,
      hasEofMarker,
      lineEnding,
      byteLength: rawByteLength,
    };
  }
}

function looksLikeFixed120ByteZengin(bytes) {
  if (bytes.length < 120) return false;
  const records = [];
  let start = 0;
  let sawNewline = false;
  for (let i = 0; i < bytes.length; i += 1) {
    if (bytes[i] === 0x0a) {
      sawNewline = true;
      const end = i > start && bytes[i - 1] === 0x0d ? i - 1 : i;
      if (end > start) records.push(bytes.subarray(start, end));
      start = i + 1;
    }
  }
  if (start < bytes.length) {
    records.push(bytes.subarray(start));
  }

  if (!sawNewline) {
    if (bytes.length % 120 !== 0) return false;
    for (let pos = 0; pos < bytes.length; pos += 120) {
      const lead = bytes[pos];
      if (lead !== 0x31 && lead !== 0x32 && lead !== 0x38 && lead !== 0x39) return false;
    }
    return true;
  }

  if (records.length === 0) return false;
  return records.every(
    (rec) =>
      rec.length === 120 &&
      (rec[0] === 0x31 || rec[0] === 0x32 || rec[0] === 0x38 || rec[0] === 0x39),
  );
}

/**
 * Verify a 13-digit Japanese Corporate Number using NTA modulo-9 check digit.
 * Formula: check_digit = 9 - (sum_{n=1..12} (n%2 ? 1 : 2) * q_n) % 9 (rightmost digit has index 1).
 */
export function verifyCorporateNumberMod9(raw) {
  const digits = normalizeIdentifierWidth(raw).replace(/[-\s]/g, "");
  if (!/^\d{13}$/.test(digits)) {
    return { valid: false, normalized: digits, reason: "法人番号は13桁の数字である必要があります。" };
  }
  const actualCheck = Number(digits[0]);
  let weightedSum = 0;
  for (let i = 1; i <= 12; i += 1) {
    const q = Number(digits[13 - i]);
    const weight = i % 2 === 1 ? 1 : 2;
    weightedSum += q * weight;
  }
  const expectedCheck = 9 - (weightedSum % 9);
  const valid = actualCheck === expectedCheck;
  return {
    valid,
    normalized: digits,
    expectedCheckDigit: expectedCheck,
    actualCheckDigit: actualCheck,
    reason: valid ? "OK" : `検査数字不一致（期待値 ${expectedCheck}, 入力値 ${actualCheck}）`,
  };
}

/**
 * Verify a Japanese Qualified Invoice ID (`T` + 13 digits).
 */
export function verifyQualifiedInvoiceId(raw) {
  const norm = normalizeIdentifierWidth(raw).replace(/[-\s]/g, "").toUpperCase();
  const match = norm.match(/^T(\d{13})$/);
  if (!match) {
    return { valid: false, normalized: norm, reason: "適格請求書発行事業者登録番号は T + 13桁です。" };
  }
  const corpRes = verifyCorporateNumberMod9(match[1]);
  return {
    ...corpRes,
    normalized: `T${match[1]}`,
  };
}

/**
 * Scan raw text or multiline list and verify every T-number / 13-digit Corporate ID found.
 */
export function verifyBatchIdentifiers(text) {
  const normalizedText = normalizeIdentifierWidth(text).toUpperCase();
  const lines = normalizedText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const items = [];
  for (let idx = 0; idx < lines.length; idx += 1) {
    const line = lines[idx];
    const compact = line.replace(/[-\s]/g, "");
    if (/^T\d{13}$/.test(compact)) {
      items.push({ line: idx + 1, input: line, kind: "INVOICE_ID", ...verifyQualifiedInvoiceId(compact) });
    } else if (/^\d{13}$/.test(compact)) {
      items.push({ line: idx + 1, input: line, kind: "CORPORATE_ID", ...verifyCorporateNumberMod9(compact) });
    } else {
      items.push({
        line: idx + 1,
        input: line,
        kind: "UNKNOWN",
        normalized: compact,
        valid: false,
        reason: "T+13桁または13桁の数字として解釈できません。",
      });
    }
  }
  const validCount = items.filter((r) => r.valid).length;
  return { total: items.length, validCount, invalidCount: items.length - validCount, items };
}

/**
 * Apply official Zengin positional corporate abbreviations (前株 ｶ) / 後株 (ｶ / 中株 (ｶ)).
 */
function applyPositionalLegalAbbreviations(normalizedStr) {
  const trimmed = normalizedStr.replace(/　/g, " ").trim();
  if (!trimmed) return "";

  const matches = [];
  let cursor = 0;
  while (cursor < trimmed.length) {
    let found = null;
    for (const entry of LEGAL_ENTITY_ABBREVIATIONS) {
      if (trimmed.startsWith(entry.pattern, cursor)) {
        found = entry;
        break;
      }
    }
    if (found) {
      matches.push({ start: cursor, end: cursor + found.pattern.length, abbr: found.abbr });
      cursor += found.pattern.length;
    } else {
      cursor += 1;
    }
  }

  if (matches.length === 0) return trimmed;

  let out = "";
  let pos = 0;
  for (let i = 0; i < matches.length; i += 1) {
    const m = matches[i];
    let beforeSegment = trimmed.slice(pos, m.start);
    const hasTextBefore = trimmed.slice(0, m.start).trim().length > 0;
    const hasTextAfter = trimmed.slice(m.end).trim().length > 0;

    let replacement;
    if (!hasTextBefore && hasTextAfter) {
      // Prefix (前株): ｶ)〇〇
      replacement = `${m.abbr})`;
    } else if (hasTextBefore && !hasTextAfter) {
      // Suffix (後株): 〇〇(ｶ
      beforeSegment = beforeSegment.replace(/\s+$/, "");
      replacement = `(${m.abbr}`;
    } else {
      // Infix (中株) or standalone: 〇〇(ｶ)△△ or (ｶ)
      beforeSegment = beforeSegment.replace(/\s+$/, "");
      replacement = `(${m.abbr})`;
    }

    out += beforeSegment + replacement;
    pos = m.end;

    // Trim whitespace immediately after prefix or infix abbreviation per Zengin convention
    if (hasTextAfter) {
      while (pos < trimmed.length && /\s/.test(trimmed[pos])) {
        pos += 1;
      }
    }
  }
  out += trimmed.slice(pos);
  return out;
}

/**
 * Convert Japanese text (Hiragana, Katakana, ASCII, full-width symbols, 25+ legal entity types)
 * to Zengin-compliant half-width string with Dakuten-Safe truncation and strict unsupported character reporting.
 */
export function toZenginHalfWidth(raw, { maxLength = 30, stripUnsupported = true } = {}) {
  const widthNorm = normalizeIdentifierWidth(String(raw ?? "")).toUpperCase();
  const withLegalAbbr = applyPositionalLegalAbbreviations(widthNorm);

  const out = [];
  const unsupported = [];
  for (const rawCh of withLegalAbbr) {
    const code = rawCh.charCodeAt(0);
    // Convert Hiragana to Katakana first
    const ch =
      code >= FULL_HIRAGANA_START && code <= FULL_HIRAGANA_END
        ? String.fromCharCode(code + 0x60)
        : rawCh;

    if (Object.prototype.hasOwnProperty.call(BASE_KANA_MAP, ch)) {
      out.push(BASE_KANA_MAP[ch]);
      continue;
    }
    if (ZENGIN_LEGAL_CHAR_RE.test(ch)) {
      out.push(ch);
      continue;
    }
    unsupported.push(rawCh);
    if (!stripUnsupported) {
      out.push("?");
    }
  }

  let result = out.join("").replace(/\s{2,}/g, " ").trim();
  const truncated = result.length > maxLength;
  let dakutenSafeAdjusted = false;

  if (truncated) {
    let cut = maxLength;
    // Never sever a voiced/semi-voiced kana at the truncation boundary (e.g. ｶﾞ -> ｶ)
    if (cut > 0 && (result[cut] === "ﾞ" || result[cut] === "ﾟ")) {
      cut -= 1;
      dakutenSafeAdjusted = true;
    }
    result = result.slice(0, cut).trimEnd();
  }

  const uniqueUnsupported = [...new Set(unsupported)];
  const hasErrors = uniqueUnsupported.length > 0;

  return {
    zenginText: result,
    byteLength: result.length,
    truncated,
    dakutenSafeAdjusted,
    unsupportedChars: uniqueUnsupported,
    invalidChars: uniqueUnsupported,
    hasErrors,
    isLegal: !hasErrors && ZENGIN_LEGAL_RE.test(result),
  };
}

function padZenginAlpha(str, width) {
  const clean = toZenginHalfWidth(str, { maxLength: width }).zenginText;
  return clean.padEnd(width, " ");
}

function padZenginNumeric(val, width) {
  const digits = normalizeIdentifierWidth(String(val ?? "0")).replace(/\D/g, "");
  if (digits.length > width) {
    throw new Error(`数値フィールド超過 (${digits.length} > ${width}桁): ${val}`);
  }
  return digits.padStart(width, "0");
}

function resolveBankNameForZengin(bankName, bankCode) {
  const raw = String(bankName ?? "").trim();
  const code = normalizeIdentifierWidth(String(bankCode ?? "")).replace(/\D/g, "").padStart(4, "0");
  if (!raw && MAJOR_BANKS[code]) {
    return { text: MAJOR_BANKS[code], autoResolved: true, invalidChars: [] };
  }
  const conv = toZenginHalfWidth(raw, { maxLength: 15 });
  if (conv.hasErrors && MAJOR_BANKS[code]) {
    return { text: MAJOR_BANKS[code], autoResolved: true, invalidChars: conv.invalidChars };
  }
  return { text: conv.zenginText, autoResolved: false, invalidChars: conv.invalidChars };
}

function resolveBranchNameForZengin(branchName) {
  const raw = String(branchName ?? "").trim();
  if (!raw) return { text: "", autoResolved: false, invalidChars: [] };
  if (Object.prototype.hasOwnProperty.call(COMMON_BRANCH_KANJI_MAP, raw)) {
    return { text: COMMON_BRANCH_KANJI_MAP[raw], autoResolved: true, invalidChars: [] };
  }
  const conv = toZenginHalfWidth(raw, { maxLength: 15 });
  return { text: conv.zenginText, autoResolved: false, invalidChars: conv.invalidChars };
}

/**
 * Validate Header settings before generating a Zengin file.
 */
export function validateHeader(header = {}) {
  const errors = [];
  const warnings = [];
  const transferType = String(header.transferType ?? "21");
  if (!Object.prototype.hasOwnProperty.call(TRANSFER_TYPES, transferType)) {
    errors.push({ field: "transferType", message: `種別コードは 21/11/12 のいずれかです (${transferType})` });
  }

  const reqCodeDigits = normalizeIdentifierWidth(String(header.requesterCode ?? "")).replace(/\D/g, "");
  if (reqCodeDigits.length === 0 || reqCodeDigits.length > 10) {
    errors.push({ field: "requesterCode", message: "委託者コードは1〜10桁の数字で入力してください。" });
  }

  const reqNameConv = toZenginHalfWidth(header.requesterName ?? "", { maxLength: 40 });
  if (!reqNameConv.zenginText && !reqNameConv.hasErrors) {
    errors.push({ field: "requesterName", message: "委託者名を入力してください。" });
  }
  if (reqNameConv.hasErrors) {
    errors.push({
      field: "requesterName",
      invalidChars: reqNameConv.invalidChars,
      message: `委託者名に全銀不可文字が含まれています: ${reqNameConv.invalidChars.join(" ")}`,
    });
  }
  if (reqNameConv.truncated) {
    warnings.push({ field: "requesterName", message: "委託者名が40バイトを超過したため末尾を切り捨てました。" });
  }

  const mmdd = normalizeIdentifierWidth(String(header.transferDateMMDD ?? "")).replace(/\D/g, "");
  if (mmdd.length !== 4) {
    errors.push({ field: "transferDateMMDD", message: "振込指定日は4桁(MMDD)で入力してください。" });
  } else {
    const mm = Number(mmdd.slice(0, 2));
    const dd = Number(mmdd.slice(2, 4));
    if (mm < 1 || mm > 12 || dd < 1 || dd > 31) {
      errors.push({ field: "transferDateMMDD", message: `振込指定日(MMDD)が不正です: ${mmdd}` });
    }
  }

  const srcBankDigits = normalizeIdentifierWidth(String(header.bankCode ?? "")).replace(/\D/g, "");
  if (srcBankDigits.length === 0 || srcBankDigits.length > 4) {
    errors.push({ field: "bankCode", message: "仕向銀行コードは4桁以内の数字です。" });
  }

  const srcBranchDigits = normalizeIdentifierWidth(String(header.branchCode ?? "")).replace(/\D/g, "");
  if (srcBranchDigits.length === 0 || srcBranchDigits.length > 3) {
    errors.push({ field: "branchCode", message: "仕向支店コードは3桁以内の数字です。" });
  }

  const srcAcctType = normalizeIdentifierWidth(String(header.accountType ?? "1")).trim();
  if (!/^[1249]$/.test(srcAcctType)) {
    errors.push({ field: "accountType", message: "仕向預金種目は 1(普通)/2(当座)/4(貯蓄)/9(その他) です。" });
  }

  const srcAcctDigits = normalizeIdentifierWidth(String(header.accountNumber ?? "")).replace(/\D/g, "");
  if (srcAcctDigits.length === 0 || srcAcctDigits.length > 7) {
    errors.push({ field: "accountNumber", message: "仕向口座番号は7桁以内の数字です。" });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    requesterNamePreview: reqNameConv,
  };
}

/**
 * Validate a single transfer row for interactive inline workbench feedback.
 */
export function validateTransferRow(row = {}, index = 0) {
  const errors = [];
  const warnings = [];
  const fieldErrors = {};

  const bankDigits = normalizeIdentifierWidth(String(row.bankCode ?? "")).replace(/\D/g, "");
  if (!bankDigits || bankDigits.length > 4) {
    const msg = "銀行コードは4桁の数字です";
    errors.push({ field: "bankCode", message: msg });
    fieldErrors.bankCode = msg;
  }

  const branchDigits = normalizeIdentifierWidth(String(row.branchCode ?? "")).replace(/\D/g, "");
  if (!branchDigits || branchDigits.length > 3) {
    const msg = "支店コードは3桁の数字です";
    errors.push({ field: "branchCode", message: msg });
    fieldErrors.branchCode = msg;
  }

  const acctType = normalizeAccountTypeValue(row.accountType);
  if (!/^[1249]$/.test(acctType)) {
    const msg = "種目は 1(普通)/2(当座)/4(貯蓄)/9(その他)";
    errors.push({ field: "accountType", message: msg });
    fieldErrors.accountType = msg;
  }

  const acctDigits = normalizeIdentifierWidth(String(row.accountNumber ?? "")).replace(/\D/g, "");
  if (!acctDigits || acctDigits.length > 7) {
    const msg = "口座番号は7桁以内の数字です";
    errors.push({ field: "accountNumber", message: msg });
    fieldErrors.accountNumber = msg;
  }

  const recConv = toZenginHalfWidth(row.recipientName ?? "", { maxLength: 30 });
  if (!String(row.recipientName ?? "").trim()) {
    const msg = "受取人名義が空です";
    errors.push({ field: "recipientName", message: msg });
    fieldErrors.recipientName = msg;
  } else if (recConv.hasErrors) {
    const msg = `全銀不可文字(漢字等): ${recConv.invalidChars.join("")}`;
    errors.push({ field: "recipientName", invalidChars: recConv.invalidChars, message: msg });
    fieldErrors.recipientName = msg;
  } else if (!recConv.zenginText) {
    const msg = "有効なカナ名義がありません";
    errors.push({ field: "recipientName", message: msg });
    fieldErrors.recipientName = msg;
  }
  if (recConv.truncated) {
    warnings.push({
      field: "recipientName",
      message: recConv.dakutenSafeAdjusted
        ? "30バイト超過のため濁点保護切捨(29バイト)"
        : "30バイト超過のため切捨",
    });
  }

  const parsedAmt = parseAmountStrict(row.amount);
  if (!parsedAmt.valid) {
    const msg = parsedAmt.reason;
    errors.push({ field: "amount", message: msg });
    fieldErrors.amount = msg;
  } else if (parsedAmt.value === 0) {
    warnings.push({ field: "amount", message: "振込金額が0円です" });
  }

  const ediConv = toZenginHalfWidth(row.ediInfo ?? "", { maxLength: 20 });
  if (ediConv.hasErrors) {
    const msg = `EDI情報に不可文字: ${ediConv.invalidChars.join("")}`;
    errors.push({ field: "ediInfo", invalidChars: ediConv.invalidChars, message: msg });
    fieldErrors.ediInfo = msg;
  }

  const bankNameConv = resolveBankNameForZengin(row.bankName, bankDigits);
  if (bankNameConv.invalidChars.length > 0 && !bankNameConv.autoResolved) {
    warnings.push({ field: "bankName", message: `銀行名の漢字は省略/半角化: ${bankNameConv.invalidChars.join("")}` });
  }

  const branchNameConv = resolveBranchNameForZengin(row.branchName);
  if (branchNameConv.invalidChars.length > 0 && !branchNameConv.autoResolved) {
    warnings.push({ field: "branchName", message: `支店名の漢字は省略/半角化: ${branchNameConv.invalidChars.join("")}` });
  }

  let invoiceCheck = null;
  const rawInv = String(row.invoiceId ?? "").trim();
  if (rawInv) {
    const compact = normalizeIdentifierWidth(rawInv).replace(/[-\s]/g, "").toUpperCase();
    invoiceCheck = compact.startsWith("T")
      ? verifyQualifiedInvoiceId(compact)
      : verifyCorporateNumberMod9(compact);
    if (!invoiceCheck.valid) {
      const msg = `T番号/法人番号不正: ${invoiceCheck.reason}`;
      errors.push({ field: "invoiceId", message: msg });
      fieldErrors.invoiceId = msg;
    }
  }

  return {
    index,
    valid: errors.length === 0,
    hasErrors: errors.length > 0,
    errors,
    warnings,
    fieldErrors,
    recipientPreview: recConv,
    ediPreview: ediConv,
    parsedAmount: parsedAmt.valid ? parsedAmt.value : null,
    invoiceCheck,
  };
}

export function validateTransferRows(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const results = list.map((r, idx) => validateTransferRow(r, idx));
  const errorRowCount = results.filter((r) => r.hasErrors).length;
  const totalErrors = results.reduce((sum, r) => sum + r.errors.length, 0);
  const totalWarnings = results.reduce((sum, r) => sum + r.warnings.length, 0);
  return {
    valid: errorRowCount === 0,
    errorRowCount,
    totalErrors,
    totalWarnings,
    rows: results,
  };
}

/**
 * Generate an exact 120-byte Shift-JIS (CP932) Zengin file from structured transfer rows.
 * Supports Transfer Types (21/11/12), Bank Presets, Pos 112 transferDesignation / feeFlag,
 * Pos 113 auto EDI indicator ("Y" when ediInfo non-empty), and emits exact Uint8Array Shift-JIS bytes.
 */
export function generateZengin120FromRows(rows, header = {}) {
  const transferList = Array.isArray(rows) ? rows : [];
  const presetId =
    header.preset && Object.prototype.hasOwnProperty.call(BANK_PRESETS, header.preset)
      ? header.preset
      : "standard";
  const preset = BANK_PRESETS[presetId];

  const transferType = String(header.transferType ?? "21");
  if (!Object.prototype.hasOwnProperty.call(TRANSFER_TYPES, transferType)) {
    throw new Error(`未対応の種別コードです (21/11/12 のみ許可): ${transferType}`);
  }

  const lineEnding = header.lineEnding ?? preset.lineEnding;
  const includeEof = header.includeEof ?? preset.includeEof;
  const clearingHouseCodeRaw = header.clearingHouseCode ?? preset.clearingHouseCode;
  const clearingHouseCode =
    clearingHouseCodeRaw === "0000" ? "0000" : String(clearingHouseCodeRaw ?? "    ").slice(0, 4).padEnd(4, " ");

  const strict = Boolean(header.strict);
  const errors = [];
  const warnings = [];
  const rowDiagnostics = [];

  const reqCode = padZenginNumeric(header.requesterCode ?? "0000000001", 10);
  const reqNameConv = toZenginHalfWidth(header.requesterName ?? "ｶ)ﾃｽﾄｼﾖｳｼﾞ", { maxLength: 40 });
  if (reqNameConv.hasErrors) {
    errors.push({
      line: 1,
      field: "requesterName",
      code: "UNSUPPORTED_CHARS",
      invalidChars: reqNameConv.invalidChars,
      message: `委託者名に全銀不可文字が含まれています: ${reqNameConv.invalidChars.join("")}`,
    });
  }
  const reqName = reqNameConv.zenginText.padEnd(40, " ");
  const transferDate = padZenginNumeric(header.transferDateMMDD ?? "1125", 4);
  const srcBankCode = padZenginNumeric(header.bankCode ?? (preset.bankCode || "0001"), 4);
  const srcBankResolved = resolveBankNameForZengin(header.bankName ?? "ﾐｽﾞﾎ", srcBankCode);
  const srcBankName = srcBankResolved.text.padEnd(15, " ");
  const srcBranchCode = padZenginNumeric(header.branchCode ?? "001", 3);
  const srcBranchResolved = resolveBranchNameForZengin(header.branchName ?? "ﾎﾝﾃﾝ");
  const srcBranchName = srcBranchResolved.text.padEnd(15, " ");
  const srcAcctType = padZenginNumeric(normalizeAccountTypeValue(header.accountType ?? "1"), 1);
  const srcAcctNum = padZenginNumeric(header.accountNumber ?? "1234567", 7);

  const headerLine =
    "1" +
    transferType +
    "0" +
    reqCode +
    reqName +
    transferDate +
    srcBankCode +
    srcBankName +
    srcBranchCode +
    srcBranchName +
    srcAcctType +
    srcAcctNum +
    " ".repeat(17);

  const lines = [headerLine];
  let totalAmount = 0;

  for (let idx = 0; idx < transferList.length; idx += 1) {
    const row = transferList[idx];
    const lineNo = idx + 2;
    const amtNum =
      typeof row.amount === "string"
        ? Number(normalizeIdentifierWidth(row.amount).replace(/[¥￥円,\s]/g, ""))
        : Number(row.amount ?? 0);

    if (!Number.isInteger(amtNum) || amtNum < 0) {
      throw new Error(`振込金額は0以上の整数である必要があります: ${row.amount}`);
    }
    totalAmount += amtNum;

    const dstBankCode = padZenginNumeric(row.bankCode ?? "0005", 4);
    const dstBankResolved = resolveBankNameForZengin(row.bankName ?? "", dstBankCode);
    const dstBranchCode = padZenginNumeric(row.branchCode ?? "001", 3);
    const dstBranchResolved = resolveBranchNameForZengin(row.branchName ?? "");
    const dstAcctType = padZenginNumeric(normalizeAccountTypeValue(row.accountType ?? "1"), 1);
    const dstAcctNum = padZenginNumeric(row.accountNumber ?? "0000001", 7);

    const recConv = toZenginHalfWidth(row.recipientName ?? "ﾔﾏﾀﾞ ﾀﾛｳ", { maxLength: 30 });
    const ediRaw = row.ediInfo ?? row.edi ?? "";
    const ediConv = toZenginHalfWidth(ediRaw, { maxLength: 20 });

    const rowErrors = [];
    if (recConv.hasErrors) {
      rowErrors.push({
        line: lineNo,
        rowIndex: idx,
        field: "recipientName",
        code: "UNSUPPORTED_CHARS",
        invalidChars: recConv.invalidChars,
        message: `明細${idx + 1}行目の受取人名義に全銀不可文字が含まれています: ${recConv.invalidChars.join("")}`,
      });
    }
    if (ediConv.hasErrors) {
      rowErrors.push({
        line: lineNo,
        rowIndex: idx,
        field: "ediInfo",
        code: "UNSUPPORTED_CHARS",
        invalidChars: ediConv.invalidChars,
        message: `明細${idx + 1}行目のEDI情報に全銀不可文字が含まれています: ${ediConv.invalidChars.join("")}`,
      });
    }
    if (recConv.truncated) {
      warnings.push({
        line: lineNo,
        rowIndex: idx,
        field: "recipientName",
        code: recConv.dakutenSafeAdjusted ? "TRUNCATED_DAKUTEN_SAFE" : "TRUNCATED",
        message: recConv.dakutenSafeAdjusted
          ? `明細${idx + 1}行目の受取人名義を濁点保護のうえ29バイトで切り捨てました。`
          : `明細${idx + 1}行目の受取人名義を30バイトで切り捨てました。`,
      });
    }
    errors.push(...rowErrors);
    rowDiagnostics.push({
      rowIndex: idx,
      line: lineNo,
      recipientPreview: recConv,
      ediPreview: ediConv,
      errors: rowErrors,
    });

    const newCode = padZenginNumeric(row.newCode ?? "0", 1);
    const ediField = ediConv.zenginText.padEnd(20, " ");
    const hasEdi = ediConv.zenginText.trim().length > 0;

    // Pos 112: 振込指定区分 ("7" 電信 default / "8" 文書 / " "), backward compatible with row.feeFlag
    const rawDesignation = row.transferDesignation ?? row.feeFlag ?? "7";
    const designationChar =
      String(rawDesignation) === " " ? " " : padZenginNumeric(rawDesignation, 1);

    // Pos 113: 識別表示 (auto "Y" when Pos 92-111 EDI info is non-empty, else " ")
    const ediIndicator =
      row.ediIndicator !== undefined && row.ediIndicator !== null && row.ediIndicator !== ""
        ? String(row.ediIndicator)[0]
        : hasEdi
          ? "Y"
          : " ";

    const dataLine =
      "2" +
      dstBankCode +
      dstBankResolved.text.padEnd(15, " ") +
      dstBranchCode +
      dstBranchResolved.text.padEnd(15, " ") +
      clearingHouseCode +
      dstAcctType +
      dstAcctNum +
      recConv.zenginText.padEnd(30, " ") +
      padZenginNumeric(amtNum, 10) +
      newCode +
      ediField +
      designationChar +
      ediIndicator +
      " ".repeat(7);

    lines.push(dataLine);
  }

  if (strict && errors.length > 0) {
    throw new Error(errors.map((e) => e.message).join(" / "));
  }

  const trailerLine =
    "8" +
    padZenginNumeric(transferList.length, 6) +
    padZenginNumeric(totalAmount, 12) +
    " ".repeat(101);

  const endLine = "9" + " ".repeat(119);
  lines.push(trailerLine, endLine);

  const recordByteLengths = lines.map((line) => encodeZenginShiftJis(line).length);
  const allRecords120Bytes = recordByteLengths.every((len) => len === 120);
  if (!allRecords120Bytes) {
    throw new Error(`全銀120バイト不変条件違反: ${recordByteLengths.join(",")}`);
  }

  const content = lineEnding === "NONE" ? lines.join("") : lines.join("\r\n") + "\r\n";
  const bytes = encodeZenginShiftJis(content, { includeEof });

  return {
    content,
    bytes,
    byteLength: bytes.length,
    recordByteLengths,
    allRecords120Bytes,
    encoding: "shift_jis",
    preset: presetId,
    transferType,
    lineEnding,
    includeEof,
    clearingHouseCode,
    lineCount: lines.length,
    dataCount: transferList.length,
    totalAmountYen: totalAmount,
    hasErrors: errors.length > 0,
    errors,
    warnings,
    rowDiagnostics,
  };
}

/**
 * Split Zengin text into logical record lines, supporting CRLF, LF, and continuous 120-byte (NONE) format.
 */
function splitZenginRecords(text) {
  const clean = String(text ?? "").replace(/^\uFEFF/, "").replace(/\x1a+$/, "");
  if (!clean) return [];
  if (!clean.includes("\n") && !clean.includes("\r") && clean.length >= 120 && clean.length % 120 === 0) {
    const chunks = [];
    for (let i = 0; i < clean.length; i += 120) {
      chunks.push(clean.slice(i, i + 120));
    }
    return chunks;
  }
  return clean
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((l) => l.length > 0);
}

/**
 * Parse and strictly audit a 120-byte Zengin payload (accepts string or Uint8Array).
 */
export function parseZengin120(input) {
  let content;
  let sourceMeta = null;
  if (input instanceof Uint8Array || input instanceof ArrayBuffer) {
    sourceMeta = decodeZenginBytes(input);
    content = sourceMeta.text;
  } else {
    content = String(input ?? "");
  }

  const rawLines = splitZenginRecords(content);
  const errors = [];
  const rows = [];
  let header = null;
  let trailer = null;
  let hasEnd = false;
  let computedTotal = 0;

  for (let idx = 0; idx < rawLines.length; idx += 1) {
    const line = rawLines[idx];
    const lineNo = idx + 1;

    let sjisByteLen = null;
    try {
      sjisByteLen = encodeZenginShiftJis(line).length;
    } catch {
      sjisByteLen = null;
    }

    if (line.length !== 120 || (sjisByteLen !== null && sjisByteLen !== 120)) {
      errors.push({
        line: lineNo,
        code: "LEN_NOT_120",
        message: `桁数が120バイトではありません (${sjisByteLen ?? line.length}バイト)`,
      });
      continue;
    }
    if (!ZENGIN_LEGAL_RE.test(line)) {
      errors.push({ line: lineNo, code: "ILLEGAL_CHAR", message: "全銀協規定外文字が含まれています。" });
    }
    const recType = line[0];
    if (recType === "1") {
      header = {
        typeCode: line.slice(1, 3),
        codeType: line.slice(3, 4),
        requesterCode: line.slice(4, 14),
        requesterName: line.slice(14, 54).trimEnd(),
        transferDateMMDD: line.slice(54, 58),
        bankCode: line.slice(58, 62),
        bankName: line.slice(62, 77).trimEnd(),
        branchCode: line.slice(77, 80),
        branchName: line.slice(80, 95).trimEnd(),
        accountType: line.slice(95, 96),
        accountNumber: line.slice(96, 103),
      };
    } else if (recType === "2") {
      const amountStr = line.slice(80, 90);
      const amount = Number(amountStr);
      if (!/^\d{10}$/.test(amountStr)) {
        errors.push({
          line: lineNo,
          code: "BAD_AMOUNT",
          message: `金額フィールドが数字10桁ではありません: ${amountStr}`,
        });
      } else {
        computedTotal += amount;
      }
      rows.push({
        line: lineNo,
        bankCode: line.slice(1, 5),
        bankName: line.slice(5, 20).trimEnd(),
        branchCode: line.slice(20, 23),
        branchName: line.slice(23, 38).trimEnd(),
        clearingHouseCode: line.slice(38, 42),
        accountType: line.slice(42, 43),
        accountNumber: line.slice(43, 50),
        recipientName: line.slice(50, 80).trimEnd(),
        amount,
        newCode: line.slice(90, 91),
        ediInfo: line.slice(91, 111).trimEnd(),
        transferDesignation: line.slice(111, 112),
        ediIndicator: line.slice(112, 113),
      });
    } else if (recType === "8") {
      const declaredCount = Number(line.slice(1, 7));
      const declaredTotal = Number(line.slice(7, 19));
      trailer = { declaredCount, declaredTotal };
    } else if (recType === "9") {
      hasEnd = true;
    } else {
      errors.push({ line: lineNo, code: "BAD_RECORD_TYPE", message: `未知のデータ区分: ${recType}` });
    }
  }

  if (!header) {
    errors.push({ line: 1, code: "MISSING_HEADER", message: "ヘッダ・レコード(区分1)がありません。" });
  }
  if (!trailer) {
    errors.push({ line: rawLines.length, code: "MISSING_TRAILER", message: "トレーラ・レコード(区分8)がありません。" });
  } else {
    if (trailer.declaredCount !== rows.length) {
      errors.push({
        line: rawLines.length,
        code: "COUNT_MISMATCH",
        message: `トレーラ合計件数(${trailer.declaredCount})と明細件数(${rows.length})が一致しません。`,
      });
    }
    if (trailer.declaredTotal !== computedTotal) {
      errors.push({
        line: rawLines.length,
        code: "AMOUNT_MISMATCH",
        message: `トレーラ合計金額(${trailer.declaredTotal})と明細合計(${computedTotal})が一致しません。`,
      });
    }
  }
  if (!hasEnd) {
    errors.push({ line: rawLines.length, code: "MISSING_END", message: "エンド・レコード(区分9)がありません。" });
  }

  return {
    valid: errors.length === 0,
    sourceMeta,
    header,
    rows,
    trailer,
    computedTotal,
    errors,
  };
}

// ---------------------------------------------------------------------------
// RFC-4180 CSV/TSV Parser + Auto Column Mapper (freee / MoneyForward / 弥生 / Excel)
// ---------------------------------------------------------------------------

const HEADER_ALIASES = {
  bankCode: [
    "銀行コード", "金融機関コード", "振込先金融機関コード", "振込先銀行コード",
    "被仕向金融機関番号", "被仕向銀行コード", "銀行番号", "金融機関番号",
    "bank_code", "bankcode", "bank_no", "bankno", "bank_cd",
  ],
  bankName: [
    "銀行名", "金融機関名", "銀行名カナ", "金融機関名カナ", "振込先銀行名",
    "振込先金融機関名", "被仕向金融機関名", "bank_name", "bankname",
  ],
  branchCode: [
    "支店コード", "支店番号", "振込先支店コード", "被仕向支店番号",
    "店舗コード", "店番", "支店cd", "branch_code", "branchcode", "branch_no", "branchno",
  ],
  branchName: [
    "支店名", "支店名カナ", "振込先支店名", "被仕向支店名", "店舗名",
    "branch_name", "branchname",
  ],
  accountType: [
    "預金種目", "口座種別", "預金種別", "口座種目", "種別", "種目",
    "account_type", "accounttype", "acct_type", "deposit_type",
  ],
  accountNumber: [
    "口座番号", "振込先口座番号", "口座no",
    "account_number", "accountnumber", "acct_num", "acct_no", "account_no",
  ],
  recipientName: [
    "受取人名", "受取人名義", "受取人名カナ", "受取人カナ", "口座名義", "口座名義人",
    "口座名義カナ", "口座名義(カナ)", "振込先口座名義", "振込先名義", "振込先名",
    "名義人", "名義", "カナ名義", "取引先名", "支払先名", "社員名", "氏名",
    "recipient_name", "recipientname", "payee_name", "payee", "beneficiary", "account_holder", "name",
  ],
  amount: [
    "振込金額", "金額", "支払金額", "支給額", "差引支給額", "振込額", "請求金額", "税込金額",
    "amount", "transfer_amount", "payment_amount", "yen",
  ],
  ediInfo: [
    "edi情報", "edi", "顧客コード", "顧客コード1", "社員番号", "識別情報", "備考", "摘要",
    "edi_info", "ediinfo", "customer_code", "reference", "memo",
  ],
  transferDesignation: [
    "振込指定区分", "振込区分", "電信文書区分", "手数料負担", "手数料区分",
    "transfer_designation", "fee_flag",
  ],
  invoiceId: [
    "t番号", "登録番号", "適格請求書発行事業者登録番号", "インボイス番号", "インボイス登録番号",
    "法人番号", "invoice_id", "t_number", "corporate_number",
  ],
};

function normalizeHeaderKey(raw) {
  return normalizeIdentifierWidth(String(raw ?? ""))
    .replace(/^\uFEFF/, "")
    .toLowerCase()
    .replace(/[\s　*＊:：（）()【】\[\]]+/g, "");
}

function normalizeAccountTypeValue(raw) {
  const s = normalizeIdentifierWidth(String(raw ?? "")).trim();
  if (!s) return "1";
  if (/^[1249]$/.test(s)) return s;
  if (/普通|ふつう|ﾌﾂｳ|savings|ordinary/i.test(s)) return "1";
  if (/当座|とうざ|ﾄｳｻﾞ|checking|current/i.test(s)) return "2";
  if (/貯蓄|ちよちく|ﾁﾖﾁｸ/i.test(s)) return "4";
  if (/その他|ｿﾉﾀ|other/i.test(s)) return "9";
  return s;
}

function parseAmountStrict(raw) {
  if (typeof raw === "number") {
    if (!Number.isFinite(raw) || !Number.isInteger(raw) || raw < 0) {
      return { valid: false, value: null, reason: `金額は0以上の整数である必要があります (${raw})` };
    }
    if (raw > 9999999999) {
      return { valid: false, value: null, reason: "金額が10桁(99億円)を超過しています" };
    }
    return { valid: true, value: raw, cleaned: false };
  }
  const orig = String(raw ?? "").trim();
  if (!orig) {
    return { valid: false, value: null, reason: "振込金額が空です" };
  }
  const norm = normalizeIdentifierWidth(orig).replace(/[¥￥円,\s　]/g, "");
  if (!/^\d+$/.test(norm)) {
    return { valid: false, value: null, reason: `金額を整数として解釈できません: ${orig}` };
  }
  const value = Number(norm);
  if (!Number.isSafeInteger(value) || value > 9999999999) {
    return { valid: false, value: null, reason: `金額が10桁を超過しています: ${orig}` };
  }
  return { valid: true, value, cleaned: norm !== orig };
}

function detectCsvDelimiter(rawText) {
  const firstLine = String(rawText ?? "")
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .find((l) => l.trim().length > 0);
  if (!firstLine) return ",";
  let inQuotes = false;
  let commas = 0;
  let tabs = 0;
  for (let i = 0; i < firstLine.length; i += 1) {
    const ch = firstLine[i];
    if (ch === '"') {
      if (inQuotes && firstLine[i + 1] === '"') {
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (!inQuotes) {
      if (ch === ",") commas += 1;
      else if (ch === "\t") tabs += 1;
    }
  }
  return tabs > 0 && tabs >= commas ? "\t" : ",";
}

/**
 * RFC-4180 compliant CSV/TSV tokenizer supporting quoted commas, escaped quotes (""), and multiline quoted fields.
 */
function parseDelimitedMatrix(rawText, delimiter) {
  const text = String(rawText ?? "").replace(/^\uFEFF/, "");
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"' && field.length === 0) {
      inQuotes = true;
    } else if (ch === delimiter) {
      row.push(field);
      field = "";
    } else if (ch === "\r") {
      if (text[i + 1] === "\n") i += 1;
      row.push(field);
      if (row.some((cell) => cell.trim() !== "")) rows.push(row);
      row = [];
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      if (row.some((cell) => cell.trim() !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }

  row.push(field);
  if (row.some((cell) => cell.trim() !== "")) rows.push(row);
  return rows;
}

function matchHeaderRow(cells) {
  const normalizedCells = cells.map(normalizeHeaderKey);
  const columnMap = {};
  let matchCount = 0;

  for (const [fieldName, aliases] of Object.entries(HEADER_ALIASES)) {
    const normAliases = aliases.map(normalizeHeaderKey);
    for (let colIdx = 0; colIdx < normalizedCells.length; colIdx += 1) {
      const cell = normalizedCells[colIdx];
      if (!cell) continue;
      if (normAliases.includes(cell)) {
        if (columnMap[fieldName] === undefined) {
          columnMap[fieldName] = colIdx;
          matchCount += 1;
        }
        break;
      }
    }
  }

  // Require at least 2 recognized accounting header columns to classify row 0 as a header
  if (matchCount < 2) return null;

  let detectedPreset = "generic";
  const joined = normalizedCells.join("|");
  if (joined.includes("取引先名") || joined.includes("振込先金融機関コード")) {
    detectedPreset = "freee";
  } else if (joined.includes("支払先名") || joined.includes("口座名義カナ")) {
    detectedPreset = "moneyforward";
  } else if (joined.includes("被仕向金融機関番号") || joined.includes("支給額")) {
    detectedPreset = "yayoi";
  }

  return { columnMap, detectedPreset };
}

/**
 * Parse accounting CSV/TSV (freee / MoneyForward / 弥生 / Excel / generic / headerless 8-col)
 * with RFC-4180 quote handling, Yen/comma cleaning, and Excel leading-zero recovery.
 */
export function parseTransferCsv(rawText) {
  const delimiter = detectCsvDelimiter(rawText);
  const matrix = parseDelimitedMatrix(rawText, delimiter);
  if (matrix.length === 0) {
    return {
      rows: [],
      delimiter,
      hasHeader: false,
      detectedPreset: "empty",
      columnMap: {},
      headers: [],
      autoRepairs: [],
      warnings: [],
    };
  }

  const headerDetection = matchHeaderRow(matrix[0]);
  const hasHeader = headerDetection !== null;
  const headers = hasHeader ? matrix[0].map((c) => c.trim()) : [];
  const columnMap = hasHeader
    ? headerDetection.columnMap
    : {
        bankCode: 0,
        bankName: 1,
        branchCode: 2,
        branchName: 3,
        accountType: 4,
        accountNumber: 5,
        recipientName: 6,
        amount: 7,
        ediInfo: 8,
        invoiceId: 9,
      };

  const dataRows = hasHeader ? matrix.slice(1) : matrix;
  const autoRepairs = [];
  const warnings = [];
  const rows = [];

  const getCell = (cells, field) => {
    const idx = columnMap[field];
    if (idx === undefined || idx >= cells.length) return "";
    return String(cells[idx] ?? "").trim();
  };

  for (let i = 0; i < dataRows.length; i += 1) {
    const cells = dataRows[i];
    const rowNo = hasHeader ? i + 2 : i + 1;
    const rowNotes = [];

    const rawBankCode = normalizeIdentifierWidth(getCell(cells, "bankCode")).replace(/\D/g, "");
    let bankCode = rawBankCode;
    if (rawBankCode.length > 0 && rawBankCode.length < 4) {
      bankCode = rawBankCode.padStart(4, "0");
      rowNotes.push(`銀行コード0補完(${rawBankCode}→${bankCode})`);
      autoRepairs.push({ row: rowNo, field: "bankCode", from: rawBankCode, to: bankCode });
    }

    const rawBranchCode = normalizeIdentifierWidth(getCell(cells, "branchCode")).replace(/\D/g, "");
    let branchCode = rawBranchCode;
    if (rawBranchCode.length > 0 && rawBranchCode.length < 3) {
      branchCode = rawBranchCode.padStart(3, "0");
      rowNotes.push(`支店コード0補完(${rawBranchCode}→${branchCode})`);
      autoRepairs.push({ row: rowNo, field: "branchCode", from: rawBranchCode, to: branchCode });
    }

    const rawAcctType = getCell(cells, "accountType");
    const accountType = normalizeAccountTypeValue(rawAcctType);
    if (rawAcctType && rawAcctType !== accountType && /^[1249]$/.test(accountType)) {
      rowNotes.push(`種目正規化(${rawAcctType}→${accountType})`);
      autoRepairs.push({ row: rowNo, field: "accountType", from: rawAcctType, to: accountType });
    }

    const rawAcctNum = normalizeIdentifierWidth(getCell(cells, "accountNumber")).replace(/\D/g, "");
    let accountNumber = rawAcctNum;
    if (rawAcctNum.length > 0 && rawAcctNum.length < 7) {
      accountNumber = rawAcctNum.padStart(7, "0");
      rowNotes.push(`口座番号0補完(${rawAcctNum}→${accountNumber})`);
      autoRepairs.push({ row: rowNo, field: "accountNumber", from: rawAcctNum, to: accountNumber });
    }

    let bankName = getCell(cells, "bankName");
    if (!bankName && MAJOR_BANKS[bankCode]) {
      bankName = MAJOR_BANKS[bankCode];
      rowNotes.push(`銀行名補完(${bankName})`);
    }

    const branchName = getCell(cells, "branchName");
    const recipientName = getCell(cells, "recipientName");
    const rawAmount = getCell(cells, "amount");
    const amtCheck = parseAmountStrict(rawAmount);
    if (amtCheck.valid && amtCheck.cleaned) {
      rowNotes.push(`金額整形(${rawAmount}→${amtCheck.value})`);
      autoRepairs.push({ row: rowNo, field: "amount", from: rawAmount, to: String(amtCheck.value) });
    }

    const ediInfo = getCell(cells, "ediInfo");
    const rawDesignation = getCell(cells, "transferDesignation");
    const transferDesignation = rawDesignation ? normalizeIdentifierWidth(rawDesignation).trim() : "7";
    const invoiceId = getCell(cells, "invoiceId");

    rows.push({
      bankCode,
      bankName,
      branchCode,
      branchName,
      accountType,
      accountNumber,
      recipientName,
      amount: amtCheck.valid ? amtCheck.value : rawAmount,
      ediInfo,
      transferDesignation,
      invoiceId,
      autoRepairNotes: rowNotes,
    });
  }

  return {
    rows,
    delimiter,
    hasHeader,
    detectedPreset: hasHeader ? headerDetection.detectedPreset : "headerless",
    columnMap,
    headers,
    autoRepairs,
    warnings,
  };
}

// ---------------------------------------------------------------------------
// 1-Click Bank-Rejected Zengin File Diagnostics & Auto-Repair
// ---------------------------------------------------------------------------

/**
 * Diagnose a broken / bank-rejected Zengin `.txt` file (UTF-8 katakana, BOM, full-width spaces,
 * wrong record length, bad trailer sum/count, missing End record, missing EDI indicator "Y")
 * and auto-repair into strict 120-byte Shift-JIS (CP932) records.
 */
export function diagnoseAndRepairZenginFile(input, options = {}) {
  const decoded = decodeZenginBytes(input);
  const presetId =
    options.preset && Object.prototype.hasOwnProperty.call(BANK_PRESETS, options.preset)
      ? options.preset
      : "standard";
  const preset = BANK_PRESETS[presetId];
  const targetLineEnding = options.lineEnding ?? preset.lineEnding;
  const targetIncludeEof = options.includeEof ?? preset.includeEof;
  const targetClearingHouse = options.clearingHouseCode ?? preset.clearingHouseCode;

  const diagnostics = [];
  const blockingErrors = [];

  if (decoded.encoding === "utf-8" || decoded.encoding === "utf-8-bom") {
    diagnostics.push({
      line: 0,
      code: "UTF8_ENCODING",
      severity: "repaired",
      fixed: true,
      message: `文字コードが ${decoded.encoding.toUpperCase()} でした（銀行は Shift-JIS/CP932 必須）。Shift-JIS バイナリへ自動変換します。`,
    });
  }
  if (decoded.hasBom) {
    diagnostics.push({
      line: 0,
      code: "UTF8_BOM",
      severity: "repaired",
      fixed: true,
      message: "先頭に UTF-8 BOM (EF BB BF) を検出しました。自動除去します。",
    });
  }
  if (decoded.lineEnding === "LF" && targetLineEnding === "CRLF") {
    diagnostics.push({
      line: 0,
      code: "LF_LINE_ENDING",
      severity: "repaired",
      fixed: true,
      message: "改行コードが LF のみでした。全銀標準 CRLF (0x0D 0x0A) へ統一します。",
    });
  }

  const rawLines = splitZenginRecords(decoded.text);
  let headerObj = null;
  const repairedRows = [];
  let declaredTrailer = null;
  let sawEnd = false;

  for (let idx = 0; idx < rawLines.length; idx += 1) {
    const rawLine = rawLines[idx];
    const lineNo = idx + 1;
    const recType = normalizeIdentifierWidth(rawLine[0] ?? "");

    let rawSjisLen = null;
    try {
      rawSjisLen = encodeZenginShiftJis(rawLine).length;
    } catch {
      rawSjisLen = null;
    }

    if (rawSjisLen === null) {
      diagnostics.push({
        line: lineNo,
        code: "NON_SHIFTJIS_OR_FULLWIDTH",
        severity: "repaired",
        fixed: true,
        message: `${lineNo}行目に全角文字・ひらがな・全角スペース等を検出しました。全銀半角カナ規格へ正規化します。`,
      });
    } else if (rawSjisLen !== 120) {
      diagnostics.push({
        line: lineNo,
        code: "LEN_NOT_120",
        severity: "repaired",
        fixed: true,
        message: `${lineNo}行目のバイト長が ${rawSjisLen} バイトでした（規定 120 バイト）。フィールド単位で120バイトへ補正します。`,
      });
    }

    if (recType === "1") {
      const parsedHeader = repairHeaderLine(rawLine, lineNo, diagnostics, blockingErrors);
      headerObj = parsedHeader;
    } else if (recType === "2") {
      const parsedRow = repairDataLine(rawLine, lineNo, diagnostics, blockingErrors, targetClearingHouse);
      if (parsedRow) repairedRows.push(parsedRow);
    } else if (recType === "8") {
      const normTrailer = normalizeIdentifierWidth(rawLine).padEnd(120, " ");
      const declaredCount = Number(normTrailer.slice(1, 7).replace(/\D/g, "") || "0");
      const declaredTotal = Number(normTrailer.slice(7, 19).replace(/\D/g, "") || "0");
      declaredTrailer = { line: lineNo, declaredCount, declaredTotal };
    } else if (recType === "9") {
      sawEnd = true;
    } else {
      blockingErrors.push({
        line: lineNo,
        code: "BAD_RECORD_TYPE",
        severity: "error",
        fixed: false,
        message: `${lineNo}行目のデータ区分 "${rawLine[0] ?? ""}" は全銀区分(1/2/8/9)ではありません。`,
      });
    }
  }

  if (!headerObj) {
    blockingErrors.push({
      line: 1,
      code: "MISSING_HEADER",
      severity: "error",
      fixed: false,
      message: "ヘッダ・レコード(区分1)が存在しません。委託者情報を設定して再生成してください。",
    });
    headerObj = {
      transferType: "21",
      requesterCode: "0000000001",
      requesterName: "ｶ)ﾐｾﾂﾃｲ",
      transferDateMMDD: "0101",
      bankCode: "0001",
      bankName: "ﾐｽﾞﾎ",
      branchCode: "001",
      branchName: "ﾎﾝﾃﾝ",
      accountType: "1",
      accountNumber: "0000001",
    };
  }

  const actualCount = repairedRows.length;
  const actualTotal = repairedRows.reduce((acc, r) => acc + r.amount, 0);

  if (!declaredTrailer) {
    diagnostics.push({
      line: rawLines.length + 1,
      code: "MISSING_TRAILER",
      severity: "repaired",
      fixed: true,
      message: `トレーラ・レコード(区分8)が欠落していました。明細 ${actualCount} 件 / 合計 ${actualTotal.toLocaleString()} 円で自動生成します。`,
    });
  } else {
    if (declaredTrailer.declaredCount !== actualCount) {
      diagnostics.push({
        line: declaredTrailer.line,
        code: "COUNT_MISMATCH",
        severity: "repaired",
        fixed: true,
        message: `トレーラ合計件数(${declaredTrailer.declaredCount})と実明細件数(${actualCount})が不一致でした。${actualCount} 件へ自動修正しました。`,
      });
    }
    if (declaredTrailer.declaredTotal !== actualTotal) {
      diagnostics.push({
        line: declaredTrailer.line,
        code: "AMOUNT_MISMATCH",
        severity: "repaired",
        fixed: true,
        message: `トレーラ合計金額(${declaredTrailer.declaredTotal.toLocaleString()}円)と実明細合計(${actualTotal.toLocaleString()}円)が不一致でした。${actualTotal.toLocaleString()} 円へ自動修正しました。`,
      });
    }
  }

  if (!sawEnd) {
    diagnostics.push({
      line: rawLines.length + 2,
      code: "MISSING_END",
      severity: "repaired",
      fixed: true,
      message: "エンド・レコード(区分9)が欠落していました。自動補完します。",
    });
  }

  const gen = generateZengin120FromRows(repairedRows, {
    ...headerObj,
    preset: presetId,
    lineEnding: targetLineEnding,
    includeEof: targetIncludeEof,
    clearingHouseCode: targetClearingHouse,
  });

  const audit = parseZengin120(gen.bytes);
  const allDiagnostics = [...diagnostics, ...blockingErrors];

  return {
    source: {
      encoding: decoded.encoding,
      hasBom: decoded.hasBom,
      lineEnding: decoded.lineEnding,
      hasEofMarker: decoded.hasEofMarker,
      rawByteLength: decoded.byteLength,
      lineCount: rawLines.length,
    },
    diagnostics: allDiagnostics,
    blockingErrors,
    fixedCount: diagnostics.filter((d) => d.fixed).length,
    repaired: {
      ok: blockingErrors.length === 0 && audit.valid && gen.allRecords120Bytes,
      content: gen.content,
      bytes: gen.bytes,
      byteLength: gen.byteLength,
      lineCount: gen.lineCount,
      dataCount: gen.dataCount,
      totalAmountYen: gen.totalAmountYen,
      allRecords120Bytes: gen.allRecords120Bytes,
      header: headerObj,
      rows: repairedRows,
      audit,
    },
  };
}

function repairHeaderLine(rawLine, lineNo, diagnostics, blockingErrors) {
  const norm = normalizeIdentifierWidth(rawLine);
  const padded = norm.padEnd(120, " ");
  const rawType = padded.slice(1, 3).trim();
  const transferType = Object.prototype.hasOwnProperty.call(TRANSFER_TYPES, rawType) ? rawType : "21";
  if (rawType !== transferType) {
    diagnostics.push({
      line: lineNo,
      code: "BAD_TRANSFER_TYPE",
      severity: "repaired",
      fixed: true,
      message: `ヘッダ種別コード "${rawType}" を 21(総合振込) へ補正しました。`,
    });
  }
  const requesterCode = padded.slice(4, 14).replace(/\D/g, "").padStart(10, "0").slice(-10);
  const reqNameRaw = padded.slice(14, 54);
  const reqNameConv = toZenginHalfWidth(reqNameRaw, { maxLength: 40 });
  if (reqNameConv.hasErrors) {
    blockingErrors.push({
      line: lineNo,
      code: "UNSUPPORTED_KANJI",
      severity: "error",
      fixed: false,
      invalidChars: reqNameConv.invalidChars,
      message: `ヘッダ委託者名に自動変換できない漢字が含まれています: ${reqNameConv.invalidChars.join("")}`,
    });
  }

  const transferDateMMDD = padded.slice(54, 58).replace(/\D/g, "").padStart(4, "0").slice(-4);
  const bankCode = padded.slice(58, 62).replace(/\D/g, "").padStart(4, "0").slice(-4);
  const bankName = resolveBankNameForZengin(padded.slice(62, 77), bankCode).text;
  const branchCode = padded.slice(77, 80).replace(/\D/g, "").padStart(3, "0").slice(-3);
  const branchName = resolveBranchNameForZengin(padded.slice(80, 95)).text;
  const accountType = normalizeAccountTypeValue(padded.slice(95, 96));
  const accountNumber = padded.slice(96, 103).replace(/\D/g, "").padStart(7, "0").slice(-7);

  return {
    transferType,
    requesterCode,
    requesterName: reqNameConv.zenginText || "ｶ)ﾐｾﾂﾃｲ",
    transferDateMMDD,
    bankCode,
    bankName,
    branchCode,
    branchName,
    accountType,
    accountNumber,
  };
}

function repairDataLine(rawLine, lineNo, diagnostics, blockingErrors, targetClearingHouse) {
  const norm = normalizeIdentifierWidth(rawLine);
  let padded = norm.padEnd(120, " ");

  // Check whether fixed-offset fields are aligned (Pos 81-90 = 10-digit amount)
  let bankCode;
  let bankNameRaw;
  let branchCode;
  let branchNameRaw;
  let accountType;
  let accountNumber;
  let recipientRaw;
  let amountStr;
  let newCode;
  let ediRaw;
  let transferDesignation;
  let origEdiIndicator;

  if (/^\d{10}$/.test(padded.slice(80, 90))) {
    bankCode = padded.slice(1, 5).replace(/\D/g, "").padStart(4, "0").slice(-4);
    bankNameRaw = padded.slice(5, 20);
    branchCode = padded.slice(20, 23).replace(/\D/g, "").padStart(3, "0").slice(-3);
    branchNameRaw = padded.slice(23, 38);
    accountType = normalizeAccountTypeValue(padded.slice(42, 43));
    accountNumber = padded.slice(43, 50).replace(/\D/g, "").padStart(7, "0").slice(-7);
    recipientRaw = padded.slice(50, 80);
    amountStr = padded.slice(80, 90);
    newCode = padded.slice(90, 91).replace(/\D/g, "") || "0";
    ediRaw = padded.slice(91, 111);
    transferDesignation = padded.slice(111, 112).trim() || "7";
    origEdiIndicator = padded.slice(112, 113);
  } else {
    // Attempt structural recovery when full-width chars shifted column offsets
    const m = norm.match(/^2(\d{4})(.{1,20}?)(\d{3})(.{1,20}?)([0\s]{4})([1249])(\d{7})(.+?)(\d{10})([012])(.*)$/);
    if (!m) {
      blockingErrors.push({
        line: lineNo,
        code: "UNPARSEABLE_DATA_RECORD",
        severity: "error",
        fixed: false,
        message: `${lineNo}行目のデータレコード構造(金額10桁等)を復元できませんでした。`,
      });
      return null;
    }
    [, bankCode, bankNameRaw, branchCode, branchNameRaw, , accountType, accountNumber, recipientRaw, amountStr, newCode] = m;
    const tail = (m[11] ?? "").padEnd(29, " ");
    ediRaw = tail.slice(0, 20);
    transferDesignation = tail.slice(20, 21).trim() || "7";
    origEdiIndicator = tail.slice(21, 22);
    diagnostics.push({
      line: lineNo,
      code: "SHIFTED_OFFSETS_RECOVERED",
      severity: "repaired",
      fixed: true,
      message: `${lineNo}行目の全角混入によるカラム位置ズレを自動復元しました。`,
    });
  }

  const recConv = toZenginHalfWidth(recipientRaw, { maxLength: 30 });
  if (recConv.hasErrors) {
    blockingErrors.push({
      line: lineNo,
      code: "UNSUPPORTED_KANJI",
      severity: "error",
      fixed: false,
      invalidChars: recConv.invalidChars,
      message: `${lineNo}行目の受取人名義に自動変換できない漢字が含まれています: ${recConv.invalidChars.join("")}`,
    });
  }

  const ediConv = toZenginHalfWidth(ediRaw, { maxLength: 20 });
  if (ediConv.hasErrors) {
    blockingErrors.push({
      line: lineNo,
      code: "UNSUPPORTED_KANJI",
      severity: "error",
      fixed: false,
      invalidChars: ediConv.invalidChars,
      message: `${lineNo}行目のEDI情報に自動変換できない漢字が含まれています: ${ediConv.invalidChars.join("")}`,
    });
  }

  if (ediConv.zenginText.trim().length > 0 && origEdiIndicator !== "Y") {
    diagnostics.push({
      line: lineNo,
      code: "EDI_INDICATOR_REPAIRED",
      severity: "repaired",
      fixed: true,
      message: `${lineNo}行目にEDI情報が存在するため Pos 113 識別表示へ "Y" を自動付与しました。`,
    });
  }

  const amount = Number(amountStr);
  return {
    bankCode,
    bankName: resolveBankNameForZengin(bankNameRaw, bankCode).text,
    branchCode,
    branchName: resolveBranchNameForZengin(branchNameRaw).text,
    clearingHouseCode: targetClearingHouse,
    accountType,
    accountNumber,
    recipientName: recConv.hasErrors ? recipientRaw.trim() : recConv.zenginText,
    amount,
    newCode,
    ediInfo: ediConv.zenginText,
    transferDesignation,
  };
}
