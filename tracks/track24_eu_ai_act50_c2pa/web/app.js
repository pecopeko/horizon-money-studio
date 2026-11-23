/**
 * C2PAGATE Interactive Browser Controller (100% Local Uint8Array / DataView).
 * Zero network calls; supports drag-and-drop binary files + 1-click synthesized demos.
 */

import {
  ComplianceParseError,
  auditC2paCompliance,
  auditC2paText,
  buildSamplePresets,
  synthesizeMediaFromSpec,
} from "./engine.js";

const presets = buildSamplePresets();

const state = {
  activePreset: "stripped-cdn-png",
  gateFilter: "all",
  searchQuery: "",
  activeTab: "gates",
  uploadedMediaBytes: null,
  uploadedMediaName: null,
  lastReport: null,
  activeBinaryBytes: null,
};

const els = {
  sidebar: document.getElementById("app-sidebar"),
  mobileNavToggle: document.getElementById("mobile-nav-toggle"),
  presetBtns: [...document.querySelectorAll("[data-preset]")],
  filterBtns: [...document.querySelectorAll("[data-filter]")],
  tabBtns: [...document.querySelectorAll("[data-tab]")],
  posturePill: document.getElementById("posture-pill"),
  toastStatus: document.getElementById("toast-status"),
  findingLead: document.getElementById("finding-lead"),
  btnDownloadBinary: document.getElementById("btn-download-binary"),
  btnExportBundle: document.getElementById("btn-export-bundle"),
  binaryDropzone: document.getElementById("binary-dropzone"),
  binaryFileInput: document.getElementById("binary-file-input"),
  binarySourceCaption: document.getElementById("binary-source-caption"),
  byteStripTitle: document.getElementById("byte-strip-title"),
  byteStripRange: document.getElementById("byte-strip-range"),
  byteStripBar: document.getElementById("byte-strip-bar"),
  byteStripLegend: document.getElementById("byte-strip-legend"),
  factCarrier: document.getElementById("fact-carrier"),
  factLabels: document.getElementById("fact-labels"),
  factIptc: document.getElementById("fact-iptc"),
  factDigest: document.getElementById("fact-digest"),
  kpiScore: document.getElementById("kpi-score"),
  kpiGradeNote: document.getElementById("kpi-grade-note"),
  kpiGatesPassed: document.getElementById("kpi-gates-passed"),
  kpiGatesBreakdown: document.getElementById("kpi-gates-breakdown"),
  kpiJumbfCount: document.getElementById("kpi-jumbf-count"),
  kpiBytesUnit: document.getElementById("kpi-bytes-unit"),
  kpiSigNote: document.getElementById("kpi-sig-note"),
  bundleEditor: document.getElementById("bundle-editor"),
  bundleFileInput: document.getElementById("bundle-file-input"),
  btnApplyRemediation: document.getElementById("btn-apply-remediation"),
  parseErrorBox: document.getElementById("parse-error-box"),
  editorSourceLabel: document.getElementById("editor-source-label"),
  editorCharCount: document.getElementById("editor-char-count"),
  gateSearch: document.getElementById("gate-search"),
  gateTbody: document.getElementById("gate-tbody"),
  gateEmptyState: document.getElementById("gate-empty-state"),
  jumbfTbody: document.getElementById("jumbf-tbody"),
  jumbfEmptyState: document.getElementById("jumbf-empty-state"),
  headersCode: document.getElementById("headers-code"),
  jsonldCode: document.getElementById("jsonld-code"),
  manifestCode: document.getElementById("manifest-code"),
  cdnCode: document.getElementById("cdn-code"),
  btnCopyHeaders: document.getElementById("btn-copy-headers"),
  btnCopyJsonld: document.getElementById("btn-copy-jsonld"),
  btnCopyManifest: document.getElementById("btn-copy-manifest"),
  btnDownloadManifest: document.getElementById("btn-download-manifest"),
  btnCopyCdn: document.getElementById("btn-copy-cdn"),
};

let toastTimer = null;

function showToast(msg) {
  if (!els.toastStatus) return;
  els.toastStatus.textContent = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    els.toastStatus.textContent = "";
  }, 2600);
}

function formatHexOffset(num) {
  return `0x${Number(num).toString(16).toUpperCase().padStart(4, "0")}`; /* taste-skill-ignore: hex offset */
}

function updatePresetBadges() {
  for (const [key, cfg] of Object.entries(presets)) {
    const rep = auditC2paCompliance(cfg);
    const badge = document.getElementById(`badge-${key}`);
    if (badge) {
      const attentionCount = rep.gates_failed + rep.gates_warned;
      badge.textContent = String(attentionCount);
      badge.classList.toggle("is-alert", rep.gates_failed > 0);
    }
  }
}

function renderByteStrip(bi, assetName) {
  els.byteStripBar.replaceChildren();
  els.byteStripLegend.replaceChildren();

  if (!bi) {
    els.byteStripTitle.textContent = `${assetName} · No binary buffer loaded`;
    els.byteStripRange.textContent = "0 B";
    els.factCarrier.textContent = "-";
    els.factLabels.textContent = "-";
    els.factIptc.textContent = "-";
    els.factDigest.textContent = "-";
    return;
  }

  els.byteStripTitle.textContent = `${assetName} · ${bi.container_format.toUpperCase()} binary layout`;
  els.byteStripRange.textContent = `${bi.byte_length.toLocaleString("en-US")} B (${formatHexOffset(0)} .. ${formatHexOffset(bi.byte_length)})`;

  const total = Math.max(1, bi.byte_length);
  for (const seg of bi.segments) {
    const div = document.createElement("div");
    div.className = "byte-seg";
    if (seg.crc_valid === false) {
      div.classList.add("is-error");
    } else if (seg.is_c2pa) {
      div.classList.add("is-c2pa");
    }
    const sharePct = Math.max(7, Math.round((seg.length / total) * 100));
    div.style.flex = `${sharePct} 1 0%`;
    div.textContent = seg.kind;
    div.title = `${seg.kind} · offset ${formatHexOffset(seg.offset)} (${seg.length} B) ${seg.detail || ""}`;
    els.byteStripBar.appendChild(div);
  }

  const c2paSwatch = document.createElement("span");
  c2paSwatch.className = "legend-item";
  c2paSwatch.innerHTML = `<span class="legend-swatch is-c2pa"></span><span>C2PA JUMBF carrier (${bi.c2pa_carrier || "missing"})</span>`;
  const stdSwatch = document.createElement("span");
  stdSwatch.className = "legend-item";
  stdSwatch.innerHTML = `<span class="legend-swatch"></span><span>Media container chunks (${bi.segments.length} segments)</span>`;
  els.byteStripLegend.append(c2paSwatch, stdSwatch);

  els.factCarrier.textContent = `${bi.container_format.toUpperCase()} · ${bi.c2pa_carrier || "none"}`;
  els.factLabels.textContent = bi.jumbf_labels.length > 0 ? bi.jumbf_labels.join(", ") : "none";
  els.factLabels.title = els.factLabels.textContent;
  const shortIptc =
    bi.iptc_source_codes.length > 0 ? bi.iptc_source_codes.join(", ") : "none";
  els.factIptc.textContent = shortIptc;
  els.factIptc.title = bi.digital_source_types.join(", ") || "none";
  els.factDigest.textContent = bi.content_digest_header;
  els.factDigest.title = `SHA-256: ${bi.sha256_hex}`;
}

function renderGateTable(report) {
  els.gateTbody.replaceChildren();
  const q = state.searchQuery.trim().toLowerCase();

  const filtered = report.gates.filter((g) => {
    if (state.gateFilter === "issues" && g.status === "pass") return false;
    if (state.gateFilter === "passed" && g.status !== "pass") return false;
    if (!q) return true;
    const hay = `${g.gate_id} ${g.title} ${g.statutory_ref} ${g.summary} ${g.findings.map((f) => `${f.title} ${f.remediation}`).join(" ")}`.toLowerCase();
    return hay.includes(q);
  });

  els.gateEmptyState.hidden = filtered.length > 0;

  for (const g of filtered) {
    const tr = document.createElement("tr");

    const tdId = document.createElement("td");
    tdId.className = "gate-id-cell";
    const idCode = document.createElement("code");
    idCode.textContent = g.gate_id;
    tdId.appendChild(idCode);

    const tdBody = document.createElement("td");
    const titleDiv = document.createElement("div");
    titleDiv.className = "gate-title";
    titleDiv.textContent = g.title;
    const refDiv = document.createElement("div");
    refDiv.className = "gate-ref";
    refDiv.textContent = g.statutory_ref;
    const sumDiv = document.createElement("div");
    sumDiv.className = "gate-summary";
    sumDiv.textContent = g.summary;
    tdBody.append(titleDiv, refDiv, sumDiv);

    if (g.findings.length > 0) {
      const ul = document.createElement("ul");
      ul.className = "finding-list";
      for (const f of g.findings) {
        const li = document.createElement("li");
        li.className = "finding-item";
        li.setAttribute("data-ui", "");
        const fTitle = document.createElement("div");
        fTitle.className = "finding-item-title";
        fTitle.textContent = `[${f.severity.toUpperCase()}] ${f.title}`;
        const fFix = document.createElement("div");
        fFix.className = "finding-item-fix";
        fFix.textContent = `Fix: ${f.remediation}`;
        li.append(fTitle, fFix);
        ul.appendChild(li);
      }
      tdBody.appendChild(ul);
    }

    const tdWeight = document.createElement("td");
    tdWeight.className = "num";
    tdWeight.textContent = `${g.weight} pt`;

    const tdStatus = document.createElement("td");
    tdStatus.className = "num";
    const pill = document.createElement("span");
    pill.className =
      g.status === "pass" ? "pill pill-pass" : g.status === "warn" ? "pill pill-warn" : "pill pill-fail";
    pill.textContent = g.status === "pass" ? "Pass" : g.status === "warn" ? "Warn" : "Fail";
    tdStatus.appendChild(pill);

    tr.append(tdId, tdBody, tdWeight, tdStatus);
    els.gateTbody.appendChild(tr);
  }
}

function renderJumbfTable(bi) {
  els.jumbfTbody.replaceChildren();
  const boxes = bi ? bi.jumbf_boxes : [];
  els.jumbfEmptyState.hidden = boxes.length > 0;

  for (const box of boxes) {
    const tr = document.createElement("tr");

    const tdType = document.createElement("td");
    const indent = "\u00a0\u00a0".repeat(Math.min(4, box.depth || 0));
    const codeEl = document.createElement("code");
    codeEl.textContent = `${indent}${box.box_type}`;
    tdType.appendChild(codeEl);

    const tdMeta = document.createElement("td");
    const lblDiv = document.createElement("div");
    lblDiv.className = "gate-title";
    lblDiv.textContent = box.label || "(payload content box)";
    tdMeta.appendChild(lblDiv);
    if (box.uuid) {
      const uuidDiv = document.createElement("div");
      uuidDiv.className = "gate-ref";
      uuidDiv.textContent = `UUID ${box.uuid}`;
      tdMeta.appendChild(uuidDiv);
    }

    const tdOff = document.createElement("td");
    tdOff.className = "num";
    const offCode = document.createElement("code");
    offCode.textContent = formatHexOffset(box.offset);
    tdOff.appendChild(offCode);

    const tdLen = document.createElement("td");
    tdLen.className = "num";
    tdLen.textContent = `${box.length.toLocaleString("en-US")} B`;

    tr.append(tdType, tdMeta, tdOff, tdLen);
    els.jumbfTbody.appendChild(tr);
  }
}

function renderReport(report) {
  state.lastReport = report;

  // Posture pill & lead sentence
  if (report.status === "compliant") {
    els.posturePill.className = "pill pill-pass";
    els.posturePill.textContent = "Compliant";
    els.findingLead.textContent = `All 10 EU AI Act Art. 50 (${report.eu_art50_sunset}) and Japan AI Promotion Act safety gates passed (${report.score}/100).`;
  } else if (report.status === "action_required") {
    els.posturePill.className = "pill pill-warn";
    els.posturePill.textContent = "Action required";
    const firstWarn = report.findings[0];
    els.findingLead.textContent = firstWarn
      ? `${report.gates_warned} warning gate(s): ${firstWarn.title}.`
      : "Origin C2PA present; review warnings before December 2, 2026.";
  } else {
    els.posturePill.className = "pill pill-fail";
    els.posturePill.textContent = "Non-compliant";
    const topFail = report.findings[0];
    els.findingLead.textContent = topFail
      ? `${report.gates_failed} blocking gate(s) failed — lead issue: ${topFail.title}.`
      : "Blocking EU AI Act Art. 50 or Japan AI Safety failures detected.";
  }

  // KPI strip
  els.kpiScore.textContent = String(report.score);
  els.kpiGradeNote.textContent = `Grade ${report.grade}`;
  els.kpiGradeNote.className =
    report.score >= 90 ? "kpi-note is-good" : report.score < 70 ? "kpi-note is-bad" : "kpi-note";

  els.kpiGatesPassed.textContent = String(report.gates_passed);
  els.kpiGatesBreakdown.textContent = `${report.gates_failed} failed · ${report.gates_warned} warnings`;
  els.kpiGatesBreakdown.className = report.gates_failed > 0 ? "kpi-note is-bad" : "kpi-note";

  const bi = report.binary_inspection;
  els.kpiJumbfCount.textContent = bi ? String(bi.jumbf_boxes.length) : "0";
  els.kpiBytesUnit.textContent = bi ? `in ${bi.byte_length.toLocaleString("en-US")} B ${bi.container_format.toUpperCase()}` : "no binary";
  if (bi && bi.has_signature) {
    els.kpiSigNote.textContent = `COSE_Sign1 present (${bi.signature_byte_length} B)`;
    els.kpiSigNote.className = "kpi-note is-good";
  } else {
    els.kpiSigNote.textContent = "No COSE signature box";
    els.kpiSigNote.className = "kpi-note is-bad";
  }

  // Sidebar filter counts
  document.getElementById("filter-count-all").textContent = String(report.gates.length);
  document.getElementById("filter-count-issues").textContent = String(report.gates_failed + report.gates_warned);
  document.getElementById("filter-count-passed").textContent = String(report.gates_passed);

  renderByteStrip(bi, report.asset_name);
  renderGateTable(report);
  renderJumbfTable(bi);

  // Compliance bundle code blocks
  els.headersCode.textContent = report.compliance_bundle.http_headers_snippet;
  els.jsonldCode.textContent = report.compliance_bundle.schema_org_html_snippet;
  els.manifestCode.textContent = JSON.stringify(report.compliance_bundle.c2pa_manifest_template, null, 2);
  els.cdnCode.textContent = report.compliance_bundle.edge_preservation_config;
}

function evaluateCurrentWorkspace() {
  const rawText = els.bundleEditor.value;
  els.editorCharCount.textContent = `${rawText.length.toLocaleString("en-US")} chars`;

  try {
    const report = auditC2paText(rawText, { mediaBytes: state.uploadedMediaBytes });
    els.parseErrorBox.hidden = true;
    els.parseErrorBox.textContent = "";

    if (state.uploadedMediaBytes !== null) {
      state.activeBinaryBytes = state.uploadedMediaBytes;
    } else {
      const parsed = JSON.parse(rawText);
      if (parsed.synthetic_media) {
        state.activeBinaryBytes = synthesizeMediaFromSpec(parsed.synthetic_media);
      } else {
        state.activeBinaryBytes = null;
      }
    }

    renderReport(report);
  } catch (err) {
    els.parseErrorBox.hidden = false;
    els.parseErrorBox.textContent =
      err instanceof ComplianceParseError ? err.message : `Evaluation error: ${err.message}`;
  }
}

function loadPreset(presetKey) {
  const cfg = presets[presetKey];
  if (!cfg) return;
  state.activePreset = presetKey;
  state.uploadedMediaBytes = null;
  state.uploadedMediaName = null;

  for (const btn of els.presetBtns) {
    btn.setAttribute("aria-current", btn.dataset.preset === presetKey ? "true" : "false");
  }

  els.bundleEditor.value = JSON.stringify(cfg, null, 2);
  els.editorSourceLabel.textContent = `Source: preset:${presetKey}`;
  els.binarySourceCaption.textContent = `Synthesized ${cfg.synthetic_media.format.toUpperCase()} buffer in memory · Drop any local media file to override.`;
  evaluateCurrentWorkspace();
}

async function handleLocalBinaryFile(file) {
  if (!file) return;
  const arrayBuf = await file.arrayBuffer();
  const bytes = new Uint8Array(arrayBuf);
  state.uploadedMediaBytes = bytes;
  state.uploadedMediaName = file.name;
  state.activePreset = null;

  for (const btn of els.presetBtns) {
    btn.setAttribute("aria-current", "false");
  }

  // Update asset.name inside editor JSON if parseable
  try {
    const currentObj = JSON.parse(els.bundleEditor.value);
    if (!currentObj.asset || typeof currentObj.asset !== "object") currentObj.asset = {};
    currentObj.asset.name = file.name;
    delete currentObj.synthetic_media;
    els.bundleEditor.value = JSON.stringify(currentObj, null, 2);
  } catch {
    // Keep editor text untouched if user is mid-edit
  }

  els.editorSourceLabel.textContent = `Source: local-binary:${file.name}`;
  els.binarySourceCaption.textContent = `Local file inspected via Uint8Array (${bytes.length.toLocaleString("en-US")} B) · 0 network requests.`;
  evaluateCurrentWorkspace();
  showToast(`Inspected ${file.name}`);
}

function triggerDownload(filename, contentBytesOrString, mimeType = "application/json") {
  const blob =
    contentBytesOrString instanceof Uint8Array
      ? new Blob([contentBytesOrString], { type: mimeType })
      : new Blob([contentBytesOrString], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function copyText(text, label) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    showToast(`Copied ${label}`);
  }
}

function bindEvents() {
  for (const btn of els.presetBtns) {
    btn.addEventListener("click", () => {
      loadPreset(btn.dataset.preset);
      els.sidebar.classList.remove("is-open");
      els.mobileNavToggle?.setAttribute("aria-expanded", "false");
    });
  }

  for (const btn of els.filterBtns) {
    btn.addEventListener("click", () => {
      state.gateFilter = btn.dataset.filter;
      for (const b of els.filterBtns) {
        b.setAttribute("aria-current", b === btn ? "true" : "false");
      }
      if (state.lastReport) renderGateTable(state.lastReport);
      els.sidebar.classList.remove("is-open");
    });
  }

  for (const btn of els.tabBtns) {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      state.activeTab = targetTab;
      for (const b of els.tabBtns) {
        const selected = b === btn;
        b.setAttribute("aria-selected", selected ? "true" : "false");
        const panelId = b.getAttribute("aria-controls");
        const panel = document.getElementById(panelId);
        if (panel) panel.hidden = !selected;
      }
    });
  }

  els.mobileNavToggle?.addEventListener("click", () => {
    const isOpen = els.sidebar.classList.toggle("is-open");
    els.mobileNavToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  els.bundleEditor.addEventListener("input", () => {
    evaluateCurrentWorkspace();
  });

  els.gateSearch.addEventListener("input", () => {
    state.searchQuery = els.gateSearch.value;
    if (state.lastReport) renderGateTable(state.lastReport);
  });

  els.binaryFileInput.addEventListener("change", (ev) => {
    const file = ev.target.files?.[0];
    if (file) handleLocalBinaryFile(file);
    ev.target.value = "";
  });

  els.bundleFileInput.addEventListener("change", async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    els.bundleEditor.value = text;
    els.editorSourceLabel.textContent = `Source: json:${file.name}`;
    evaluateCurrentWorkspace();
    showToast(`Loaded ${file.name}`);
    ev.target.value = "";
  });

  // Drag-and-drop binary inspection
  els.binaryDropzone.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    els.binaryDropzone.classList.add("is-dragover");
  });
  els.binaryDropzone.addEventListener("dragleave", () => {
    els.binaryDropzone.classList.remove("is-dragover");
  });
  els.binaryDropzone.addEventListener("drop", (ev) => {
    ev.preventDefault();
    els.binaryDropzone.classList.remove("is-dragover");
    const file = ev.dataTransfer?.files?.[0];
    if (file) handleLocalBinaryFile(file);
  });

  els.btnApplyRemediation.addEventListener("click", () => {
    if (!state.lastReport) return;
    const rem = state.lastReport.remediated_input;
    // If the currently loaded local binary lacked valid AI C2PA credentials, switch to synthesized signed C2PA container
    const bi = state.lastReport.binary_inspection;
    if (!bi || !bi.c2pa_present || !bi.has_signature || bi.non_ai_capture_asserted) {
      state.uploadedMediaBytes = null;
      state.uploadedMediaName = null;
      els.binarySourceCaption.textContent = `Synthesized signed ${rem.synthetic_media.format.toUpperCase()} C2PA buffer · 10/10 Art. 50 + JP Safety ready.`;
    }
    els.bundleEditor.value = JSON.stringify(rem, null, 2);
    els.editorSourceLabel.textContent = "Source: auto-remediated (Art. 50 + JP Safety)";
    evaluateCurrentWorkspace();
    showToast("Applied 10/10 Art. 50 + JP fix");
  });

  els.btnDownloadBinary.addEventListener("click", () => {
    if (!state.activeBinaryBytes || !state.lastReport?.binary_inspection) {
      showToast("No binary buffer active");
      return;
    }
    const bi = state.lastReport.binary_inspection;
    const fname = state.lastReport.asset_name || `c2pa-demo.${bi.container_format}`;
    triggerDownload(fname, state.activeBinaryBytes, bi.mime_type);
    showToast(`Downloaded ${fname}`);
  });

  els.btnExportBundle.addEventListener("click", () => {
    if (!state.lastReport) return;
    triggerDownload(
      "c2pa-eu-art50-jp-compliance-bundle.json",
      `${JSON.stringify(state.lastReport.compliance_bundle, null, 2)}\n`,
      "application/json"
    );
    showToast("Exported compliance bundle");
  });

  els.btnDownloadManifest.addEventListener("click", () => {
    if (!state.lastReport) return;
    triggerDownload(
      "c2pa-manifest.json",
      `${JSON.stringify(state.lastReport.compliance_bundle.c2pa_manifest_template, null, 2)}\n`,
      "application/json"
    );
    showToast("Downloaded c2pa-manifest.json");
  });

  els.btnCopyHeaders.addEventListener("click", () => {
    if (state.lastReport) copyText(state.lastReport.compliance_bundle.http_headers_snippet, "HTTP headers");
  });
  els.btnCopyJsonld.addEventListener("click", () => {
    if (state.lastReport) copyText(state.lastReport.compliance_bundle.schema_org_html_snippet, "JSON-LD snippet");
  });
  els.btnCopyManifest.addEventListener("click", () => {
    if (state.lastReport) {
      copyText(JSON.stringify(state.lastReport.compliance_bundle.c2pa_manifest_template, null, 2), "c2patool manifest");
    }
  });
  els.btnCopyCdn.addEventListener("click", () => {
    if (state.lastReport) copyText(state.lastReport.compliance_bundle.edge_preservation_config, "CDN config");
  });
}

updatePresetBadges();
bindEvents();
loadPreset("stripped-cdn-png");
