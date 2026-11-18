/**
 * ZENGINGATE (全銀門) - 100% Browser-Local Japanese Qualified Invoice (Mod-9) & Zengin 120-Byte Banking Engine
 * Implements:
 *   1. NTA Modulo-9 check-digit verification for Qualified Invoice IDs (T+13 digits) & Corporate Numbers (13 digits).
 *   2. Zengin (全銀協) half-width kana conversion & 1-byte voiced mark budgeting.
 *   3. Fixed-length 120-byte Sogo Furikomi (総合振込) parser, trailer-sum validator, and CSV -> Zengin generator.
 * Zero external dependencies; zero network calls.
 */

const FULL_HIRAGANA_START = 0x3041;
const FULL_HIRAGANA_END = 0x3096;

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
  // Common small half-width katakana promoted to full half-width per Zengin spec
  ｧ: "ｱ", ｨ: "ｲ", ｩ: "ｳ", ｪ: "ｴ", ｫ: "ｵ", ｯ: "ﾂ", ｬ: "ﾔ", ｭ: "ﾕ", ｮ: "ﾖ",
  // Prolonged vowel / spaces / punctuation
  ー: "-", "－": "-", "―": "-", "−": "-", "‐": "-",
  "　": " ", "．": ".", "（": "(", "）": ")", "／": "/", "，": ",", "、": ",", "・": ".",
  "㈱": "(ｶ)", "㈲": "(ﾕ)", "㈹": "(ﾀﾞｲ)",
};

const ZENGIN_LEGAL_RE = /^[A-Z0-9ｱ-ﾝﾞﾟ \-\.\(\)\/,]*$/;

/**
 * Normalize full-width ASCII digits/letters/hyphens into half-width uppercase ASCII.
 */
export function normalizeIdentifierWidth(raw) {
  return String(raw ?? "").replace(/[！-～]/g, (ch) =>
    String.fromCharCode(ch.charCodeAt(0) - 0xfee0),
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
 * Convert Japanese text (Hiragana, Katakana, ASCII, full-width symbols) to Zengin-compliant half-width string.
 */
export function toZenginHalfWidth(raw, { maxLength = 30, stripUnsupported = true } = {}) {
  const halfWidthAscii = normalizeIdentifierWidth(String(raw ?? ""))
    .replace(/株式会社/g, "(ｶ)")
    .replace(/有限会社/g, "(ﾕ)")
    .replace(/合同会社/g, "(ﾄﾞ)")
    .toUpperCase();

  const out = [];
  const unsupported = [];
  for (const rawCh of halfWidthAscii) {
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
    if (ZENGIN_LEGAL_RE.test(ch)) {
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
  if (truncated) {
    result = result.slice(0, maxLength);
    // Do not leave dangling voiced mark alone if base truncated at boundary — here if sliced mid-character, trailing dakuten still attaches to preceding char, whereas leading space strip is clean
    result = result.trimEnd();
  }

  return {
    zenginText: result,
    byteLength: result.length,
    truncated,
    unsupportedChars: [...new Set(unsupported)],
    isLegal: ZENGIN_LEGAL_RE.test(result),
  };
}

function padZenginAlpha(str, width) {
  const clean = toZenginHalfWidth(str, { maxLength: width }).zenginText;
  return clean.padEnd(width, " ");
}

function padZenginNumeric(val, width) {
  const digits = String(val ?? "0").replace(/\D/g, "");
  if (digits.length > width) {
    throw new Error(`数値フィールド超過 (${digits.length} > ${width}桁): ${val}`);
  }
  return digits.padStart(width, "0");
}

/**
 * Generate an exact 120-byte Zengin Sogo Furikomi (総合振込) file from structured transfer rows.
 */
export function generateZengin120FromRows(rows, header = {}) {
  const transferList = Array.isArray(rows) ? rows : [];
  const reqCode = padZenginNumeric(header.requesterCode ?? "0000000001", 10);
  const reqName = padZenginAlpha(header.requesterName ?? "ｶ)ﾃｽﾄｼﾖｳｼﾞ", 40);
  const transferDate = padZenginNumeric(header.transferDateMMDD ?? "1125", 4);
  const srcBankCode = padZenginNumeric(header.bankCode ?? "0001", 4);
  const srcBankName = padZenginAlpha(header.bankName ?? "ﾐｽﾞﾎ", 15);
  const srcBranchCode = padZenginNumeric(header.branchCode ?? "001", 3);
  const srcBranchName = padZenginAlpha(header.branchName ?? "ﾎﾝﾃﾝ", 15);
  const srcAcctType = padZenginNumeric(header.accountType ?? "1", 1);
  const srcAcctNum = padZenginNumeric(header.accountNumber ?? "1234567", 7);

  const headerLine =
    "1" +
    "21" +
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

  for (const row of transferList) {
    const amtNum = Number(row.amount ?? 0);
    if (!Number.isInteger(amtNum) || amtNum < 0) {
      throw new Error(`振込金額は0以上の整数である必要があります: ${row.amount}`);
    }
    totalAmount += amtNum;
    const dataLine =
      "2" +
      padZenginNumeric(row.bankCode ?? "0005", 4) +
      padZenginAlpha(row.bankName ?? "ﾐﾂﾋﾞｼﾕｰｴﾌｼﾞｴｲ", 15) +
      padZenginNumeric(row.branchCode ?? "001", 3) +
      padZenginAlpha(row.branchName ?? "ﾎﾝﾃﾝ", 15) +
      "0000" +
      padZenginNumeric(row.accountType ?? "1", 1) +
      padZenginNumeric(row.accountNumber ?? "0000001", 7) +
      padZenginAlpha(row.recipientName ?? "ﾔﾏﾀﾞ ﾀﾛｳ", 30) +
      padZenginNumeric(amtNum, 10) +
      "0" +
      padZenginAlpha(row.ediInfo ?? "", 20) +
      padZenginNumeric(row.feeFlag ?? "7", 1) +
      " ".repeat(8);
    lines.push(dataLine);
  }

  const trailerLine =
    "8" +
    padZenginNumeric(transferList.length, 6) +
    padZenginNumeric(totalAmount, 12) +
    " ".repeat(101);

  const endLine = "9" + " ".repeat(119);
  lines.push(trailerLine, endLine);

  return {
    content: lines.join("\r\n") + "\r\n",
    lineCount: lines.length,
    dataCount: transferList.length,
    totalAmountYen: totalAmount,
  };
}

/**
 * Parse and strictly audit a 120-byte Zengin Sogo Furikomi text payload.
 */
export function parseZengin120(content) {
  const rawLines = String(content ?? "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((l) => l.length > 0);

  const errors = [];
  const rows = [];
  let header = null;
  let trailer = null;
  let hasEnd = false;
  let computedTotal = 0;

  for (let idx = 0; idx < rawLines.length; idx += 1) {
    const line = rawLines[idx];
    const lineNo = idx + 1;
    if (line.length !== 120) {
      errors.push({ line: lineNo, code: "LEN_NOT_120", message: `桁数が120バイトではありません (${line.length}バイト)` });
      continue;
    }
    if (!ZENGIN_LEGAL_RE.test(line)) {
      errors.push({ line: lineNo, code: "ILLEGAL_CHAR", message: "全銀協規定外文字が含まれています。" });
    }
    const recType = line[0];
    if (recType === "1") {
      header = {
        typeCode: line.slice(1, 3),
        requesterCode: line.slice(4, 14),
        requesterName: line.slice(14, 54).trimEnd(),
        transferDateMMDD: line.slice(54, 58),
      };
    } else if (recType === "2") {
      const amountStr = line.slice(80, 90);
      const amount = Number(amountStr);
      if (!/^\d{10}$/.test(amountStr)) {
        errors.push({ line: lineNo, code: "BAD_AMOUNT", message: `金額フィールドが数字10桁ではありません: ${amountStr}` });
      } else {
        computedTotal += amount;
      }
      rows.push({
        line: lineNo,
        bankCode: line.slice(1, 5),
        bankName: line.slice(5, 20).trimEnd(),
        branchCode: line.slice(20, 23),
        branchName: line.slice(23, 38).trimEnd(),
        accountType: line.slice(42, 43),
        accountNumber: line.slice(43, 50),
        recipientName: line.slice(50, 80).trimEnd(),
        amount,
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

  if (!header) errors.push({ line: 1, code: "MISSING_HEADER", message: "ヘッダ・レコード(区分1)がありません。" });
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
  if (!hasEnd) errors.push({ line: rawLines.length, code: "MISSING_END", message: "エンド・レコード(区分9)がありません。" });

  return {
    valid: errors.length === 0,
    header,
    rows,
    trailer,
    computedTotal,
    errors,
  };
}
