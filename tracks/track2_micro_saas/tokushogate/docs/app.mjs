import { auditTokushoAndCheckout, generateTokushoTemplate } from "./core/tokusho-engine.mjs";

const RISKY_TOKUSHO = `販売業者：○○ショップ
メールアドレス：info@example.com
販売価格：プランページ記載
支払方法：クレジットカード
返品について：いかなる理由であっても一切返金いたしません。解約は電話のみで承ります。`;

const RISKY_CHECKOUT = `今すぐ申し込む（初回500円！初月無料キャンペーン実施中！）
※確認ボタンをクリックして注文を確定してください。`;

const SAFE_TOKUSHO = `販売業者：合同会社ホライゾンラボ
運営統括責任者：田中 一郎
所在地：請求があったら遅滞なく開示いたします
電話番号：請求があったら遅滞なく開示いたします
メールアドレス：support@example.co.jp
販売価格：月額 2,980円（消費税込）
商品代金以外の必要料金：通信料・振込手数料
支払方法および支払時期：クレジットカード決済（申込時および毎月応当日決済）
商品の引渡時期：決済完了後直ちに利用開始
返品・解約条件：デジタル役務の特性上お客様都合の返金不可（不具合・瑕疵時は全額返金）。定期課金はマイページよりいつでも解約可能。
動作環境：Chrome / Safari / Edge 最新版`;

const SAFE_CHECKOUT = `初回500円（税込）・2回目以降は月額2,980円（税込）となります。最低契約期間の定めなし・12ヶ月利用時の支払総額目安33,280円（税込）。管理画面からいつでも解約できます。`;

const tokushoInput = document.getElementById("tokushoTextInput");
const checkoutInput = document.getElementById("checkoutTextInput");
const isDigitalCheckbox = document.getElementById("isDigitalCheckbox");
const isSubCheckbox = document.getElementById("isSubCheckbox");
const summaryBox = document.getElementById("auditSummaryBox");
const findingsBody = document.getElementById("findingsTableBody");
const templatePreview = document.getElementById("templatePreview");
const sellerInput = document.getElementById("sellerInput");
const repInput = document.getElementById("repInput");
const emailInput = document.getElementById("emailInput");

let latestAuditReportMd = "";

function updateTemplate() {
  templatePreview.textContent = generateTokushoTemplate({
    seller: sellerInput.value.trim() || "株式会社サンプル",
    representative: repInput.value.trim() || "代表 太郎",
    email: emailInput.value.trim() || "support@example.com",
  });
}

function renderAudit() {
  const res = auditTokushoAndCheckout({
    tokushoText: tokushoInput.value,
    checkoutText: checkoutInput.value,
    isDigitalOrSaas: isDigitalCheckbox.checked,
    isSubscription: isSubCheckbox.checked,
  });

  summaryBox.className = `status-box ${
    res.complianceScore >= 90 && res.missingCount === 0
      ? "is-ok"
      : res.complianceScore >= 60
        ? "is-warn"
        : "is-err"
  }`;
  summaryBox.textContent = `法令・審査適合スコア: ${res.complianceScore}/100（${res.underwritingStatus}） ／ 欠落項目: ${res.missingCount} 件 ／ 指摘計: ${res.findingsCount} 件`;

  findingsBody.replaceChildren();
  const mdLines = [
    "# 特定商取引法・最終確認画面 監査メモ（TOKUSHOGATE生成）",
    `- 適合スコア: ${res.complianceScore}/100（${res.underwritingStatus}）`,
    "",
  ];

  if (res.findings.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "特商法第11条必須項目および定期確認画面の基本要件を満たしています。";
    tr.appendChild(td);
    findingsBody.appendChild(tr);
    mdLines.push("主要必須項目およびダークパターン禁止チェックをすべて通過しました。");
  } else {
    for (const f of res.findings) {
      const tr = document.createElement("tr");
      const sTd = document.createElement("td");
      sTd.className = `sev-${f.severity}`;
      sTd.textContent = f.severityLabel;

      const lTd = document.createElement("td");
      lTd.textContent = `${f.title}（${f.law}）`;

      const mTd = document.createElement("td");
      mTd.textContent = f.matched;

      const cTd = document.createElement("td");
      cTd.textContent = f.counterClause;

      tr.append(sTd, lTd, mTd, cTd);
      findingsBody.appendChild(tr);
      mdLines.push(`## ${f.title} [${f.ruleId}]`);
      mdLines.push(`- 根拠: ${f.law}`);
      mdLines.push(`- 修正案: ${f.counterClause}`);
      mdLines.push("");
    }
  }
  latestAuditReportMd = mdLines.join("\n");
}

document.getElementById("loadRiskyPresetBtn").addEventListener("click", () => {
  tokushoInput.value = RISKY_TOKUSHO;
  checkoutInput.value = RISKY_CHECKOUT;
  renderAudit();
});

document.getElementById("loadSafePresetBtn").addEventListener("click", () => {
  tokushoInput.value = SAFE_TOKUSHO;
  checkoutInput.value = SAFE_CHECKOUT;
  renderAudit();
});

document.getElementById("runAuditBtn").addEventListener("click", renderAudit);
isDigitalCheckbox.addEventListener("change", renderAudit);
isSubCheckbox.addEventListener("change", renderAudit);
sellerInput.addEventListener("input", updateTemplate);
repInput.addEventListener("input", updateTemplate);
emailInput.addEventListener("input", updateTemplate);

document.getElementById("copyReportBtn").addEventListener("click", async () => {
  if (!latestAuditReportMd) renderAudit();
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(latestAuditReportMd);
    summaryBox.textContent = `${summaryBox.textContent} ／ 修正提案をコピーしました`;
  }
});

document.getElementById("downloadTemplateBtn").addEventListener("click", () => {
  updateTemplate();
  const blob = new Blob([templatePreview.textContent], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "tokushoho.md";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

tokushoInput.value = RISKY_TOKUSHO;
checkoutInput.value = RISKY_CHECKOUT;
updateTemplate();
renderAudit();
