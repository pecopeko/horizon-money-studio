import { auditJapaneseAdCopy } from "./core/yakki-engine.mjs";

const extInput = document.getElementById("extInput");
const extResult = document.getElementById("extResult");
const grabBtn = document.getElementById("grabSelectionBtn");
const auditBtn = document.getElementById("auditBtn");

function renderResult() {
  const res = auditJapaneseAdCopy(extInput.value);
  const lines = [
    `リスク: ${res.riskLevel} (${res.overallRiskScore} / 100) [${res.predictedLabel}]`,
    `検出: ${res.findings.length} 件`,
    ...res.findings.map((f) => `- [${f.law}] ${f.matchedText}: ${f.suggestion}`),
  ];
  extResult.textContent = lines.join("\n");
}

auditBtn.addEventListener("click", renderResult);
grabBtn.addEventListener("click", async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return;
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection()?.toString() || "",
    });
    if (result) {
      extInput.value = result;
      renderResult();
    }
  } catch (err) {
    extResult.textContent = `選択取得不可: ${err?.message || err}`;
  }
});
