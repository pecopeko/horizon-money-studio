import {
  auditJapaneseAdCopy,
  batchAuditAdCopy,
  buildAuditCertificateMarkdown,
} from "./core/yakki-engine.mjs";

const PRESETS = {
  yakki:
    "このサプリを飲むだけで糖尿病が完治し、シミが完全に消えます。さらに内臓脂肪が溶けて副作用は一切なし！",
  keihyo:
    "口コミ満足度No.1！通常9,800円が永久500円！絶対に失敗しない奇跡の美容液です。",
  stema:
    "企業様から新発売コスメを商品提供いただきました！自腹購入級のお気に入りなのでぜひ使ってみてください。",
  clean:
    "#PR 株式会社テスト提供 / 保湿成分配合で肌にうるおいを与え、乾燥による小じわを目立たなくします（効能評価試験済）。",
};

const copyInput = document.getElementById("copyInput");
const runAuditBtn = document.getElementById("runAuditBtn");
const downloadReportBtn = document.getElementById("downloadReportBtn");
const clearInputBtn = document.getElementById("clearInputBtn");
const riskLevelPill = document.getElementById("riskLevelPill");
const scoreTotalVal = document.getElementById("scoreTotalVal");
const predictedLabelVal = document.getElementById("predictedLabelVal");
const breakdownVal = document.getElementById("breakdownVal");
const highlightedText = document.getElementById("highlightedText");
const rewriteHint = document.getElementById("rewriteHint");
const findingsTableBody = document.getElementById("findingsTableBody");
const batchInput = document.getElementById("batchInput");
const runBatchBtn = document.getElementById("runBatchBtn");
const batchSummary = document.getElementById("batchSummary");

let lastAudit = null;

function renderHighlighted(text, findings) {
  highlightedText.replaceChildren();
  if (!text) return;
  if (!findings.length) {
    highlightedText.textContent = text;
    return;
  }
  let cursor = 0;
  for (const f of findings) {
    if (f.start < cursor) continue;
    if (f.start > cursor) {
      highlightedText.appendChild(document.createTextNode(text.slice(cursor, f.start)));
    }
    const mark = document.createElement("mark");
    mark.className = "hl-mark";
    mark.textContent = text.slice(f.start, f.end);
    mark.title = `${f.law}: ${f.ruleName}`;
    highlightedText.appendChild(mark);
    cursor = f.end;
  }
  if (cursor < text.length) {
    highlightedText.appendChild(document.createTextNode(text.slice(cursor)));
  }
}

function executeAudit() {
  const raw = copyInput.value;
  const res = auditJapaneseAdCopy(raw);
  lastAudit = res;

  riskLevelPill.textContent = `${res.riskLevel} (${res.overallRiskScore} / 100)`;
  riskLevelPill.className = "risk-pill";
  if (res.overallRiskScore >= 40) riskLevelPill.classList.add("is-high");
  else if (res.overallRiskScore >= 20) riskLevelPill.classList.add("is-med");

  scoreTotalVal.textContent = `${res.overallRiskScore} / 100`;
  predictedLabelVal.textContent = res.predictedLabel;
  breakdownVal.textContent = `${res.categoryCounts.yakki_medical_claim} / ${res.categoryCounts.keihyo_exaggerated_no1} / ${res.categoryCounts.stealth_marketing_unlabeled}`;
  rewriteHint.textContent = res.suggestedRewriteHint;

  renderHighlighted(raw, res.findings);

  findingsTableBody.replaceChildren();
  if (!res.findings.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "muted-cell";
    td.textContent = "NGパターンは検出されませんでした。";
    tr.appendChild(td);
    findingsTableBody.appendChild(tr);
    return;
  }

  for (const f of res.findings) {
    const tr = document.createElement("tr");
    for (const val of [f.id, f.law, f.matchedText, `+${f.severity}`, f.suggestion]) {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    }
    findingsTableBody.appendChild(tr);
  }
}

function executeBatch() {
  const lines = batchInput.value.split(/\r?\n/).filter((l) => l.trim());
  const batch = batchAuditAdCopy(lines);
  batchSummary.replaceChildren();

  const summaryP = document.createElement("p");
  summaryP.textContent = `合計 ${batch.totalRows} 行：要修正 ${batch.flaggedRows} 行 / 適法目安 ${batch.compliantRows} 行`;
  batchSummary.appendChild(summaryP);

  const ul = document.createElement("ul");
  for (const row of batch.results) {
    const li = document.createElement("li");
    li.textContent = `[${row.id}] ${row.riskLevel} (${row.overallRiskScore}点 / ${row.predictedLabel}): ${row.preview}`;
    ul.appendChild(li);
  }
  batchSummary.appendChild(ul);
}

for (const btn of document.querySelectorAll("[data-preset]")) {
  btn.addEventListener("click", () => {
    const key = btn.getAttribute("data-preset");
    if (key && PRESETS[key]) {
      copyInput.value = PRESETS[key];
      executeAudit();
    }
  });
}

runAuditBtn.addEventListener("click", executeAudit);
runBatchBtn.addEventListener("click", executeBatch);
clearInputBtn.addEventListener("click", () => {
  copyInput.value = "";
  executeAudit();
});

downloadReportBtn.addEventListener("click", () => {
  if (!lastAudit) executeAudit();
  const md = buildAuditCertificateMarkdown(lastAudit);
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "yakkigate-audit-report.md";
  a.click();
  URL.revokeObjectURL(url);
});

copyInput.value = PRESETS.yakki;
executeAudit();
executeBatch();
