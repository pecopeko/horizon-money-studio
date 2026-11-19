import test from "node:test";
import assert from "node:assert/strict";
import {
  BANK_PRESETS,
  LEGAL_ENTITY_ABBREVIATIONS,
  TRANSFER_TYPES,
  decodeZenginBytes,
  diagnoseAndRepairZenginFile,
  encodeZenginShiftJis,
  generateZengin120FromRows,
  parseTransferCsv,
  parseZengin120,
  toZenginHalfWidth,
  validateHeader,
  validateTransferRows,
  verifyBatchIdentifiers,
  verifyCorporateNumberMod9,
  verifyQualifiedInvoiceId,
} from "../docs/core/zengin-engine.mjs";

test("verifies valid and mutated NTA Qualified Invoice IDs and Corporate Numbers", () => {
  // NTA sample Corporate ID 7000012050002 -> check digit 7, rest 000012050002
  const validInv = verifyQualifiedInvoiceId("Ｔ７００００１２０５０００２");
  assert.equal(validInv.valid, true);
  assert.equal(validInv.normalized, "T7000012050002");

  const mutatedInv = verifyQualifiedInvoiceId("T8000012050002");
  assert.equal(mutatedInv.valid, false);
  assert.equal(mutatedInv.expectedCheckDigit, 7);

  const validCorp = verifyCorporateNumberMod9("70000-1205-0002");
  assert.equal(validCorp.valid, true);
});

test("verifyBatchIdentifiers reports valid vs invalid counts cleanly", () => {
  const res = verifyBatchIdentifiers("T7000012050002\nT9000012050002\n12345");
  assert.equal(res.total, 3);
  assert.equal(res.validCount, 1);
  assert.equal(res.invalidCount, 2);
});

test("converts Hiragana, positional corporate prefix, small kana, and voiced marks to Zengin format", () => {
  const conv = toZenginHalfWidth("株式会社ぎょうせいきかく　ﾔﾏﾀﾞ ｼｮｯﾌﾟ", { maxLength: 30 });
  assert.equal(conv.isLegal, true);
  assert.equal(conv.hasErrors, false);
  assert.equal(conv.zenginText, "ｶ)ｷﾞﾖｳｾｲｷｶｸ ﾔﾏﾀﾞ ｼﾖﾂﾌﾟ");
  // Confirm dakuten counts as 1 byte in Zengin fixed width
  assert.equal(conv.byteLength, "ｶ)ｷﾞﾖｳｾｲｷｶｸ ﾔﾏﾀﾞ ｼﾖﾂﾌﾟ".length);
});

test("flags unsupported full-width Kanji characters cleanly via invalidChars and hasErrors", () => {
  const res = toZenginHalfWidth("株式会社田中商事");
  assert.equal(res.hasErrors, true);
  assert.equal(res.isLegal, false);
  assert.ok(res.unsupportedChars.includes("田"));
  assert.deepEqual(res.invalidChars, ["田", "中", "商", "事"]);
  assert.equal(res.zenginText, "ｶ)");
});

test("applies official Zengin positional corporate abbreviations across 25+ entity types", () => {
  assert.ok(LEGAL_ENTITY_ABBREVIATIONS.length >= 25);

  // Prefix / Suffix / Infix for 株式会社
  assert.equal(toZenginHalfWidth("株式会社ホライゾン").zenginText, "ｶ)ﾎﾗｲｿﾞﾝ");
  assert.equal(toZenginHalfWidth("ホライゾン株式会社").zenginText, "ﾎﾗｲｿﾞﾝ(ｶ");
  assert.equal(toZenginHalfWidth("ホライゾン株式会社トウキョウ").zenginText, "ﾎﾗｲｿﾞﾝ(ｶ)ﾄｳｷﾖｳ");
  assert.equal(toZenginHalfWidth("株式会社 テスト").zenginText, "ｶ)ﾃｽﾄ");
  assert.equal(toZenginHalfWidth("テスト 株式会社").zenginText, "ﾃｽﾄ(ｶ");

  // Legal entity coverage
  assert.equal(toZenginHalfWidth("有限会社サクラ").zenginText, "ﾕ)ｻｸﾗ");
  assert.equal(toZenginHalfWidth("サクラ有限会社").zenginText, "ｻｸﾗ(ﾕ");
  assert.equal(toZenginHalfWidth("合同会社アオバ").zenginText, "ﾄﾞ)ｱｵﾊﾞ");
  assert.equal(toZenginHalfWidth("アオバ合同会社").zenginText, "ｱｵﾊﾞ(ﾄﾞ");
  assert.equal(toZenginHalfWidth("合名会社アルファ").zenginText, "ﾒ)ｱﾙﾌｱ");
  assert.equal(toZenginHalfWidth("合資会社ベータ").zenginText, "ｼ)ﾍﾞ-ﾀ");
  assert.equal(toZenginHalfWidth("医療法人ヒカリ").zenginText, "ｲ)ﾋｶﾘ");
  assert.equal(toZenginHalfWidth("一般社団法人ミライ").zenginText, "ｼﾔ)ﾐﾗｲ");
  assert.equal(toZenginHalfWidth("一般財団法人キボウ").zenginText, "ｻﾞｲ)ｷﾎﾞｳ");
  assert.equal(toZenginHalfWidth("特定非営利活動法人エコ").zenginText, "ﾄｸﾋ)ｴｺ");
  assert.equal(toZenginHalfWidth("NPO法人エコ").zenginText, "ﾄｸﾋ)ｴｺ");
  assert.equal(toZenginHalfWidth("社会福祉法人アイ").zenginText, "ﾌｸ)ｱｲ");
  assert.equal(toZenginHalfWidth("学校法人ガクエン").zenginText, "ｶﾞｸ)ｶﾞｸｴﾝ");
  assert.equal(toZenginHalfWidth("宗教法人テラ").zenginText, "ｼﾕｳ)ﾃﾗ");
  assert.equal(toZenginHalfWidth("税理士法人タナカ").zenginText, "ｾﾞｲ)ﾀﾅｶ");
  assert.equal(toZenginHalfWidth("弁護士法人サトウ").zenginText, "ﾍﾞﾝ)ｻﾄｳ");
  assert.equal(toZenginHalfWidth("司法書士法人スズキ").zenginText, "ｼﾎ)ｽｽﾞｷ");
  assert.equal(toZenginHalfWidth("監査法人アオゾラ").zenginText, "ｶﾝｻ)ｱｵｿﾞﾗ");
  assert.equal(toZenginHalfWidth("テスト組合").zenginText, "ﾃｽﾄ(ｸﾐ");
  assert.equal(toZenginHalfWidth("テスト営業所").zenginText, "ﾃｽﾄ(ｴｲ");
  assert.equal(toZenginHalfWidth("テスト支店").zenginText, "ﾃｽﾄ(ｼﾃﾝ");
});

test("dakuten-safe 30-byte truncation never severs voiced or semi-voiced marks", () => {
  // 29 'ｱ' + 'ガ' ('ｶﾞ') => 31 bytes; byte 30 is 'ｶ', byte 31 is 'ﾞ' -> must drop 'ｶ' too => 29 bytes!
  const voicedBoundary = "ｱ".repeat(29) + "ガ";
  const resVoiced = toZenginHalfWidth(voicedBoundary, { maxLength: 30 });
  assert.equal(resVoiced.truncated, true);
  assert.equal(resVoiced.dakutenSafeAdjusted, true);
  assert.equal(resVoiced.byteLength, 29);
  assert.equal(resVoiced.zenginText, "ｱ".repeat(29));

  // Handakuten boundary: 29 'ｱ' + 'パ' ('ﾊﾟ') -> 29 bytes
  const handakutenBoundary = "ｱ".repeat(29) + "パ";
  const resHanda = toZenginHalfWidth(handakutenBoundary, { maxLength: 30 });
  assert.equal(resHanda.dakutenSafeAdjusted, true);
  assert.equal(resHanda.byteLength, 29);

  // Exact fit: 28 'ｱ' + 'ガ' ('ｶﾞ') => 30 bytes -> keep full 'ｶﾞ'
  const exactFit = "ｱ".repeat(28) + "ガ";
  const resExact = toZenginHalfWidth(exactFit, { maxLength: 30 });
  assert.equal(resExact.truncated, false);
  assert.equal(resExact.dakutenSafeAdjusted, false);
  assert.equal(resExact.byteLength, 30);
  assert.equal(resExact.zenginText, "ｱ".repeat(28) + "ｶﾞ");

  // Verify inside 120-byte Zengin record: byte 80 (pos 80, index 79) becomes space (0x20), never severed 'ｶ'
  const gen = generateZengin120FromRows([{ recipientName: voicedBoundary, amount: 1000 }]);
  const dataRecord = gen.content.split("\r\n")[1];
  const recipientField = dataRecord.slice(50, 80);
  assert.equal(recipientField, "ｱ".repeat(29) + " ");
  assert.equal(encodeZenginShiftJis(recipientField).length, 30);
});

test("encodeZenginShiftJis emits exact CP932 single bytes (0xB1 for ｱ) and exact 120-byte records", () => {
  const bytes = encodeZenginShiftJis("ｱｲｳｶﾞﾊﾟｦA0-¥");
  assert.deepEqual(
    Array.from(bytes),
    [0xb1, 0xb2, 0xb3, 0xb6, 0xde, 0xca, 0xdf, 0xa6, 0x41, 0x30, 0x2d, 0x5c],
  );

  const withEof = encodeZenginShiftJis("ｱ", { includeEof: true });
  assert.deepEqual(Array.from(withEof), [0xb1, 0x1a]);

  assert.throws(() => encodeZenginShiftJis("田中"), /Shift-JIS/);
});

test("decodeZenginBytes accurately detects Shift-JIS (even tricky ﾅｶ pairs), UTF-8, BOM, and EOF", () => {
  const gen = generateZengin120FromRows([{ recipientName: "ﾅｶ", amount: 5000 }], {
    requesterName: "ﾅｶ",
    includeEof: true,
  });
  // Verify exact raw byte length: 4 records * (120 + 2 CRLF) + 1 EOF = 489 bytes!
  assert.equal(gen.bytes.length, 4 * 122 + 1);
  assert.equal(gen.bytes[gen.bytes.length - 1], 0x1a);

  const decodedSjis = decodeZenginBytes(gen.bytes);
  assert.equal(decodedSjis.encoding, "shift_jis");
  assert.equal(decodedSjis.hasEofMarker, true);
  assert.equal(decodedSjis.lineEnding, "CRLF");
  assert.equal(decodedSjis.text, gen.content);

  // UTF-8 with BOM
  const utf8Body = new TextEncoder().encode(gen.content);
  const withBom = new Uint8Array(3 + utf8Body.length);
  withBom.set([0xef, 0xbb, 0xbf], 0);
  withBom.set(utf8Body, 3);
  const decodedBom = decodeZenginBytes(withBom);
  assert.equal(decodedBom.encoding, "utf-8-bom");
  assert.equal(decodedBom.hasBom, true);
});

test("generates strict 120-byte Shift-JIS Zengin Sogo Furikomi file and round-trip parses cleanly", () => {
  const gen = generateZengin120FromRows(
    [
      {
        bankCode: "0005",
        bankName: "三菱UFJ",
        branchCode: "001",
        branchName: "本店",
        accountType: "1",
        accountNumber: "123456",
        recipientName: "株式会社テストサプライ",
        amount: 125000,
      },
      {
        bankCode: "0009",
        bankName: "三井住友",
        branchCode: "200",
        branchName: "新宿",
        accountType: "2",
        accountNumber: "7654321",
        recipientName: "ヤマダ タロウ",
        amount: 48500,
      },
    ],
    { requesterName: "株式会社ホライゾン", transferDateMMDD: "1125" },
  );

  const lines = gen.content.slice(0, -2).split("\r\n");
  assert.equal(lines.length, 5);
  for (const line of lines) {
    assert.equal(line.length, 120);
    assert.equal(encodeZenginShiftJis(line).length, 120);
  }
  assert.equal(gen.allRecords120Bytes, true);
  assert.equal(gen.bytes.length, 5 * 122);
  assert.equal(gen.totalAmountYen, 173500);

  // Round-trip both string and raw Shift-JIS Uint8Array
  const parsedStr = parseZengin120(gen.content);
  assert.equal(parsedStr.valid, true);
  assert.equal(parsedStr.rows.length, 2);
  assert.equal(parsedStr.computedTotal, 173500);

  const parsedBin = parseZengin120(gen.bytes);
  assert.equal(parsedBin.valid, true);
  assert.equal(parsedBin.rows[0].recipientName, "ｶ)ﾃｽﾄｻﾌﾟﾗｲ");
});

test("supports Transfer Types 21/11/12, Bank Presets, Pos 112 transferDesignation/feeFlag, and Pos 113 auto EDI Y", () => {
  assert.ok(TRANSFER_TYPES["21"] && TRANSFER_TYPES["11"] && TRANSFER_TYPES["12"]);
  for (const id of ["standard", "mufg", "smbc", "mizuho", "rakuten", "sbi", "gmo"]) {
    assert.ok(BANK_PRESETS[id], `Missing bank preset ${id}`);
  }

  // 給与振込 (11) with SMBC preset (CRLF + EOF 0x1A + clearingHouse 0000) and EDI info -> Pos 113 = "Y"
  const salaryGen = generateZengin120FromRows(
    [
      {
        bankCode: "0009",
        branchCode: "200",
        accountType: "1",
        accountNumber: "1234567",
        recipientName: "ヤマダ タロウ",
        amount: 320000,
        ediInfo: "EMP-2026-001",
        transferDesignation: "7",
      },
      {
        bankCode: "0005",
        branchCode: "001",
        accountType: "1",
        accountNumber: "7654321",
        recipientName: "サトウ ハナコ",
        amount: 280000,
        ediInfo: "",
        feeFlag: "8", // backward-compatible option
      },
    ],
    {
      preset: "smbc",
      transferType: "11",
      requesterName: "株式会社ホライゾン",
      transferDateMMDD: "1125",
    },
  );

  assert.equal(salaryGen.bytes[salaryGen.bytes.length - 1], 0x1a);
  const salaryLines = salaryGen.content.slice(0, -2).split("\r\n");
  assert.equal(salaryLines[0].slice(1, 3), "11");
  // Pos 39-42 (index 38..42) clearingHouseCode = "0000"
  assert.equal(salaryLines[1].slice(38, 42), "0000");
  // Pos 112 (index 111) = "7", Pos 113 (index 112) = "Y" because ediInfo is non-empty!
  assert.equal(salaryLines[1][111], "7");
  assert.equal(salaryLines[1][112], "Y");
  // Row 2: Pos 112 = "8" (from feeFlag), Pos 113 = " " (ediInfo empty!)
  assert.equal(salaryLines[2][111], "8");
  assert.equal(salaryLines[2][112], " ");

  // 賞与振込 (12) with Mizuho preset (lineEnding: "NONE" continuous 120B records)
  const bonusGen = generateZengin120FromRows(
    [{ bankCode: "0001", branchCode: "001", accountNumber: "1111111", recipientName: "スズキ イチロウ", amount: 500000 }],
    { preset: "mizuho", transferType: "12" },
  );
  assert.equal(bonusGen.lineEnding, "NONE");
  assert.equal(bonusGen.bytes.length, 4 * 120); // Strictly 480 raw bytes, zero CRLF!
  const parsedBonus = parseZengin120(bonusGen.bytes);
  assert.equal(parsedBonus.valid, true);
  assert.equal(parsedBonus.header.typeCode, "12");
  assert.equal(parsedBonus.computedTotal, 500000);
});

test("parseTransferCsv handles RFC-4180 quotes, Yen/commas, Excel leading-zero loss, and accounting headers", () => {
  const dirtyCsv = [
    "振込先金融機関コード,銀行名,支店コード,支店名,預金種目,口座番号,取引先名,振込金額,EDI情報,T番号",
    '5,三菱UFJ,1,本店,普通,12345,"株式会社テストサプライ","¥125,000","INV-001",T7000012050002',
    '9,,200,ｼﾝｼﾞﾕｸ,当座,7654321,"ヤマダ, タロウ","48,500円","",T8000012050002',
  ].join("\r\n");

  const parsed = parseTransferCsv(dirtyCsv);
  assert.equal(parsed.hasHeader, true);
  assert.equal(parsed.detectedPreset, "freee");
  assert.equal(parsed.rows.length, 2);

  assert.equal(parsed.rows[0].bankCode, "0005");
  assert.equal(parsed.rows[0].branchCode, "001");
  assert.equal(parsed.rows[0].accountType, "1");
  assert.equal(parsed.rows[0].accountNumber, "0012345");
  assert.equal(parsed.rows[0].amount, 125000);
  assert.equal(parsed.rows[0].ediInfo, "INV-001");

  assert.equal(parsed.rows[1].bankCode, "0009");
  assert.equal(parsed.rows[1].bankName, "ﾐﾂｲｽﾐﾄﾓ"); // auto-filled from MAJOR_BANKS
  assert.equal(parsed.rows[1].accountType, "2");
  assert.equal(parsed.rows[1].recipientName, "ヤマダ, タロウ");
  assert.equal(parsed.rows[1].amount, 48500);

  // Row validation catches invalid Mod-9 T-number on row 2
  const validation = validateTransferRows(parsed.rows);
  assert.equal(validation.rows[0].valid, true);
  assert.equal(validation.rows[1].valid, false);
  assert.ok(validation.rows[1].fieldErrors.invoiceId);
});

test("diagnoseAndRepairZenginFile repairs UTF-8 BOM, full-width spaces, wrong length, bad trailer sum, and missing End record", () => {
  // Build a valid base, then deliberately break EVERY common bank-rejection factor
  const base = generateZengin120FromRows(
    [
      {
        bankCode: "0005",
        bankName: "ﾐﾂﾋﾞｼUFJ",
        branchCode: "001",
        branchName: "ﾎﾝﾃﾝ",
        accountType: "1",
        accountNumber: "1234567",
        recipientName: "ﾔﾏﾀﾞ ﾀﾛｳ",
        amount: 100000,
        ediInfo: "INV2026",
      },
    ],
    { requesterName: "ｶ)ﾎﾗｲｿﾞﾝ", transferDateMMDD: "1125" },
  );

  const lines = base.content.trimEnd().split("\r\n");
  // Break line 2: replace recipient with full-width kana & space, blank Pos 113 'Y', trim trailing spaces
  const brokenData =
    lines[1].slice(0, 50) +
    "ヤマダ　タロウ".padEnd(30, " ") +
    lines[1].slice(80, 112) +
    " " +
    ""; // missing trailing spaces (length 113, not 120!)
  // Break trailer: wrong count (000099) & wrong sum (000000999999)
  const brokenTrailer = "8000099000000999999" + " ".repeat(101);
  // Drop End record (9...) and use LF-only + UTF-8 BOM!
  const brokenUtf8Text = "\uFEFF" + [lines[0], brokenData, brokenTrailer].join("\n") + "\n";
  const brokenBytes = new TextEncoder().encode(brokenUtf8Text);

  const repaired = diagnoseAndRepairZenginFile(brokenBytes, { preset: "mufg" });
  assert.equal(repaired.source.encoding, "utf-8-bom");
  assert.equal(repaired.source.hasBom, true);
  assert.equal(repaired.repaired.ok, true);
  assert.equal(repaired.repaired.allRecords120Bytes, true);
  assert.equal(repaired.repaired.dataCount, 1);
  assert.equal(repaired.repaired.totalAmountYen, 100000);
  assert.equal(repaired.repaired.bytes.length, 4 * 122); // Header + Data + Trailer + End, each 120 + CRLF!
  assert.ok(repaired.diagnostics.some((d) => d.code === "UTF8_BOM"));
  assert.ok(repaired.diagnostics.some((d) => d.code === "COUNT_MISMATCH"));
  assert.ok(repaired.diagnostics.some((d) => d.code === "AMOUNT_MISMATCH"));
  assert.ok(repaired.diagnostics.some((d) => d.code === "MISSING_END"));
  assert.ok(repaired.diagnostics.some((d) => d.code === "EDI_INDICATOR_REPAIRED"));

  const finalAudit = parseZengin120(repaired.repaired.bytes);
  assert.equal(finalAudit.valid, true);
  assert.equal(finalAudit.rows[0].recipientName, "ﾔﾏﾀﾞ ﾀﾛｳ");
  assert.equal(finalAudit.rows[0].ediIndicator, "Y");
});

test("parseZengin120 catches trailer total amount mismatch and wrong line length", () => {
  const gen = generateZengin120FromRows([{ recipientName: "ﾀﾅｶ", amount: 10000 }]);
  const corrupted = gen.content.replace("8000001000000010000", "8000001000000099999");
  const parsed = parseZengin120(corrupted);
  assert.equal(parsed.valid, false);
  assert.ok(parsed.errors.some((e) => e.code === "AMOUNT_MISMATCH"));

  const badLen = parseZengin120("1SHORTLINE\r\n");
  assert.equal(badLen.valid, false);
  assert.ok(badLen.errors.some((e) => e.code === "LEN_NOT_120"));
});

test("promotes Hiragana small vowels and handakuten accurately", () => {
  const res = toZenginHalfWidth("ぱぴぷぺぽ　ぁぃぅぇぉゃゅょっ", { maxLength: 40 });
  assert.equal(res.zenginText, "ﾊﾟﾋﾟﾌﾟﾍﾟﾎﾟ ｱｲｳｴｵﾔﾕﾖﾂ");
  assert.equal(res.isLegal, true);
});

test("rejects negative or non-integer transfer amount and strict kanji in Zengin generator", () => {
  assert.throws(
    () => generateZengin120FromRows([{ recipientName: "ｻﾄｳ", amount: -100 }]),
    /0以上の整数/,
  );
  assert.throws(
    () => generateZengin120FromRows([{ recipientName: "ｻﾄｳ", amount: 12.5 }]),
    /0以上の整数/,
  );
  assert.throws(
    () => generateZengin120FromRows([{ recipientName: "株式会社田中商事", amount: 10000 }], { strict: true }),
    /全銀不可文字/,
  );
  const headerErr = validateHeader({ requesterName: "株式会社山田", transferDateMMDD: "1399" });
  assert.equal(headerErr.valid, false);
  assert.ok(headerErr.errors.length >= 2);
});

test("diagnoseAndRepairZenginFile surfaces unrepairable Kanji as blockingErrors instead of silently deleting", () => {
  const base = generateZengin120FromRows([{ recipientName: "ﾔﾏﾀﾞ ﾀﾛｳ", amount: 50000 }]);
  const lines = base.content.trimEnd().split("\r\n");
  const kanjiDataLine = lines[1].slice(0, 50) + "株式会社田中商事".padEnd(30, " ") + lines[1].slice(80);
  const broken = [lines[0], kanjiDataLine, lines[2], lines[3]].join("\r\n") + "\r\n";

  const result = diagnoseAndRepairZenginFile(broken, { preset: "mufg" });
  assert.equal(result.repaired.ok, false);
  assert.ok(result.blockingErrors.some((e) => e.code === "UNSUPPORTED_KANJI"));
  assert.ok(result.blockingErrors[0].invalidChars.includes("田"));
});

test("parseTransferCsv supports Excel TSV paste and MoneyForward / Yayoi headers", () => {
  const tsv = [
    "銀行コード\t支店コード\t預金種目\t口座番号\t口座名義カナ\t支払金額",
    "36\t201\t普通\t98765\tｻﾄｳ ﾊﾅｺ\t¥32,000",
  ].join("\r\n");
  const parsed = parseTransferCsv(tsv);
  assert.equal(parsed.delimiter, "\t");
  assert.equal(parsed.detectedPreset, "moneyforward");
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.rows[0].bankCode, "0036");
  assert.equal(parsed.rows[0].bankName, "ﾗｸﾃﾝ");
  assert.equal(parsed.rows[0].accountNumber, "0098765");
  assert.equal(parsed.rows[0].amount, 32000);
});

test("encodeZenginShiftJis round-trips cleanly through TextDecoder('shift_jis') across all legal Zengin characters", () => {
  const sample = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ -.()/,｢｣";
  const bytes = encodeZenginShiftJis(sample);
  assert.equal(bytes.length, sample.length);
  const decoded = new TextDecoder("shift_jis").decode(bytes);
  assert.equal(decoded, sample);
});
