import {
  auditMcpConfig,
  auditMcpText,
  buildSamplePresets
} from "./engine.js";

const presets = buildSamplePresets();

let currentReport = null;
let currentFilter = "all";
let currentSearch = "";
let toastTimer = null;

const elSidebar = document.getElementById("app-sidebar");
const elMobileToggle = document.getElementById("mobile-menu-toggle");
const elEditor = document.getElementById("manifest-editor");
const elParseError = document.getElementById("parse-error-box");
const elSourceLabel = document.getElementById("editor-source-label");
const elByteCount = document.getElementById("editor-byte-count");
const elSearch = document.getElementById("gate-search");
const elFileInput = document.getElementById("manifest-file-input");

const elPosturePill = document.getElementById("posture-pill");
const elToast = document.getElementById("toast-feedback");
const elFindingLead = document.getElementById("finding-lead");

const elKpiScore = document.getElementById("kpi-score");
const elKpiGradeNote = document.getElementById("kpi-grade-note");
const elKpiGatesPassed = document.getElementById("kpi-gates-passed");
const elKpiGatesBreakdown = document.getElementById("kpi-gates-breakdown");
const elKpiFindings = document.getElementById("kpi-findings");
const elKpiServersUnit = document.getElementById("kpi-servers-unit");
const elKpiBlockerNote = document.getElementById("kpi-blocker-note");

const elGateTbody = document.getElementById("gate-tbody");
const elGateEmpty = document.getElementById("gate-empty-state");
const elPolicyCode = document.getElementById("policy-json-code");
const elMigratedCode = document.getElementById("migrated-json-code");

const elFilterAll = document.getElementById("filter-count-all");
const elFilterIssues = document.getElementById("filter-count-issues");
const elFilterPassed = document.getElementById("filter-count-passed");

function showToast(msg) {
  elToast.textContent = msg;
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    elToast.textContent = "";
  }, 2600);
}

function updatePresetBadges() {
  for (const key of ["legacy-sse", "shadow-npx", "hardened-v2"]) {
    const rep = auditMcpConfig(presets[key]);
    const issueGates = rep.gates_failed + rep.gates_warned;
    const badge = document.getElementById(`badge-${key}`);
    if (badge) {
      badge.textContent = String(issueGates);
      badge.classList.toggle("is-alert", rep.gates_failed > 0);
    }
  }
}

function setActivePresetButton(presetKey) {
  document.querySelectorAll("[data-preset]").forEach((btn) => {
    btn.setAttribute("aria-current", btn.dataset.preset === presetKey ? "true" : "false");
  });
}

function setActiveFilterButton(filterKey) {
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.setAttribute("aria-current", btn.dataset.filter === filterKey ? "true" : "false");
  });
}

function setActiveTab(tabKey) {
  document.querySelectorAll("[data-tab]").forEach((btn) => {
    const selected = btn.dataset.tab === tabKey;
    btn.setAttribute("aria-selected", selected ? "true" : "false");
    const panelId = btn.getAttribute("aria-controls");
    const panel = document.getElementById(panelId);
    if (panel) {
      panel.hidden = !selected;
    }
  });
}

function buildStatusPill(status) {
  const span = document.createElement("span");
  if (status === "pass") {
    span.className = "pill pill-pass";
    span.textContent = "Pass";
  } else if (status === "warn") {
    span.className = "pill pill-warn";
    span.textContent = "Warn";
  } else {
    span.className = "pill pill-fail";
    span.textContent = "Fail";
  }
  return span;
}

function renderGateRows(report) {
  elGateTbody.replaceChildren();
  const query = currentSearch.trim().toLowerCase();

  const visibleGates = report.gates.filter((gate) => {
    if (currentFilter === "issues" && gate.status === "pass") return false;
    if (currentFilter === "passed" && gate.status !== "pass") return false;
    if (!query) return true;
    const haystack = [
      gate.gate_id,
      gate.name,
      gate.summary,
      ...gate.findings.flatMap((f) => [f.server_name, f.title, f.evidence, f.remediation])
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });

  elGateEmpty.hidden = visibleGates.length > 0;

  for (const gate of visibleGates) {
    const tr = document.createElement("tr");

    const tdId = document.createElement("td");
    tdId.className = "gate-id-cell";
    const idCode = document.createElement("code");
    idCode.textContent = gate.gate_id;
    tdId.appendChild(idCode);

    const tdBody = document.createElement("td");
    const titleDiv = document.createElement("div");
    titleDiv.className = "gate-name";
    titleDiv.textContent = gate.name;
    tdBody.appendChild(titleDiv);

    const summaryDiv = document.createElement("div");
    summaryDiv.className = "gate-summary";
    summaryDiv.textContent = gate.summary;
    tdBody.appendChild(summaryDiv);

    if (gate.findings.length > 0) {
      const ul = document.createElement("ul");
      ul.className = "finding-list";
      for (const f of gate.findings) {
        const li = document.createElement("li");
        li.className = "finding-item";
        li.setAttribute("data-ui", "");

        const fHead = document.createElement("div");
        fHead.className = "finding-item-title";
        fHead.textContent = `[${f.severity.toUpperCase()} · ${f.server_name}] ${f.title}`;

        const fFix = document.createElement("div");
        fFix.className = "finding-item-fix";
        fFix.textContent = `Remediation: ${f.remediation}`;

        li.appendChild(fHead);
        li.appendChild(fFix);
        ul.appendChild(li);
      }
      tdBody.appendChild(ul);
    }

    const tdHits = document.createElement("td");
    tdHits.className = "num";
    tdHits.textContent = String(gate.findings_count);

    const tdStatus = document.createElement("td");
    tdStatus.className = "num";
    tdStatus.appendChild(buildStatusPill(gate.status));

    tr.appendChild(tdId);
    tr.appendChild(tdBody);
    tr.appendChild(tdHits);
    tr.appendChild(tdStatus);
    elGateTbody.appendChild(tr);
  }
}

function renderReport(report) {
  currentReport = report;

  elKpiScore.textContent = String(report.score);
  elKpiGradeNote.textContent = `Grade ${report.grade}`;
  elKpiGradeNote.className =
    report.status === "ready"
      ? "kpi-note is-good"
      : report.status === "blocked"
        ? "kpi-note is-bad"
        : "kpi-note";

  elKpiGatesPassed.textContent = String(report.gates_passed);
  elKpiGatesBreakdown.textContent = `${report.gates_failed} failed · ${report.gates_warned} warnings`;

  elKpiFindings.textContent = String(report.findings_count);
  const srvCount = report.servers_audited;
  elKpiServersUnit.textContent = srvCount === 1 ? "across 1 server" : `across ${srvCount} servers`;

  const blockerCount = report.findings.filter(
    (f) => f.severity === "critical" || f.severity === "high"
  ).length;
  elKpiBlockerNote.textContent =
    blockerCount > 0 ? `${blockerCount} high or critical` : "0 high or critical";
  elKpiBlockerNote.className = blockerCount > 0 ? "kpi-note is-bad" : "kpi-note is-good";

  if (report.status === "ready") {
    elPosturePill.className = "pill pill-pass";
    elPosturePill.textContent = "Ready";
    elFindingLead.textContent =
      `All 10 Stateless MCP 2026-07-28 and Enterprise L7 Firewall gates pass across ${srvCount} configured ${srvCount === 1 ? "server" : "servers"}.`;
  } else if (report.status === "action_required") {
    elPosturePill.className = "pill pill-warn";
    elPosturePill.textContent = "Action required";
    elFindingLead.textContent = report.findings[0]
      ? `Primary advisory (${report.findings[0].server_name}): ${report.findings[0].title}.`
      : "Medium-severity firewall advisories require review before edge rollout.";
  } else {
    elPosturePill.className = "pill pill-fail";
    elPosturePill.textContent = "Blocked";
    const topFinding =
      report.findings.find((f) => f.severity === "critical") || report.findings[0];
    elFindingLead.textContent = topFinding
      ? `Primary blocker (${topFinding.server_name}): ${topFinding.title}.`
      : "High-severity findings block Enterprise MCP Firewall deployment.";
  }

  const issueGateCount = report.gates_failed + report.gates_warned;
  elFilterAll.textContent = String(report.gates.length);
  elFilterIssues.textContent = String(issueGateCount);
  elFilterIssues.classList.toggle("is-alert", report.gates_failed > 0);
  elFilterPassed.textContent = String(report.gates_passed);

  renderGateRows(report);
  elPolicyCode.textContent = JSON.stringify(report.enterprise_firewall_policy, null, 2);
  elMigratedCode.textContent = JSON.stringify(report.migrated_stateless_config, null, 2);
}

function evaluateEditorText(sourceTag) {
  const raw = elEditor.value;
  const byteLen = new TextEncoder().encode(raw).length;
  elByteCount.textContent = `${byteLen.toLocaleString("en-US")} bytes`;
  if (sourceTag) {
    elSourceLabel.textContent = `Source: ${sourceTag}`;
  }

  try {
    const report = auditMcpText(raw);
    elParseError.hidden = true;
    elParseError.textContent = "";
    renderReport(report);
  } catch (err) {
    elParseError.hidden = false;
    elParseError.textContent = `${err.message} Showing last valid audit state until syntax is fixed.`;
  }
}

function loadPreset(presetKey) {
  const data = presets[presetKey];
  if (!data) return;
  setActivePresetButton(presetKey);
  elEditor.value = JSON.stringify(data, null, 2);
  evaluateEditorText(`preset:${presetKey}`);
  elSidebar.classList.remove("is-open");
  elMobileToggle.setAttribute("aria-expanded", "false");
}

function downloadJsonFile(filename, obj) {
  const payload = JSON.stringify(obj, null, 2) + "\n";
  const blob = new Blob([payload], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function copyJsonToClipboard(obj, label) {
  const payload = JSON.stringify(obj, null, 2) + "\n";
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(payload);
    showToast(`Copied ${label}`);
  }
}

// Wire event listeners
document.querySelectorAll("[data-preset]").forEach((btn) => {
  btn.addEventListener("click", () => {
    loadPreset(btn.dataset.preset);
  });
});

document.querySelectorAll("[data-filter]").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;
    setActiveFilterButton(currentFilter);
    setActiveTab("gates");
    if (currentReport) {
      renderGateRows(currentReport);
    }
    elSidebar.classList.remove("is-open");
    elMobileToggle.setAttribute("aria-expanded", "false");
  });
});

document.querySelectorAll("[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => {
    setActiveTab(btn.dataset.tab);
  });
});

elSearch.addEventListener("input", () => {
  currentSearch = elSearch.value;
  setActiveTab("gates");
  if (currentReport) {
    renderGateRows(currentReport);
  }
});

elEditor.addEventListener("input", () => {
  setActivePresetButton("");
  evaluateEditorText("custom-editor");
});

elFileInput.addEventListener("change", async (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const text = await file.text();
  setActivePresetButton("");
  elEditor.value = text;
  evaluateEditorText(`file:${file.name}`);
  showToast(`Loaded ${file.name}`);
});

document.getElementById("btn-apply-remediation").addEventListener("click", () => {
  if (!currentReport) return;
  setActivePresetButton("");
  elEditor.value = JSON.stringify(currentReport.migrated_stateless_config, null, 2);
  evaluateEditorText("auto-remediated:2026-07-28");
  showToast("Applied Stateless 2026-07-28 remediation");
});

function handleDownloadPolicy() {
  if (!currentReport) return;
  downloadJsonFile("mcp-enterprise-firewall-policy.json", currentReport.enterprise_firewall_policy);
  showToast("Exported mcp-enterprise-firewall-policy.json");
}

function handleDownloadPatch() {
  if (!currentReport) return;
  downloadJsonFile("mcp-stateless-2026-07-28.json", currentReport.migrated_stateless_config);
  showToast("Exported mcp-stateless-2026-07-28.json");
}

document.getElementById("btn-download-policy").addEventListener("click", handleDownloadPolicy);
document.getElementById("btn-save-policy-tab").addEventListener("click", handleDownloadPolicy);
document.getElementById("btn-download-patch").addEventListener("click", handleDownloadPatch);
document.getElementById("btn-save-migrated-tab").addEventListener("click", handleDownloadPatch);

document.getElementById("btn-copy-policy").addEventListener("click", () => {
  if (currentReport) {
    copyJsonToClipboard(currentReport.enterprise_firewall_policy, "firewall policy JSON");
  }
});

document.getElementById("btn-copy-migrated").addEventListener("click", () => {
  if (currentReport) {
    copyJsonToClipboard(currentReport.migrated_stateless_config, "Stateless 2026-07-28 config");
  }
});

elMobileToggle.addEventListener("click", () => {
  const isOpen = elSidebar.classList.toggle("is-open");
  elMobileToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
});

// Initialize default state
updatePresetBadges();
loadPreset("legacy-sse");
