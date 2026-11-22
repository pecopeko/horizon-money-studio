import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  STUDIO_CSV_FILENAME,
  STUDIO_KITEI_FILENAME,
  analyzeUploadedFile,
  auditDenchoWorkflow,
  buildDenchoZipPackage,
  buildStoredZip,
  computeSha256Hex,
  crc32,
  createSyntheticInvoicePdfBytes,
  extractDenchoFieldsFromText,
  extractTextFromPdfBytes,
  formatDenchoFilename,
  generateJimuShoriKitei,
  markDuplicateRecords,
  normalizeDenchoBatch,
  normalizeDenchoRecord,
  parseJapaneseOrIsoDate,
  resolveFilenameCollisions,
} from "../docs/core/dencho-engine.mjs";

const TEXT_DECODER = new TextDecoder("utf-8", { ignoreBOM: true });

function readStoredZipEntries(zipBytes) {
  const view = new DataView(zipBytes.buffer, zipBytes.byteOffset, zipBytes.byteLength);
  // Find EOCD at end (no comment => last 22 bytes)
  const eocdOff = zipBytes.byteLength - 22;
  assert.equal(view.getUint32(eocdOff, true), 0x06054b50, "EOCD signature PK\\x05\\x06");
  const entryCount = view.getUint16(eocdOff + 10, true);
  const cdSize = view.getUint32(eocdOff + 12, true);
  const cdOffset = view.getUint32(eocdOff + 16, true);
  assert.equal(cdOffset + cdSize, eocdOff);

  const entries = [];
  let ptr = cdOffset;
  for (let i = 0; i < entryCount; i += 1) {
    assert.equal(view.getUint32(ptr, true), 0x02014b50, "Central Dir signature PK\\x01\\x02");
    const cdFlags = view.getUint16(ptr + 8, true);
    const cdMethod = view.getUint16(ptr + 10, true);
    const cdCrc = view.getUint32(ptr + 16, true);
    const cdCompSize = view.getUint32(ptr + 20, true);
    const cdUncompSize = view.getUint32(ptr + 24, true);
    const nameLen = view.getUint16(ptr + 28, true);
    const extraLen = view.getUint16(ptr + 30, true);
    const commentLen = view.getUint16(ptr + 32, true);
    const localOff = view.getUint32(ptr + 42, true);
    const name = TEXT_DECODER.decode(zipBytes.subarray(ptr + 46, ptr + 46 + nameLen));

    assert.equal(cdFlags & 0x0800, 0x0800, "UTF-8 flag bit 11 must be set in Central Dir");
    assert.equal(cdMethod, 0, "Stored compression method 0");
    assert.equal(cdCompSize, cdUncompSize);

    // Inspect matching Local File Header
    assert.equal(view.getUint32(localOff, true), 0x04034b50, "Local header signature PK\\x03\\x04");
    const lfFlags = view.getUint16(localOff + 6, true);
    const lfCrc = view.getUint32(localOff + 14, true);
    const lfNameLen = view.getUint16(localOff + 26, true);
    const lfExtraLen = view.getUint16(localOff + 28, true);
    assert.equal(lfFlags & 0x0800, 0x0800, "UTF-8 flag bit 11 must be set in Local Header");
    assert.equal(lfCrc, cdCrc);

    const payloadStart = localOff + 30 + lfNameLen + lfExtraLen;
    const payload = zipBytes.subarray(payloadStart, payloadStart + cdUncompSize);
    assert.equal(crc32(payload), cdCrc, `CRC-32 mismatch for ${name}`);

    entries.push({ name, payload, crc: cdCrc, flags: cdFlags });
    ptr += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

// --- Existing v1 Tests (preserved verbatim for 100% backward compatibility) ---

test("parseJapaneseOrIsoDate normalizes Wareki and full-width ISO dates", () => {
  assert.equal(parseJapaneseOrIsoDate("令和8年11月19日").yyyymmdd, "20261119");
  assert.equal(parseJapaneseOrIsoDate("令和元年5月1日").yyyymmdd, "20190501");
  assert.equal(parseJapaneseOrIsoDate("R6.4.5").yyyymmdd, "20240405");
  assert.equal(parseJapaneseOrIsoDate("２０２６／１１／１９").yyyymmdd, "20261119");
});

test("normalizeDenchoRecord strips illegal chars, validates T-number, and emits YYYYMMDD_Partner_Amount", () => {
  const ok = normalizeDenchoRecord(
    "令和8年11月19日 株式会社テスト:商事 請求書 110,000円 T7000012050002.pdf",
  );
  assert.equal(ok.compliant, true);
  assert.equal(ok.date, "20261119");
  assert.equal(ok.amountYen, 110000);
  assert.equal(ok.invoiceId, "T7000012050002");
  assert.equal(ok.invoiceIdValid, true);
  assert.equal(ok.standardizedFilename, "20261119_株式会社テスト商事_110000円.pdf");

  const zeroYen = normalizeDenchoRecord("2026-10-31 さくらIT ０円");
  assert.equal(zeroYen.compliant, true);
  assert.equal(zeroYen.amountYen, 0);

  const missingDate = normalizeDenchoRecord("領収書_田中商店_8800円.pdf");
  assert.equal(missingDate.compliant, false);
  assert.deepEqual(missingDate.missingKeys, ["date"]);
});

test("normalizeDenchoBatch builds UTF-8 BOM NTA search index CSV and workflow auditor flags violations", () => {
  const batch = normalizeDenchoBatch(
    "2026-11-19 株式会社A 55,000円.pdf\n田中商店 1200円",
  );
  assert.equal(batch.totalCount, 2);
  assert.equal(batch.compliantCount, 1);
  assert.equal(batch.nonCompliantCount, 1);
  assert.ok(batch.indexCsvUtf8Bom.startsWith("\uFEFF取引年月日,取引先名,取引金額"));
  assert.ok(batch.indexCsvUtf8Bom.includes("20261119_株式会社A_55000円.pdf"));

  const badFlow = auditDenchoWorkflow({
    workflowText: "メールPDFは紙に印刷して電子ファイルは破棄。スキャン150dpi。",
  });
  const ids = new Set(badFlow.findings.map((f) => f.ruleId));
  assert.ok(ids.has("DENCHO-PAPER-ONLY-NG"));
  assert.ok(ids.has("DENCHO-TRUTH-MISSING"));
  assert.ok(ids.has("DENCHO-SEARCH-MISSING"));
  assert.ok(ids.has("DENCHO-SCANNER-DPI"));

  const goodFlow = auditDenchoWorkflow({
    workflowText: "YYYYMMDD_取引先名_金額.pdfと索引簿CSV・事務処理規程を備付け。",
    hasJimuKitei: true,
    hasSearchableNamingOrCsv: true,
  });
  assert.equal(goodFlow.complianceScore, 100);
  assert.equal(goodFlow.findingsCount, 0);
});

test("generateJimuShoriKitei renders complete internal control rules Markdown", () => {
  const md = generateJimuShoriKitei({
    companyName: "テスト株式会社",
    managerTitle: "経理部長",
    effectiveDate: "2026-11-19",
  });
  assert.ok(md.includes("電子取引データの訂正及び削除の防止に関する事務処理規程"));
  assert.ok(md.includes("事業者名: テスト株式会社"));
  assert.ok(md.includes("YYYYMMDD_取引先名_金額.pdf"));
});

// --- New Studio v2.0 Tests ---

test("buildStoredZip emits valid PKZIP headers, IEEE CRC-32, UTF-8 Japanese filenames, and exact payload bytes", () => {
  assert.equal(crc32(new TextEncoder().encode("123456789")), 0xcbf43926);

  const sampleBinary = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x00, 0xff, 0x42]);
  const sampleCsv = "\uFEFF取引年月日,取引先名,取引金額\n20261119,株式会社サンプル商事,110000\n";
  const sampleMd = "# 訂正削除防止規程\nテスト本文\n";

  const zipBytes = buildStoredZip([
    { name: "20261119_株式会社サンプル商事_110000.pdf", data: sampleBinary },
    { name: STUDIO_CSV_FILENAME, data: sampleCsv },
    { name: STUDIO_KITEI_FILENAME, data: sampleMd },
  ]);

  const parsed = readStoredZipEntries(zipBytes);
  assert.equal(parsed.length, 3);
  assert.equal(parsed[0].name, "20261119_株式会社サンプル商事_110000.pdf");
  assert.deepEqual(parsed[0].payload, sampleBinary);
  assert.equal(parsed[1].name, STUDIO_CSV_FILENAME);
  assert.deepEqual([...parsed[1].payload.subarray(0, 3)], [0xef, 0xbb, 0xbf]);
  assert.equal(TEXT_DECODER.decode(parsed[1].payload), sampleCsv);
  assert.equal(parsed[2].name, STUDIO_KITEI_FILENAME);
  assert.equal(TEXT_DECODER.decode(parsed[2].payload), sampleMd);

  // Cross-verify against Python stdlib zipfile.ZipFile (exact PKWARE interop check)
  const pyCheck = execFileSync(
    "python3",
    [
      "-c",
      [
        "import io, json, sys, zipfile",
        "data = sys.stdin.buffer.read()",
        "zf = zipfile.ZipFile(io.BytesIO(data), 'r')",
        "bad = zf.testzip()",
        "assert bad is None, f'corrupt entry: {bad}'",
        "out = {info.filename: {'flag': info.flag_bits, 'len': len(zf.read(info.filename))} for info in zf.infolist()}",
        "print(json.dumps(out, ensure_ascii=False))",
      ].join("; "),
    ],
    { input: Buffer.from(zipBytes) },
  ).toString("utf-8");

  const pyMeta = JSON.parse(pyCheck);
  assert.equal(pyMeta["20261119_株式会社サンプル商事_110000.pdf"].len, sampleBinary.length);
  assert.equal(pyMeta["20261119_株式会社サンプル商事_110000.pdf"].flag & 0x0800, 0x0800);
  assert.ok(pyMeta[STUDIO_CSV_FILENAME]);
  assert.ok(pyMeta[STUDIO_KITEI_FILENAME]);
});

test("extractTextFromPdfBytes decompresses /FlateDecode PDFs and extractDenchoFieldsFromText extracts all fields from generic filenames", async () => {
  const compressedPdf = await createSyntheticInvoicePdfBytes({
    issueDate: "令和8年11月19日",
    partnerName: "株式会社サンプル商事",
    recipientName: "合同会社ホライゾンラボ 御中",
    amountYen: 110000,
    invoiceId: "T7000012050002",
    compress: true,
  });

  const extraction = await extractTextFromPdfBytes(compressedPdf);
  assert.equal(extraction.isEncrypted, false);
  assert.equal(extraction.decompressedCount, 1);
  assert.ok(extraction.text.includes("株式会社サンプル商事"));
  assert.ok(extraction.text.includes("T7000012050002"));

  const fields = extractDenchoFieldsFromText(extraction, { filename: "invoice_001.pdf" });
  assert.equal(fields.date, "20261119");
  assert.equal(fields.partner, "株式会社サンプル商事");
  assert.equal(fields.amountYen, 110000);
  assert.equal(fields.invoiceId, "T7000012050002");
  assert.equal(fields.invoiceIdValid, true);
  assert.equal(fields.compliant, true);
  assert.equal(fields.primarySource, "pdf_text");
});

test("extractTextFromPdfBytes supports uncompressed Tj/TJ operators, ToUnicode CMap, and degrades safely on encrypted/scanned PDFs", async () => {
  // 1. Uncompressed ASCII/UTF-8 PDF with literal Tj & TJ array
  const uncompressedPdf = new TextEncoder().encode(
    [
      "%PDF-1.4",
      "1 0 obj << /Length 160 >>",
      "stream",
      "BT /F1 12 Tf",
      "0 700 Td (Invoice Date: 2026/11/08) Tj",
      "0 -20 Td [(Acme ) -200 (Cloud ) -180 (Services Inc.)] TJ",
      "0 -20 Td (Total Amount: ¥48,400) Tj",
      "0 -20 Td (Registration: T7000012050002) Tj",
      "ET",
      "endstream endobj",
      "%%EOF",
    ].join("\n"),
  );
  const res1 = await extractTextFromPdfBytes(uncompressedPdf);
  const f1 = extractDenchoFieldsFromText(res1, { filename: "download.pdf" });
  assert.equal(f1.date, "20261108");
  assert.equal(f1.partner, "AcmeCloudServicesInc");
  assert.equal(f1.amountYen, 48400);
  assert.equal(f1.invoiceId, "T7000012050002");
  assert.equal(f1.invoiceIdValid, true);

  // 2. ToUnicode CMap + hex glyph stream
  const cmapPdf = new TextEncoder().encode(
    [
      "%PDF-1.4",
      "1 0 obj << /Length 220 >>",
      "stream",
      "begincmap",
      "2 beginbfchar",
      "<0001> <682A>", // 株
      "<0002> <5F0F>", // 式
      "endbfchar",
      "1 beginbfrange",
      "<0003> <0004> [<4F1A> <793E>]", // 会 社
      "endbfrange",
      "endcmap",
      "endstream endobj",
      "2 0 obj << /Length 40 >>",
      "stream",
      "BT /F1 12 Tf <0001000200030004> Tj ET",
      "endstream endobj",
      "%%EOF",
    ].join("\n"),
  );
  const resCmap = await extractTextFromPdfBytes(cmapPdf);
  assert.ok(resCmap.text.includes("株式会社"));

  // 3. Encrypted PDF fails safely without throwing
  const encPdf = new TextEncoder().encode("%PDF-1.4\n1 0 obj << /Encrypt 2 0 R >> endobj\n%%EOF");
  const resEnc = await extractTextFromPdfBytes(encPdf);
  assert.equal(resEnc.isEncrypted, true);
  assert.equal(resEnc.text, "");

  // 4. Scanned image-only PDF flags isLikelyScanned safely
  const scanPdf = new TextEncoder().encode(
    "%PDF-1.4\n1 0 obj << /Subtype /Image /Filter /DCTDecode /Length 4 >>\nstream\n\xff\xd8\xff\xd9\nendstream endobj\n%%EOF",
  );
  const resScan = await extractTextFromPdfBytes(scanPdf);
  assert.equal(resScan.isLikelyScanned, true);
  assert.equal(resScan.text, "");
});

test("extractDenchoFieldsFromText prioritizes issue date over due date, grand total over subtotal/tax, and issuer over recipient", () => {
  const invoiceText = [
    "請求書",
    "株式会社クライアント 御中",
    "お支払期限：2026年12月31日",
    "発行日：R8.11.15",
    "小計：100,000円",
    "消費税：10,000円",
    "ご請求金額（税込）",
    "¥110,000-",
    "合同会社テストクラウド",
    "登録番号：T7000012050002",
  ].join("\n");

  const parsed = extractDenchoFieldsFromText(invoiceText, { filename: "領収書.pdf" });
  assert.equal(parsed.date, "20261115");
  assert.equal(parsed.partner, "合同会社テストクラウド");
  assert.equal(parsed.amountYen, 110000);
  assert.equal(parsed.invoiceId, "T7000012050002");
  assert.equal(parsed.invoiceIdValid, true);
  assert.equal(parsed.compliant, true);
});

test("formatDenchoFilename templates, collision suffixing, SHA-256 duplicate flagging, and buildDenchoZipPackage work end-to-end", async () => {
  const fCompact = formatDenchoFilename(
    { date: "20261119", partner: "株式会社サンプル商事", amountYen: 110000, invoiceId: "T7000012050002", extension: ".pdf" },
    { template: "compact_no_yen", includeTNumber: false },
  );
  assert.equal(fCompact.filename, "20261119_株式会社サンプル商事_110000.pdf");

  const fIsoWithT = formatDenchoFilename(
    { date: "20261119", partner: "株式会社サンプル商事", amountYen: 110000, invoiceId: "T7000012050002", extension: ".png" },
    { template: "iso_yen", includeTNumber: true },
  );
  assert.equal(fIsoWithT.filename, "2026-11-19_株式会社サンプル商事_110000円_T7000012050002.png");

  // Collision suffixing + SHA-256 duplicate detection
  const pdf1 = await createSyntheticInvoicePdfBytes({
    issueDate: "令和8年11月19日",
    partnerName: "株式会社サンプル商事",
    amountYen: 110000,
    invoiceId: "T7000012050002",
    compress: true,
  });
  const pdf2 = new Uint8Array(pdf1); // byte-identical duplicate
  const pdf3 = await createSyntheticInvoicePdfBytes({
    issueDate: "2026年11月19日",
    partnerName: "株式会社サンプル商事",
    amountYen: 110000,
    invoiceId: "T7000012050002",
    invoiceNumber: "INV-2026-9999", // different bytes -> NOT a byte duplicate, but SAME target filename!
    compress: true,
  });

  const rec1 = { ...(await analyzeUploadedFile({ name: "invoice_001.pdf", bytes: pdf1 })), bytes: pdf1 };
  const rec2 = { ...(await analyzeUploadedFile({ name: "download_copy.pdf", bytes: pdf2 })), bytes: pdf2 };
  const rec3 = { ...(await analyzeUploadedFile({ name: "invoice_003.pdf", bytes: pdf3 })), bytes: pdf3 };

  assert.equal(rec1.sha256, await computeSha256Hex(pdf1));
  assert.equal(rec1.sha256, rec2.sha256);
  assert.notEqual(rec1.sha256, rec3.sha256);

  const marked = resolveFilenameCollisions(markDuplicateRecords([rec1, rec2, rec3]));
  assert.equal(marked[0].isDuplicate, false);
  assert.equal(marked[0].hasDuplicatePeer, true);
  assert.equal(marked[1].isDuplicate, true);
  assert.equal(marked[1].duplicateOf, "invoice_001.pdf");
  assert.equal(marked[2].isDuplicate, false);

  assert.equal(marked[0].standardizedFilename, "20261119_株式会社サンプル商事_110000.pdf");
  assert.equal(marked[1].standardizedFilename, "20261119_株式会社サンプル商事_110000_2.pdf");
  assert.equal(marked[2].standardizedFilename, "20261119_株式会社サンプル商事_110000_3.pdf");

  // Full ZIP package including duplicates
  const fullPkg = buildDenchoZipPackage({
    records: marked,
    kiteiOptions: { companyName: "テスト合同会社", managerTitle: "代表社員", effectiveDate: "2026-11-19" },
    includeDuplicates: true,
  });
  const fullEntries = readStoredZipEntries(fullPkg.zipBytes);
  assert.equal(fullEntries.length, 5); // 3 PDFs + CSV + Kitei MD
  const csvEntry = fullEntries.find((e) => e.name === STUDIO_CSV_FILENAME);
  assert.ok(csvEntry);
  const csvText = TEXT_DECODER.decode(csvEntry.payload);
  assert.ok(csvText.startsWith("\uFEFF取引年月日,取引先名,取引金額"));
  assert.ok(csvText.includes(rec1.sha256));
  assert.ok(csvText.includes("重複（元: invoice_001.pdf）"));

  // ZIP package excluding byte-identical duplicates
  const dedupPkg = buildDenchoZipPackage({
    records: marked,
    includeDuplicates: false,
  });
  assert.equal(dedupPkg.excludedDuplicatesCount, 1);
  assert.equal(dedupPkg.binaryFileCount, 2);
  const dedupNames = readStoredZipEntries(dedupPkg.zipBytes).map((e) => e.name);
  assert.deepEqual(dedupNames, [
    "20261119_株式会社サンプル商事_110000.pdf",
    "20261119_株式会社サンプル商事_110000_2.pdf",
    STUDIO_CSV_FILENAME,
    STUDIO_KITEI_FILENAME,
  ]);
});
