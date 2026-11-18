import {
  auditDenchoWorkflow,
  generateJimuShoriKitei,
  normalizeDenchoBatch,
} from "./core/dencho-engine.mjs";

const SAMPLE_BATCH = `令和8年11月19日 株式会社サンプル商事 請求書 110,000円 T7000012050002.pdf
R6.4.5/株式会社クラウド保守/¥55,000.pdf
2026年10月31日 さくらITサービス ０円（無料枠調整）
領収書_田中商店_8800円.jpg`;

const RISKY_WORKFLOW =
  "メール添付PDFは紙に印刷してバインダー保存し電子ファイルは破棄しています。スキャン時は150dpiで取り込み。";

const SAFE_WORKFLOW =
  "電子取引PDFはYYYYMMDD_取引先名_金額.pdfで命名のうえ事務処理規程を備付けし、検索用索引簿CSVとともにNASへ7年保存しています。";

const batchInput = document.getElementById("batchInput");
const batchSummaryBox = document.getElementById("batchSummaryBox");
const batchTableBody = document.getElementById("batchTableBody");

const workflowInput = document.getElementById("workflowInput");
const hasImmutableCheck = document.getElementById("hasImmutableCheck");
const hasKiteiCheck = document.getElementById("hasKiteiCheck");
const hasSearchCheck = document.getElementById("hasSearchCheck");
const under50mCheck = document.getElementById("under50mCheck");
const flowSummaryBox = document.getElementById("flowSummaryBox");
const flowTableBody = document.getElementById("flowTableBody");

const companyInput = document.getElementById("companyInput");
const managerInput = document.getElementById("managerInput");
const effectiveDateInput = document.getElementById("effectiveDateInput");
const kiteiPreview = document.getElementById("kiteiPreview");

let latestCsv = "";

function renderBatch() {
  const res = normalizeDenchoBatch(batchInput.value);
  latestCsv = res.indexCsvUtf8Bom;
  batchSummaryBox.className = `status-box ${
    res.totalCount > 0 && res.nonCompliantCount === 0
      ? "is-ok"
      : res.compliantCount > 0
        ? "is-warn"
        : "is-err"
  }`;
  batchSummaryBox.textContent = `変換件数: ${res.totalCount} 件 ／ 3要件充足: ${res.compliantCount} 件 ／ 要補完: ${res.nonCompliantCount} 件`;

  batchTableBody.replaceChildren();
  for (const r of res.records) {
    const tr = document.createElement("tr");

    const dTd = document.createElement("td");
    dTd.textContent = r.date || "（日付未検出）";

    const pTd = document.createElement("td");
    pTd.textContent = r.partner || "（取引先未検出）";

    const aTd = document.createElement("td");
    aTd.textContent = r.amountYen !== null ? `${r.amountYen.toLocaleString()}円` : "（金額未検出）";

    const tTd = document.createElement("td");
    tTd.textContent = r.invoiceId
      ? `${r.invoiceId} (${r.invoiceIdValid ? "妥当" : "不整合"})`
      : "-";

    const fTd = document.createElement("td");
    fTd.textContent = r.standardizedFilename;

    const sTd = document.createElement("td");
    sTd.className = r.compliant ? "sev-ok" : "sev-high";
    sTd.textContent = r.compliant ? "要件充足" : `不足: ${r.missingKeys.join(", ")}`;

    tr.append(dTd, pTd, aTd, tTd, fTd, sTd);
    batchTableBody.appendChild(tr);
  }
}

function renderFlowAudit() {
  const res = auditDenchoWorkflow({
    workflowText: workflowInput.value,
    isUnder50M: under50mCheck.checked,
    hasImmutableSystem: hasImmutableCheck.checked,
    hasJimuKitei: hasKiteiCheck.checked,
    hasSearchableNamingOrCsv: hasSearchCheck.checked,
  });

  flowSummaryBox.className = `status-box ${
    res.complianceScore >= 90 ? "is-ok" : res.complianceScore >= 60 ? "is-warn" : "is-err"
  }`;
  flowSummaryBox.textContent = `電帳法適合スコア: ${res.complianceScore}/100（${res.statusLabel}） ／ 指摘: ${res.findingsCount} 件`;

  flowTableBody.replaceChildren();
  if (res.findings.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "真実性・可視性・検索性の主要要件を満たしています。";
    tr.appendChild(td);
    flowTableBody.appendChild(tr);
    return;
  }

  for (const f of res.findings) {
    const tr = document.createElement("tr");
    const sTd = document.createElement("td");
    sTd.className = `sev-${f.severity}`;
    sTd.textContent = f.severityLabel;

    const lTd = document.createElement("td");
    lTd.textContent = f.law;

    const mTd = document.createElement("td");
    mTd.textContent = f.matched;

    const cTd = document.createElement("td");
    cTd.textContent = f.counterClause;

    tr.append(sTd, lTd, mTd, cTd);
    flowTableBody.appendChild(tr);
  }
}

function updateKitei() {
  kiteiPreview.textContent = generateJimuShoriKitei({
    companyName: companyInput.value.trim() || "株式会社サンプル",
    managerTitle: managerInput.value.trim() || "経理責任者",
    effectiveDate: effectiveDateInput.value.trim() || "2026-11-19",
  });
}

document.getElementById("loadSampleBatchBtn").addEventListener("click", () => {
  batchInput.value = SAMPLE_BATCH;
  renderBatch();
});

document.getElementById("clearBatchBtn").addEventListener("click", () => {
  batchInput.value = "";
  renderBatch();
});

document.getElementById("normalizeBatchBtn").addEventListener("click", renderBatch);

document.getElementById("downloadCsvBtn").addEventListener("click", () => {
  renderBatch();
  const blob = new Blob([latestCsv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "dencho_search_index.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

document.getElementById("loadRiskyFlowBtn").addEventListener("click", () => {
  workflowInput.value = RISKY_WORKFLOW;
  hasImmutableCheck.checked = false;
  hasKiteiCheck.checked = false;
  hasSearchCheck.checked = false;
  under50mCheck.checked = false;
  renderFlowAudit();
});

document.getElementById("loadSafeFlowBtn").addEventListener("click", () => {
  workflowInput.value = SAFE_WORKFLOW;
  hasImmutableCheck.checked = false;
  hasKiteiCheck.checked = true;
  hasSearchCheck.checked = true;
  renderFlowAudit();
});

document.getElementById("runFlowAuditBtn").addEventListener("click", renderFlowAudit);
[hasImmutableCheck, hasKiteiCheck, hasSearchCheck, under50mCheck].forEach((el) =>
  el.addEventListener("change", renderFlowAudit),
);

[companyInput, managerInput, effectiveDateInput].forEach((el) =>
  el.addEventListener("input", updateKitei),
);

document.getElementById("downloadKiteiBtn").addEventListener("click", () => {
  updateKitei();
  const blob = new Blob([kiteiPreview.textContent], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "jimu_shori_kitei.md";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

batchInput.value = SAMPLE_BATCH;
workflowInput.value = RISKY_WORKFLOW;
renderBatch();
renderFlowAudit();
updateKitei();
