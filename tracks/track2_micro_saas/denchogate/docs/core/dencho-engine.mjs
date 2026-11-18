/**
 * DENCHOGATE Core Engine — 100% browser-local Revised Electronic Books Preservation Act
 * (改正電子帳簿保存法 第7条電子取引) search-key normalizer, workflow auditor & rules generator.
 */

function toHalfWidthAscii(text) {
  return String(text || "").replace(/[！-～]/g, (ch) =>
    String.fromCharCode(ch.charCodeAt(0) - 0xfee0),
  ).replace(/　/g, " ");
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

function sanitizeFilenameSegment(text) {
  return String(text || "")
    .replace(/[\\/:*?"<>|]/g, "")
    .replace(/\b(?:請求書|領収書|納品書|見積書|控え|再発行|税込|税抜|円|pdf|png|jpg|jpeg)\b/gi, "")
    .replace(/(?:請求書|領収書|納品書|見積書|御中|様|宛て)/g, "")
    .replace(/^[\s_\-,._・()（）[\]【】]+|[\s_\-,._・()（）[\]【】]+$/g, "")
    .replace(/\s+/g, "")
    .slice(0, 60);
}

/**
 * Normalize one messy PDF filename or CSV/tab line into Electronic Books Preservation Act 3-key search naming.
 */
export function normalizeDenchoRecord(rawLine) {
  const original = String(rawLine || "").trim();
  const norm = toHalfWidthAscii(original);

  // Strip extension only at end so embedded numbers don't break.
  const withoutExt = norm.replace(/\.(pdf|png|jpe?g|tiff?)$/i, "");
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
