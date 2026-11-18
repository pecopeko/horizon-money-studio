import {
  generateZengin120FromRows,
  parseZengin120,
  verifyBatchIdentifiers,
} from "./core/zengin-engine.mjs";

const SAMPLE_CSV = `0005,ﾐﾂﾋﾞｼﾕｰｴﾌｼﾞｴｲ,001,ﾎﾝﾃﾝ,1,1234567,株式会社テストサプライ,125000
0009,ﾐﾂｲｽﾐﾄﾓ,200,ｼﾝｼﾞﾕｸ,2,7654321,ヤマダ タロウ,48500
0001,ﾐｽﾞﾎ,005,ﾄｳｷﾖｳ,1,0098765,サトウ ハナコ（ぎょうせい企画）,32000`;

const reqNameInput = document.getElementById("reqNameInput");
const reqCodeInput = document.getElementById("reqCodeInput");
const transferDateInput = document.getElementById("transferDateInput");
const csvRowsInput = document.getElementById("csvRowsInput");
const generateZenginBtn = document.getElementById("generateZenginBtn");
const downloadZenginBtn = document.getElementById("downloadZenginBtn");
const loadSampleCsvBtn = document.getElementById("loadSampleCsvBtn");
const genSummary = document.getElementById("genSummary");
const zenginPreview = document.getElementById("zenginPreview");
const zenginRawInput = document.getElementById("zenginRawInput");
const auditZenginBtn = document.getElementById("auditZenginBtn");
const zenginAuditOutput = document.getElementById("zenginAuditOutput");
const idsInput = document.getElementById("idsInput");
const checkIdsBtn = document.getElementById("checkIdsBtn");
const idsTableBody = document.getElementById("idsTableBody");

let lastZenginContent = "";

function parseCsvRows(rawCsv) {
  return rawCsv
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const [bankCode, bankName, branchCode, branchName, accountType, accountNumber, recipientName, amount] =
        line.split(",").map((p) => (p ?? "").trim());
      return {
        bankCode,
        bankName,
        branchCode,
        branchName,
        accountType,
        accountNumber,
        recipientName,
        amount: Number(amount),
      };
    });
}

function runGenerate() {
  try {
    const rows = parseCsvRows(csvRowsInput.value);
    const out = generateZengin120FromRows(rows, {
      requesterName: reqNameInput.value,
      requesterCode: reqCodeInput.value,
      transferDateMMDD: transferDateInput.value,
    });
    lastZenginContent = out.content;
    zenginPreview.textContent = out.content;
    zenginRawInput.value = out.content;
    genSummary.className = "status-box is-ok";
    genSummary.textContent = `生成完了: ${out.dataCount} 件 / 合計金額 ${out.totalAmountYen.toLocaleString()} 円 / 全 ${out.lineCount} 行 (各120バイト厳格チェック準備済)`;
    runAuditZengin();
  } catch (err) {
    genSummary.className = "status-box is-err";
    genSummary.textContent = `生成エラー: ${err?.message || err}`;
  }
}

function runAuditZengin() {
  const res = parseZengin120(zenginRawInput.value);
  if (res.valid) {
    zenginAuditOutput.className = "status-box is-ok";
    zenginAuditOutput.textContent = `合格 (120バイト構文・トレーラ検算一致): 明細 ${res.rows.length} 件 / 合計 ${res.computedTotal.toLocaleString()} 円`;
  } else {
    zenginAuditOutput.className = "status-box is-err";
    zenginAuditOutput.textContent = `エラー ${res.errors.length} 件: ` + res.errors.map((e) => `${e.line}行目[${e.code}] ${e.message}`).join(" | ");
  }
}

function runCheckIds() {
  const res = verifyBatchIdentifiers(idsInput.value);
  idsTableBody.replaceChildren();
  for (const item of res.items) {
    const tr = document.createElement("tr");
    for (const val of [
      String(item.line),
      item.kind,
      item.normalized,
      item.valid ? "VALID" : "INVALID",
      item.reason,
    ]) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }
    idsTableBody.appendChild(tr);
  }
}

loadSampleCsvBtn.addEventListener("click", () => {
  csvRowsInput.value = SAMPLE_CSV;
  runGenerate();
});
generateZenginBtn.addEventListener("click", runGenerate);
auditZenginBtn.addEventListener("click", runAuditZengin);
checkIdsBtn.addEventListener("click", runCheckIds);

downloadZenginBtn.addEventListener("click", () => {
  if (!lastZenginContent) runGenerate();
  const blob = new Blob([lastZenginContent], { type: "text/plain;charset=ascii" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sogo-furikomi-120b.txt";
  a.click();
  URL.revokeObjectURL(url);
});

csvRowsInput.value = SAMPLE_CSV;
runGenerate();
runCheckIds();
