import test from "node:test";
import assert from "node:assert/strict";
import {
  auditDenchoWorkflow,
  generateJimuShoriKitei,
  normalizeDenchoBatch,
  normalizeDenchoRecord,
  parseJapaneseOrIsoDate,
} from "../docs/core/dencho-engine.mjs";

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
