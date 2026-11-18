import test from "node:test";
import assert from "node:assert/strict";
import {
  generateZengin120FromRows,
  parseZengin120,
  toZenginHalfWidth,
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

test("converts Hiragana, corporate symbols, small kana, and voiced marks to Zengin format", () => {
  const conv = toZenginHalfWidth("株式会社ぎょうせいきかく　ﾔﾏﾀﾞ ｼｮｯﾌﾟ", { maxLength: 30 });
  assert.equal(conv.isLegal, true);
  assert.equal(conv.zenginText, "(ｶ)ｷﾞﾖｳｾｲｷｶｸ ﾔﾏﾀﾞ ｼﾖﾂﾌﾟ");
  // Confirm dakuten counts as 1 char in Zengin fixed width
  assert.equal(conv.byteLength, "(ｶ)ｷﾞﾖｳｾｲｷｶｸ ﾔﾏﾀﾞ ｼﾖﾂﾌﾟ".length);
});

test("flags unsupported full-width Kanji characters when converting", () => {
  const res = toZenginHalfWidth("株式会社田中商事");
  assert.ok(res.unsupportedChars.includes("田"));
  assert.equal(res.zenginText, "(ｶ)");
});

test("generates strict 120-byte Zengin Sogo Furikomi file and round-trip parses cleanly", () => {
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
  }
  assert.equal(gen.totalAmountYen, 173500);

  const parsed = parseZengin120(gen.content);
  assert.equal(parsed.valid, true);
  assert.equal(parsed.rows.length, 2);
  assert.equal(parsed.computedTotal, 173500);
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

test("rejects negative or non-integer transfer amount in Zengin generator", () => {
  assert.throws(
    () => generateZengin120FromRows([{ recipientName: "ｻﾄｳ", amount: -100 }]),
    /0以上の整数/,
  );
  assert.throws(
    () => generateZengin120FromRows([{ recipientName: "ｻﾄｳ", amount: 12.5 }]),
    /0以上の整数/,
  );
});
