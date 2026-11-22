/**
 * DENCHOGATE Core Engine v2.0 — 100% browser-local Revised Electronic Books Preservation Act
 * (改正電子帳簿保存法 第7条電子取引) PDF extractor, search-key normalizer, duplicate detector,
 * PKWARE Stored ZIP packager, workflow auditor & rules generator.
 */

import { buildStoredZip, crc32 } from "./zip-builder.mjs";
import {
  createSyntheticInvoicePdfBytes,
  extractTextFromPdfBytes,
  inflateFlateBytes,
} from "./pdf-text-extractor.mjs";

export {
  buildStoredZip,
  crc32,
  createSyntheticInvoicePdfBytes,
  extractTextFromPdfBytes,
  inflateFlateBytes,
};

const TEXT_ENCODER = new TextEncoder();

export const STUDIO_CSV_FILENAME = "検索用索引簿_電帳法.csv";
export const STUDIO_KITEI_FILENAME = "訂正削除防止_事務処理規程.md";

export const FILENAME_TEMPLATES = {
  compact_no_yen: "YYYYMMDD_取引先_金額",
  iso_yen: "YYYY-MM-DD_取引先_金額円",
  compact_yen: "YYYYMMDD_取引先_金額円",
};

function toHalfWidthAscii(text) {
  return String(text || "")
    .replace(/[！-～]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/￥/g, "¥")
    .replace(/　/g, " ");
}

function pad2(num) {
  return String(num).padStart(2, "0");
}

function validateCalendarDate(year, month, day) {
  if (year < 1926 || year > 2099 || month < 1 || month > 12 || day < 1 || day > 31) {
    return null;
  }
  const dt = new Date(Date.UTC(year, month - 1, day));
  if (
    dt.getUTCFullYear() !== year ||
    dt.getUTCMonth() + 1 !== month ||
    dt.getUTCDate() !== day
  ) {
    return null;
  }
  return `${year}${pad2(month)}${pad2(day)}`;
}

const ERA_BASE = {
  令和: 2018,
  R: 2018,
  平成: 1988,
  H: 1988,
  昭和: 1925,
  S: 1925,
};

/**
 * Parse Gregorian (`YYYY-MM-DD`, `YYYY/M/D`, `YYYYMMDD`, `YYYY年M月D日`) or Wareki
 * (`令和8年11月19日`, `令和元年5月1日`, `R6.4.5`) into `{ yyyymmdd, matched }`.
 */
export function parseJapaneseOrIsoDate(rawText) {
  const norm = toHalfWidthAscii(rawText);

  const warekiKanji = norm.match(
    /(令和|平成|昭和)\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?/,
  );
  if (warekiKanji) {
    const eraNum = warekiKanji[2] === "元" ? 1 : Number(warekiKanji[2]);
    const year = ERA_BASE[warekiKanji[1]] + eraNum;
    const yyyymmdd = validateCalendarDate(year, Number(warekiKanji[3]), Number(warekiKanji[4]));
    if (yyyymmdd) return { yyyymmdd, matched: warekiKanji[0] };
  }

  const warekiShort = norm.match(/\b([RHSrhs])\s*(\d{1,2})[./-](\d{1,2})[./-](\d{1,2})\b/);
  if (warekiShort) {
    const eraKey = warekiShort[1].toUpperCase();
    const year = ERA_BASE[eraKey] + Number(warekiShort[2]);
    const yyyymmdd = validateCalendarDate(year, Number(warekiShort[3]), Number(warekiShort[4]));
    if (yyyymmdd) return { yyyymmdd, matched: warekiShort[0] };
  }

  const gregSep = norm.match(/(19\d{2}|20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})\s*日?/);
  if (gregSep) {
    const yyyymmdd = validateCalendarDate(
      Number(gregSep[1]),
      Number(gregSep[2]),
      Number(gregSep[3]),
    );
    if (yyyymmdd) return { yyyymmdd, matched: gregSep[0] };
  }

  const compact = norm.match(/(?:^|[^\d])((?:19|20)\d{2})(\d{2})(\d{2})(?:[^\d]|$)/);
  if (compact) {
    const yyyymmdd = validateCalendarDate(
      Number(compact[1]),
      Number(compact[2]),
      Number(compact[3]),
    );
    if (yyyymmdd) return { yyyymmdd, matched: `${compact[1]}${compact[2]}${compact[3]}` };
  }

  return { yyyymmdd: "", matched: "" };
}

/**
 * Verify Japanese NTA Qualified Invoice ID (`T` + 13 digits, Modulo-9 check digit).
 */
export function verifyInvoiceTNumber(rawText) {
  const norm = toHalfWidthAscii(rawText);
  const m = norm.match(/T[-\s]?(\d{13})\b/i);
  if (!m) return { present: false, normalized: "", valid: null };
  const digits = m[1];
  const actualCd = Number(digits[0]);
  let total = 0;
  for (let idx = 1; idx < 13; idx += 1) {
    const q = Number(digits[13 - idx]);
    total += q * (idx % 2 === 1 ? 1 : 2);
  }
  const expectedCd = 9 - (total % 9);
  return {
    present: true,
    normalized: `T${digits}`,
    valid: actualCd === expectedCd,
    expectedCd,
  };
}

function parseAmountYen(normWithoutDatesOrIds) {
  const yenSuffix = normWithoutDatesOrIds.match(/([0-9][0-9,]{0,11})\s*円/);
  if (yenSuffix) {
    return { amount: Number(yenSuffix[1].replace(/,/g, "")), matched: yenSuffix[0] };
  }
  const yenPrefix = normWithoutDatesOrIds.match(/[¥\\]\s*([0-9][0-9,]{0,11})/);
  if (yenPrefix) {
    return { amount: Number(yenPrefix[1].replace(/,/g, "")), matched: yenPrefix[0] };
  }
  const commaNumber = normWithoutDatesOrIds.match(/\b([1-9]\d{0,2}(?:,\d{3})+)\b/);
  if (commaNumber) {
    return { amount: Number(commaNumber[1].replace(/,/g, "")), matched: commaNumber[0] };
  }
  const plainAmount = normWithoutDatesOrIds.match(/(?:^|[\s_,])(\d{2,9})(?=\s|$|[._])/);
  if (plainAmount) {
    return { amount: Number(plainAmount[1]), matched: plainAmount[1] };
  }
  return { amount: null, matched: "" };
}

export function sanitizeFilenameSegment(text) {
  return String(text || "")
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "")
    .replace(/\b(?:請求書|領収書|納品書|見積書|控え|再発行|税込|税抜|円|pdf|png|jpg|jpeg|webp|tiff?)\b/gi, "")
    .replace(/(?:御請求書|請求書|領収書|納品書|見積書|御中|様|宛て)/g, "")
    .replace(/^[\s_\-,._・()（）[\]【】]+|[\s_\-,._・()（）[\]【】]+$/g, "")
    .replace(/\s+/g, "")
    .slice(0, 60);
}

function extractExtension(filename) {
  const m = String(filename || "").trim().match(/(\.(?:pdf|png|jpe?g|webp|tiff?|txt|csv))$/i);
  return m ? m[1].toLowerCase() : ".pdf";
}

function isGenericFilenameStem(stem) {
  const norm = toHalfWidthAscii(stem).trim().toLowerCase();
  if (!norm) return true;
  if (
    /^(?:invoice|receipt|bill|statement|download|document|doc|scan|scanned|img|image|photo|pic|file|page|untitled|copy|export|output|report|order|attachment|pdf|dsc|pxl|screenshot|領収書|請求書|納品書|見積書|明細|明細書|レシート|控え)(?:[\s_\-.()]*(?:\d+|copy|dup|final|v\d+|scan|new|fixed|\(\d+\)))*$/i.test(
      norm,
    )
  ) {
    return true;
  }
  return /^[\d\s_\-.()]+$/.test(norm);
}

/**
 * Normalize one messy PDF filename or CSV/tab line into Electronic Books Preservation Act 3-key search naming.
 */
export function normalizeDenchoRecord(rawLine) {
  const original = String(rawLine || "").trim();
  const norm = toHalfWidthAscii(original);

  // Strip extension only at end so embedded numbers don't break.
  const withoutExt = norm.replace(/\.(pdf|png|jpe?g|webp|tiff?)$/i, "");
  const dateRes = parseJapaneseOrIsoDate(withoutExt);
  const invRes = verifyInvoiceTNumber(withoutExt);

  let remainder = withoutExt;
  if (dateRes.matched) remainder = remainder.replace(dateRes.matched, " ");
  if (invRes.normalized) remainder = remainder.replace(/T[-\s]?\d{13}/i, " ");

  const amtRes = parseAmountYen(remainder);
  if (amtRes.matched) remainder = remainder.replace(amtRes.matched, " ");

  // Strip tab/comma delimiters if input came from CSV-like pasted lines.
  remainder = remainder.replace(/[\t,;]+/g, " ");
  const partner = sanitizeFilenameSegment(remainder);

  const missingKeys = [];
  if (!dateRes.yyyymmdd) missingKeys.push("date");
  if (!partner) missingKeys.push("partner");
  if (amtRes.amount === null || !Number.isFinite(amtRes.amount)) missingKeys.push("amount");

  const compliant = missingKeys.length === 0;
  const datePart = dateRes.yyyymmdd || "DATE_MISSING";
  const partnerPart = partner || "PARTNER_MISSING";
  const amountPart = amtRes.amount !== null ? `${amtRes.amount}円` : "AMOUNT_MISSING";
  const standardizedFilename = `${datePart}_${partnerPart}_${amountPart}.pdf`;

  return {
    original,
    date: dateRes.yyyymmdd,
    partner,
    amountYen: amtRes.amount,
    invoiceId: invRes.normalized,
    invoiceIdValid: invRes.valid,
    standardizedFilename,
    missingKeys,
    compliant,
  };
}

function parseAmountCandidatesFromLine(line) {
  const cleaned = line
    .replace(/T[-\s]?\d{13}/gi, " ")
    .replace(/〒\s*\d{3}-?\d{4}/g, " ")
    .replace(/\b0\d{1,4}-\d{1,4}-\d{3,4}\b/g, " ")
    .replace(/(?:19|20)\d{2}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?/g, " ");

  const results = [];
  const patterns = [
    /[¥\\]\s*([0-9][0-9,]{0,11})\s*(?:円|円也|-)?/g,
    /([0-9][0-9,]{0,11})\s*円(?:也|\s*[（(]?税込[)）]?)?/g,
  ];
  for (const pat of patterns) {
    let m;
    while ((m = pat.exec(cleaned)) !== null) {
      const val = Number(m[1].replace(/,/g, ""));
      if (Number.isFinite(val) && val >= 0 && val < 100_000_000_000) {
        results.push(val);
      }
    }
  }
  return results;
}

function cleanExtractedPartner(rawCandidate) {
  let s = toHalfWidthAscii(rawCandidate || "").trim();
  s = s.replace(/^(?:発行元|発行者|請求元|請求者|販売元|販売店|店舗名|事業者名|会社名|発行事業者|取引先|屋号|Issuer|Vendor|From)\s*[:：]\s*/i, "");
  s = s.replace(/\s*(?:登録番号|適格請求書|TEL|FAX|〒|http|https|E-?mail).*$/i, "");
  s = s.replace(/[（(][^）)]*(?:担当|経理|営業)[^）)]*[)）]/g, "");
  return sanitizeFilenameSegment(s);
}

/**
 * Extract Dencho-ho 3 search keys + Qualified Invoice T-number from digital PDF text
 * (with safe fallback to filename when filename is non-generic).
 *
 * @param {string | { text?: string }} textOrExtraction
 * @param {{ filename?: string }} [options]
 */
export function extractDenchoFieldsFromText(textOrExtraction, { filename = "" } = {}) {
  const rawText =
    typeof textOrExtraction === "string"
      ? textOrExtraction
      : String(textOrExtraction?.text || "");

  const normText = toHalfWidthAscii(rawText);
  const lines = normText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const sources = {
    date: "missing",
    partner: "missing",
    amount: "missing",
    invoiceId: "missing",
  };

  // --- 1. Transaction / Issue Date ---
  let date = "";
  const issueLabelRe = /(?:発行日|請求日|取引日|領収日|ご利用日|利用日|決済日|購入日|売上日|日付|Invoice\s*Date|Issue\s*Date|Date)\s*[:：]?/i;
  const dueDateRe = /(?:支払期限|お支払期限|お支払期日|支払期日|振込期限|有効期限|Due\s*Date)/i;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (issueLabelRe.test(line) && !dueDateRe.test(line)) {
      const d = parseJapaneseOrIsoDate(line);
      if (d.yyyymmdd) {
        date = d.yyyymmdd;
        sources.date = "pdf_text";
        break;
      }
      if (i + 1 < lines.length) {
        const nextD = parseJapaneseOrIsoDate(lines[i + 1]);
        if (nextD.yyyymmdd) {
          date = nextD.yyyymmdd;
          sources.date = "pdf_text";
          break;
        }
      }
    }
  }
  if (!date) {
    for (const line of lines) {
      if (dueDateRe.test(line)) continue;
      const d = parseJapaneseOrIsoDate(line);
      if (d.yyyymmdd) {
        date = d.yyyymmdd;
        sources.date = "pdf_text";
        break;
      }
    }
  }
  if (!date) {
    for (const line of lines) {
      const d = parseJapaneseOrIsoDate(line);
      if (d.yyyymmdd) {
        date = d.yyyymmdd;
        sources.date = "pdf_text";
        break;
      }
    }
  }

  // --- 2. Qualified Invoice T-Number (NTA Modulo-9) ---
  let invoiceId = "";
  let invoiceIdValid = null;
  const tCandidates = [];
  for (const line of lines) {
    const matches = line.matchAll(/T[-\s]?(\d{13})\b/gi);
    for (const m of matches) {
      const check = verifyInvoiceTNumber(`T${m[1]}`);
      if (check.present) {
        tCandidates.push({
          ...check,
          labeled: /(?:登録番号|適格請求書|インボイス|Registration)/i.test(line),
        });
      }
    }
  }
  if (tCandidates.length > 0) {
    tCandidates.sort((a, b) => {
      const score = (c) => (c.labeled ? 4 : 0) + (c.valid ? 2 : 0);
      return score(b) - score(a);
    });
    invoiceId = tCandidates[0].normalized;
    invoiceIdValid = tCandidates[0].valid;
    sources.invoiceId = "pdf_text";
  }

  // --- 3. Total Amount (Yen) ---
  let amountYen = null;
  const grandTotalLabelRe =
    /(?:ご請求金額|御請求金額|ご請求額|御請求額|請求金額|領収金額|お支払金額|お買上合計|合計金額|税込合計|合計\s*[（(]?\s*税込\s*[)）]?|総額|Grand\s*Total|Total\s*Amount)/i;
  const genericTotalRe = /(?:^|\s)(?:合計|計|Total)\s*[:：]?/i;
  const subOrTaxRe = /(?:小計|消費税|内消費税|税額|Subtotal|Tax)/i;

  const tier1Amounts = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!grandTotalLabelRe.test(line)) continue;
    const sameLine = parseAmountCandidatesFromLine(line);
    if (sameLine.length > 0) {
      tier1Amounts.push(...sameLine);
    } else if (i + 1 < lines.length) {
      const nextLine = parseAmountCandidatesFromLine(lines[i + 1]);
      if (nextLine.length > 0) {
        tier1Amounts.push(...nextLine);
      } else {
        const bareNum = lines[i + 1].match(/^\s*[¥\\]?\s*([0-9][0-9,]{0,11})\s*-?\s*$/);
        if (bareNum) tier1Amounts.push(Number(bareNum[1].replace(/,/g, "")));
      }
    }
  }

  if (tier1Amounts.length > 0) {
    amountYen = Math.max(...tier1Amounts);
    sources.amount = "pdf_text";
  }

  if (amountYen === null) {
    const tier2Amounts = [];
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (genericTotalRe.test(line) && !subOrTaxRe.test(line)) {
        const amts = parseAmountCandidatesFromLine(line);
        if (amts.length > 0) tier2Amounts.push(...amts);
        else if (i + 1 < lines.length) {
          tier2Amounts.push(...parseAmountCandidatesFromLine(lines[i + 1]));
        }
      }
    }
    if (tier2Amounts.length > 0) {
      amountYen = Math.max(...tier2Amounts);
      sources.amount = "pdf_text";
    }
  }

  if (amountYen === null) {
    const allCurrencyAmounts = [];
    for (const line of lines) {
      if (subOrTaxRe.test(line)) continue;
      allCurrencyAmounts.push(...parseAmountCandidatesFromLine(line));
    }
    if (allCurrencyAmounts.length > 0) {
      amountYen = Math.max(...allCurrencyAmounts);
      sources.amount = "pdf_text";
    }
  }

  // --- 4. Partner / Issuer Name ---
  let partner = "";
  const issuerLabelRe =
    /^(?:発行元|発行者|請求元|請求者|販売元|販売店|店舗名|事業者名|会社名|発行事業者|取引先|屋号|Issuer|Vendor|From)\s*[:：]\s*(.+)$/i;
  const recipientLineRe = /(?:御中|様|殿)\s*$|^(?:請求先|宛先|お客様|Bill\s*to|To)\s*[:：]/i;
  const jpEntityPrefixRe =
    /((?:株式会社|合同会社|有限会社|合資会社|合名会社|一般社団法人|一般財団法人|公益社団法人|公益財団法人|特定非営利活動法人|NPO法人|医療法人|学校法人|税理士法人|弁護士法人|司法書士法人|社会保険労務士法人|行政書士法人)[^\s、。,:：/()（）]{1,35})/;
  const jpEntitySuffixRe =
    /([^\s、。,:：/()（）]{2,35}(?:株式会社|合同会社|有限会社|商店|製作所|事務所|クリニック|薬局|ホテル|旅館|書房|出版|工業|建設|運送|商事|物産|産業|システムズ|テクノロジー|ソリューションズ|サービス))/;
  const enEntityRe =
    /([A-Z][A-Za-z0-9&.\- ]{1,40}\b(?:Inc\.?|LLC|Ltd\.?|Co\.,?\s*Ltd\.?|Corp\.?|G\.?K\.?))/;

  // Tier 1: explicit issuer label
  for (const line of lines) {
    const m = line.match(issuerLabelRe);
    if (m) {
      const cleaned = cleanExtractedPartner(m[1]);
      if (cleaned) {
        partner = cleaned;
        sources.partner = "pdf_text";
        break;
      }
    }
  }

  // Tier 2: corporate entity name (not recipient)
  if (!partner) {
    for (const line of lines) {
      if (recipientLineRe.test(line)) continue;
      if (/DENCHOGATE|サンプル請求書です/i.test(line)) continue;
      const m = line.match(jpEntityPrefixRe) || line.match(jpEntitySuffixRe) || line.match(enEntityRe);
      if (m) {
        const cleaned = cleanExtractedPartner(m[1]);
        if (cleaned) {
          partner = cleaned;
          sources.partner = "pdf_text";
          break;
        }
      }
    }
  }

  // Tier 3: line immediately adjacent to T-number registration line
  if (!partner && invoiceId) {
    const tLineIdx = lines.findIndex((l) => l.toUpperCase().includes(invoiceId));
    if (tLineIdx > 0) {
      const prev = lines[tLineIdx - 1];
      if (
        !recipientLineRe.test(prev) &&
        !/^(?:〒|TEL|FAX|http|小計|合計|消費税|発行日|No\.)/i.test(prev)
      ) {
        const cleaned = cleanExtractedPartner(prev);
        if (cleaned && cleaned.length >= 2) {
          partner = cleaned;
          sources.partner = "pdf_text";
        }
      }
    }
  }

  // --- 5. Filename Fallback (only when filename carries real metadata) ---
  if (filename) {
    const stem = toHalfWidthAscii(filename).replace(/\.(pdf|png|jpe?g|webp|tiff?|txt|csv)$/i, "");
    const generic = isGenericFilenameStem(stem);

    if (!date) {
      const fd = parseJapaneseOrIsoDate(stem);
      if (fd.yyyymmdd) {
        date = fd.yyyymmdd;
        sources.date = "filename";
      }
    }
    if (!invoiceId) {
      const ft = verifyInvoiceTNumber(stem);
      if (ft.present) {
        invoiceId = ft.normalized;
        invoiceIdValid = ft.valid;
        sources.invoiceId = "filename";
      }
    }
    if (!generic) {
      const fnRec = normalizeDenchoRecord(filename);
      if (amountYen === null && fnRec.amountYen !== null) {
        amountYen = fnRec.amountYen;
        sources.amount = "filename";
      }
      if (!partner && fnRec.partner && !isGenericFilenameStem(fnRec.partner)) {
        partner = fnRec.partner;
        sources.partner = "filename";
      }
    }
  }

  const missingKeys = [];
  if (!date) missingKeys.push("date");
  if (!partner) missingKeys.push("partner");
  if (amountYen === null || !Number.isFinite(amountYen)) missingKeys.push("amount");

  const usedPdf = Object.values(sources).includes("pdf_text");
  const usedFilename = Object.values(sources).includes("filename");
  const primarySource = usedPdf
    ? usedFilename
      ? "pdf+filename"
      : "pdf_text"
    : usedFilename
      ? "filename"
      : "manual_required";

  return {
    date,
    partner,
    amountYen,
    invoiceId,
    invoiceIdValid,
    missingKeys,
    compliant: missingKeys.length === 0,
    sources,
    primarySource,
  };
}

/**
 * Format standardized filename using chosen Studio template and optional T-number suffix.
 *
 * @param {{
 *   date?: string,
 *   partner?: string,
 *   amountYen?: number | null,
 *   invoiceId?: string,
 *   extension?: string,
 * }} record
 * @param {{
 *   template?: "compact_no_yen" | "iso_yen" | "compact_yen",
 *   includeTNumber?: boolean,
 * }} [options]
 */
export function formatDenchoFilename(
  record,
  { template = "compact_no_yen", includeTNumber = false } = {},
) {
  const rawDate = String(record.date || "").trim();
  const parsedDate = /^\d{8}$/.test(rawDate) ? rawDate : parseJapaneseOrIsoDate(rawDate).yyyymmdd;
  const partner = sanitizeFilenameSegment(record.partner || "");
  const amountYen =
    record.amountYen !== null && record.amountYen !== undefined && record.amountYen !== ""
      ? Number(String(record.amountYen).replace(/[,¥円\s]/g, ""))
      : null;
  const validAmount = amountYen !== null && Number.isFinite(amountYen) && amountYen >= 0 ? Math.trunc(amountYen) : null;

  const invCheck = record.invoiceId ? verifyInvoiceTNumber(record.invoiceId) : { present: false, normalized: "", valid: null };
  const invoiceId = invCheck.present ? invCheck.normalized : "";

  const ext = record.extension ? (record.extension.startsWith(".") ? record.extension.toLowerCase() : `.${record.extension.toLowerCase()}`) : ".pdf";

  const missingKeys = [];
  if (!parsedDate) missingKeys.push("date");
  if (!partner) missingKeys.push("partner");
  if (validAmount === null) missingKeys.push("amount");

  let datePart = "DATE_MISSING";
  if (parsedDate) {
    datePart =
      template === "iso_yen"
        ? `${parsedDate.slice(0, 4)}-${parsedDate.slice(4, 6)}-${parsedDate.slice(6, 8)}`
        : parsedDate;
  }
  const partnerPart = partner || "PARTNER_MISSING";

  let amountPart = "AMOUNT_MISSING";
  if (validAmount !== null) {
    amountPart = template === "compact_no_yen" ? `${validAmount}` : `${validAmount}円`;
  }

  const tSuffix = includeTNumber && invoiceId ? `_${invoiceId}` : "";
  const filename = `${datePart}_${partnerPart}_${amountPart}${tSuffix}${ext}`;

  return {
    filename,
    date: parsedDate,
    partner,
    amountYen: validAmount,
    invoiceId,
    invoiceIdValid: invCheck.valid,
    missingKeys,
    compliant: missingKeys.length === 0,
  };
}

/**
 * Prevent case-insensitive filename collisions across a batch by appending `_2`, `_3`, ...
 * Also reserves the NTA index CSV and internal rules Markdown names.
 */
export function resolveFilenameCollisions(
  records,
  { reservedNames = [STUDIO_CSV_FILENAME, STUDIO_KITEI_FILENAME] } = {},
) {
  const claimed = new Set(reservedNames.map((n) => String(n).toLowerCase()));
  return records.map((rec) => {
    const rawName = String(rec.standardizedFilename || "unnamed.pdf");
    const dotIdx = rawName.lastIndexOf(".");
    let stem = dotIdx > 0 ? rawName.slice(0, dotIdx) : rawName;
    const ext = dotIdx > 0 ? rawName.slice(dotIdx) : "";
    if (rec.collisionSuffix && stem.endsWith(rec.collisionSuffix)) {
      stem = stem.slice(0, -rec.collisionSuffix.length);
    }

    let candidate = `${stem}${ext}`;
    let suffix = "";
    let counter = 2;
    while (claimed.has(candidate.toLowerCase())) {
      suffix = `_${counter}`;
      candidate = `${stem}${suffix}${ext}`;
      counter += 1;
    }
    claimed.add(candidate.toLowerCase());

    return {
      ...rec,
      standardizedFilename: candidate,
      collisionSuffix: suffix,
    };
  });
}

/**
 * Compute lowercase 64-char SHA-256 hex digest using standard Web Crypto API (browser & Node 22).
 * @param {Uint8Array | ArrayBuffer | string} input
 * @returns {Promise<string>}
 */
export async function computeSha256Hex(input) {
  const bytes =
    typeof input === "string"
      ? TEXT_ENCODER.encode(input)
      : input instanceof Uint8Array
        ? input
        : new Uint8Array(input);

  if (!globalThis.crypto?.subtle?.digest) {
    throw new Error("Web Crypto subtle.digest(SHA-256) is unavailable in this runtime");
  }
  const digestBuf = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  const digestBytes = new Uint8Array(digestBuf);
  let hex = "";
  for (let i = 0; i < digestBytes.length; i += 1) {
    hex += digestBytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

/**
 * Flag byte-identical duplicate receipts based on exact SHA-256 hash.
 */
export function markDuplicateRecords(records) {
  const hashCounts = new Map();
  for (const r of records) {
    if (r.sha256) {
      hashCounts.set(r.sha256, (hashCounts.get(r.sha256) || 0) + 1);
    }
  }

  const firstSeenByHash = new Map();
  return records.map((r) => {
    const hash = r.sha256 || "";
    if (!hash) {
      return {
        ...r,
        isDuplicate: false,
        hasDuplicatePeer: false,
        duplicateOf: "",
        duplicateGroupSize: 1,
      };
    }
    const groupSize = hashCounts.get(hash) || 1;
    const firstOwner = firstSeenByHash.get(hash);
    if (!firstOwner) {
      firstSeenByHash.set(hash, r.originalName || r.original || r.standardizedFilename);
      return {
        ...r,
        isDuplicate: false,
        hasDuplicatePeer: groupSize > 1,
        duplicateOf: "",
        duplicateGroupSize: groupSize,
      };
    }
    return {
      ...r,
      isDuplicate: true,
      hasDuplicatePeer: true,
      duplicateOf: firstOwner,
      duplicateGroupSize: groupSize,
    };
  });
}

/**
 * Analyze a locally loaded file (PDF / image) end-to-end without leaving the browser.
 */
export async function analyzeUploadedFile({
  name,
  bytes,
  mimeType = "",
  template = "compact_no_yen",
  includeTNumber = false,
}) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const extension = extractExtension(name);
  const sha256 = await computeSha256Hex(u8);
  const isPdf = extension === ".pdf" || mimeType === "application/pdf";

  let pdfExtraction = null;
  if (isPdf) {
    pdfExtraction = await extractTextFromPdfBytes(u8);
  }

  const fields = extractDenchoFieldsFromText(pdfExtraction || "", { filename: name });
  const formatted = formatDenchoFilename(
    {
      date: fields.date,
      partner: fields.partner,
      amountYen: fields.amountYen,
      invoiceId: fields.invoiceId,
      extension,
    },
    { template, includeTNumber },
  );

  return {
    originalName: name,
    extension,
    mimeType: mimeType || (isPdf ? "application/pdf" : "application/octet-stream"),
    sizeBytes: u8.byteLength,
    sha256,
    sha256Short: sha256.slice(0, 12),
    extractedText: pdfExtraction?.text || "",
    isEncryptedPdf: Boolean(pdfExtraction?.isEncrypted),
    isLikelyScannedPdf: Boolean(pdfExtraction?.isLikelyScanned),
    extractionWarnings: pdfExtraction?.warnings || [],
    primarySource: fields.primarySource,
    sources: fields.sources,
    date: formatted.date,
    partner: formatted.partner,
    amountYen: formatted.amountYen,
    invoiceId: formatted.invoiceId,
    invoiceIdValid: formatted.invoiceIdValid,
    standardizedFilename: formatted.filename,
    missingKeys: formatted.missingKeys,
    compliant: formatted.compliant,
    collisionSuffix: "",
    isDuplicate: false,
    hasDuplicatePeer: false,
    duplicateOf: "",
    duplicateGroupSize: 1,
  };
}

function escapeCsvCell(val) {
  const s = String(val ?? "");
  return `"${s.replace(/"/g, '""')}"`;
}

/**
 * Normalize a multiline batch of filenames or CSV lines and emit an NTA-style search index CSV.
 */
export function normalizeDenchoBatch(multilineText) {
  const lines = String(multilineText || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const records = lines.map(normalizeDenchoRecord);
  const compliantCount = records.filter((r) => r.compliant).length;
  const header = [
    "取引年月日",
    "取引先名",
    "取引金額",
    "適格請求書番号",
    "T番号チェック",
    "推奨標準ファイル名",
    "判定",
  ].join(",");

  const csvRows = records.map((r) =>
    [
      escapeCsvCell(r.date || "要補完"),
      escapeCsvCell(r.partner || "要補完"),
      escapeCsvCell(r.amountYen ?? ""),
      escapeCsvCell(r.invoiceId),
      escapeCsvCell(
        r.invoiceId ? (r.invoiceIdValid ? "Mod-9妥当" : "チェックデジット不整合") : "-",
      ),
      escapeCsvCell(r.standardizedFilename),
      escapeCsvCell(r.compliant ? "要件充足" : `不足:${r.missingKeys.join("/")}`),
    ].join(","),
  );

  return {
    totalCount: records.length,
    compliantCount,
    nonCompliantCount: records.length - compliantCount,
    records,
    indexCsvUtf8Bom: `\uFEFF${header}\n${csvRows.join("\n")}\n`,
  };
}

const SOURCE_LABELS = {
  pdf_text: "PDF本文抽出",
  "pdf+filename": "PDF本文＋ファイル名",
  filename: "ファイル名抽出",
  manual: "手動編集",
  manual_required: "手入力待ち",
};

/**
 * Build Studio v2 Excel-ready UTF-8 BOM NTA Search Index CSV with SHA-256 & duplicate audit columns.
 */
export function buildStudioIndexCsv(records) {
  const header = [
    "取引年月日",
    "取引先名",
    "取引金額",
    "適格請求書番号",
    "T番号チェック",
    "変更後ファイル名",
    "元ファイル名",
    "抽出元",
    "SHA-256",
    "重複検知",
    "要件判定",
  ].join(",");

  const rows = records.map((r) => {
    const tStatus = r.invoiceId
      ? r.invoiceIdValid
        ? "Mod-9妥当"
        : "チェックデジット不整合"
      : "-";
    const dupLabel = r.isDuplicate
      ? `重複（元: ${r.duplicateOf}）`
      : r.hasDuplicatePeer
        ? "同一ハッシュあり（原本側）"
        : "-";
    const judge = r.compliant ? "要件充足" : `不足:${(r.missingKeys || []).join("/")}`;
    return [
      escapeCsvCell(r.date || "要補完"),
      escapeCsvCell(r.partner || "要補完"),
      escapeCsvCell(r.amountYen ?? ""),
      escapeCsvCell(r.invoiceId || ""),
      escapeCsvCell(tStatus),
      escapeCsvCell(r.standardizedFilename || ""),
      escapeCsvCell(r.originalName || r.original || ""),
      escapeCsvCell(SOURCE_LABELS[r.primarySource] || r.primarySource || "-"),
      escapeCsvCell(r.sha256 || ""),
      escapeCsvCell(dupLabel),
      escapeCsvCell(judge),
    ].join(",");
  });

  return `\uFEFF${header}\n${rows.join("\n")}\n`;
}

/**
 * Assemble a 1-click tax-office-ready Stored ZIP containing:
 * - All renamed binary files (PDF/PNG/JPG/WebP) with collision-free UTF-8 Japanese names
 * - `検索用索引簿_電帳法.csv` (UTF-8 BOM, Excel-ready, NTA 3 search keys + SHA-256 + T-number check)
 * - `訂正削除防止_事務処理規程.md`
 *
 * @param {{
 *   records: Array<{ standardizedFilename: string, bytes?: Uint8Array | null, isDuplicate?: boolean }>,
 *   kiteiOptions?: { companyName?: string, managerTitle?: string, effectiveDate?: string },
 *   includeDuplicates?: boolean,
 *   mtime?: Date,
 * }} params
 */
export function buildDenchoZipPackage({
  records = [],
  kiteiOptions = {},
  includeDuplicates = true,
  mtime = new Date(),
} = {}) {
  const excludedDuplicatesCount = includeDuplicates
    ? 0
    : records.filter((r) => r.isDuplicate).length;
  const filtered = includeDuplicates ? records : records.filter((r) => !r.isDuplicate);
  const resolved = resolveFilenameCollisions(filtered);

  const csvContent = buildStudioIndexCsv(resolved);
  const kiteiContent = generateJimuShoriKitei(kiteiOptions);

  const entries = [];
  for (const rec of resolved) {
    if (rec.bytes && rec.bytes.byteLength > 0) {
      entries.push({
        name: rec.standardizedFilename,
        data: rec.bytes,
        mtime,
      });
    }
  }
  entries.push({
    name: STUDIO_CSV_FILENAME,
    data: csvContent,
    mtime,
  });
  entries.push({
    name: STUDIO_KITEI_FILENAME,
    data: kiteiContent,
    mtime,
  });

  const zipBytes = buildStoredZip(entries);
  return {
    zipBytes,
    entryCount: entries.length,
    binaryFileCount: entries.length - 2,
    excludedDuplicatesCount,
    includedRecords: resolved,
    csvContent,
    kiteiContent,
  };
}

/**
 * Audit electronic transaction preservation workflow under Art. 7 of the Japanese Electronic Books Preservation Act.
 */
export function auditDenchoWorkflow({
  workflowText = "",
  isUnder50M = false,
  hasImmutableSystem = false,
  hasJimuKitei = false,
  hasSearchableNamingOrCsv = false,
} = {}) {
  const text = toHalfWidthAscii(workflowText);
  const findings = [];

  if (
    /(?:紙(?:に|で)?印刷して|プリントアウトして|電子ファイルは破棄|原本は紙のみで保管)/.test(
      text,
    )
  ) {
    findings.push({
      ruleId: "DENCHO-PAPER-ONLY-NG",
      severity: "high",
      severityLabel: "高（法令違反）",
      weight: 40,
      law: "電子帳簿保存法 第7条（2024年1月完全義務化）",
      matched: "電子取引データを紙出力のみ保存・電子データ削除",
      counterClause:
        "PDF・メール受信データは改ざん防止措置を講じた上で電子データのまま7年（繰越欠損金あり10年）保存へ切替えてください。",
    });
  }

  const textHasKitei = /(?:事務処理規程|訂正及び削除の防止に関する規程)/.test(text);
  const textHasSystem = /(?:タイムスタンプ|訂正削除(?:の|履歴)が(?:残る|確認できる)|クラウド会計|電子帳簿システム)/.test(
    text,
  );
  if (!hasImmutableSystem && !hasJimuKitei && !textHasKitei && !textHasSystem) {
    findings.push({
      ruleId: "DENCHO-TRUTH-MISSING",
      severity: "high",
      severityLabel: "高（真実性要件欠落）",
      weight: 35,
      law: "電帳法施行規則 第4条第1項（真実性の確保）",
      matched: "タイムスタンプ・履歴保存システム・事務処理規程のいずれも未確認",
      counterClause:
        "無料対応としては本画面下の「電子取引データの訂正及び削除の防止に関する事務処理規程」を作成・備付けして運用してください。",
    });
  }

  const textHasSearch = /(?:YYYYMMDD|索引簿|日付[_・]取引先[_・]金額|検索(?:用)?CSV|Excel管理簿)/i.test(
    text,
  );
  if (!hasSearchableNamingOrCsv && !textHasSearch) {
    findings.push({
      ruleId: "DENCHO-SEARCH-MISSING",
      severity: isUnder50M ? "medium" : "high",
      severityLabel: isUnder50M ? "中（猶予特例確認）" : "高（検索3要件欠落）",
      weight: isUnder50M ? 15 : 30,
      law: "電帳法施行規則 第4条（検索要件：日付・金額・取引先）",
      matched: "日付・金額・取引先の規則的ファイル名または索引簿が未整備",
      counterClause: isUnder50M
        ? "基準期間売上5,000万円以下特例が使える場合もありますが、実務上「YYYYMMDD_取引先_金額.pdf」と索引簿CSVの併用を推奨します。"
        : "「YYYYMMDD_取引先名_金額.pdf」へ一括改名するか、検索用索引簿CSV（上記パネルで自動出力）を同フォルダへ保存してください。",
    });
  }

  if (/(?:100\s*dpi|150\s*dpi|低解像度|白黒2値スキャン)/i.test(text)) {
    findings.push({
      ruleId: "DENCHO-SCANNER-DPI",
      severity: "medium",
      severityLabel: "中（スキャナ保存要件）",
      weight: 18,
      law: "電帳法施行規則 第2条第6項（解像度200dpi・24bitカラー相当）",
      matched: "スキャナ保存設定が200dpi未満またはグレースケール固定の懸念",
      counterClause:
        "紙領収書のスキャナ保存（4条3項）を行う場合は解像度200dpi以上・階調情報（原則256階調カラー）を満たす設定へ変更してください。",
    });
  }

  const penalty = findings.reduce((acc, f) => acc + f.weight, 0);
  const complianceScore = Math.max(0, 100 - penalty);
  const statusLabel =
    complianceScore >= 90
      ? "要件充足・税務調査対応可"
      : complianceScore >= 60
        ? "一部改善推奨"
        : "法令不適合リスク高";

  return {
    complianceScore,
    statusLabel,
    findingsCount: findings.length,
    findings,
  };
}

/**
 * Generate NTA-compliant internal control rules Markdown for electronic transactions.
 */
export function generateJimuShoriKitei({
  companyName = "株式会社サンプル",
  managerTitle = "経理責任者",
  effectiveDate = "2026-11-19",
} = {}) {
  return [
    "# 電子取引データの訂正及び削除の防止に関する事務処理規程",
    "",
    `- 事業者名: ${companyName}`,
    `- 管理責任者: ${managerTitle}`,
    `- 施行日: ${effectiveDate}`,
    "",
    "## 第1条（目的）",
    `本規程は、電子帳簿保存法第7条に基づき、${companyName}が授受した請求書・領収書等の電子取引データについて、正当な理由なき訂正及び削除を防止し、真実性及び可視性を確保することを目的とする。`,
    "",
    "## 第2条（対象となる電子取引データ）",
    "1. メール・Webダウンロード・クラウド請求サービス等で受領または交付した請求書、領収書、契約書、見積書、注文書のPDF等",
    "2. 上記データに付随する検索用索引簿CSVデータ",
    "",
    "## 第3条（訂正・削除の原則禁止と申請手続）",
    `受領・保存した電子取引データは原則として訂正及び削除を行わない。やむを得ず訂正又は削除を行う場合は、${managerTitle}へ理由・対象ファイル・日時を記した訂正削除申請書（メール/ワークフロー記録可）を提出し承認を得るものとする。`,
    "",
    "## 第4条（検索性及び保存期間）",
    "電子取引データは原則として `YYYYMMDD_取引先名_金額.pdf` 形式で命名し、取引年月日・取引金額・取引先名により検索可能な状態を維持したうえで、法人税法・所得税法に定める期間（原則7年、欠損金生ずる事業年度は10年）保存する。",
  ].join("\n");
}
