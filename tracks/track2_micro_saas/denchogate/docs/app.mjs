import {
  STUDIO_CSV_FILENAME,
  STUDIO_KITEI_FILENAME,
  analyzeUploadedFile,
  auditDenchoWorkflow,
  buildDenchoZipPackage,
  buildStudioIndexCsv,
  createSyntheticInvoicePdfBytes,
  formatDenchoFilename,
  generateJimuShoriKitei,
  markDuplicateRecords,
  normalizeDenchoRecord,
  parseJapaneseOrIsoDate,
  resolveFilenameCollisions,
  verifyInvoiceTNumber,
} from "./core/dencho-engine.mjs";

const SUPPORTED_EXT_RE = /\.(pdf|png|jpe?g|webp|tiff?)$/i;

const SAMPLE_PASTE_LINES = `令和8年11月19日 株式会社サンプル商事 請求書 110,000円 T7000012050002.pdf
R6.4.5/株式会社クラウド保守/¥55,000.pdf
2026年10月31日 さくらITサービス ０円（無料枠調整）
領収書_田中商店_8800円.jpg`;

const RISKY_WORKFLOW =
  "メール添付PDFは紙に印刷してバインダー保存し電子ファイルは破棄しています。スキャン時は150dpiで取り込み。";

const SAFE_WORKFLOW =
  "電子取引PDFはYYYYMMDD_取引先名_金額.pdfで命名のうえ事務処理規程を備付けし、検索用索引簿CSVとともにNASへ7年保存しています。";

const SOURCE_BADGES = {
  pdf_text: { label: "PDF本文抽出", cls: "src-pill src-pill--pdf" },
  "pdf+filename": { label: "PDF＋ファイル名", cls: "src-pill src-pill--pdf" },
  filename: { label: "ファイル名抽出", cls: "src-pill" },
  manual: { label: "手動編集済", cls: "src-pill" },
  manual_required: { label: "要手入力", cls: "src-pill" },
};

let nextRowId = 1;

const state = {
  items: [],
  selectedId: null,
  filter: "all",
  template: "compact_no_yen",
  includeTNumber: false,
  excludeDuplicatesInZip: false,
  showExtractedText: false,
  fsDirHandle: null,
  lastUndoOps: [],
};

// DOM References
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const fsDirectBtn = document.getElementById("fsDirectBtn");
const fsSupportHint = document.getElementById("fsSupportHint");
const loadDemoPdfsBtn = document.getElementById("loadDemoPdfsBtn");

const directFsBanner = document.getElementById("directFsBanner");
const directFsLabel = document.getElementById("directFsLabel");
const directFsDetail = document.getElementById("directFsDetail");
const applyDirectRenameBtn = document.getElementById("applyDirectRenameBtn");
const undoDirectRenameBtn = document.getElementById("undoDirectRenameBtn");
const disconnectFsBtn = document.getElementById("disconnectFsBtn");

const togglePasteModeBtn = document.getElementById("togglePasteModeBtn");
const pasteModeDrawer = document.getElementById("pasteModeDrawer");
const pasteInput = document.getElementById("pasteInput");
const importPasteLinesBtn = document.getElementById("importPasteLinesBtn");
const fillPasteSampleBtn = document.getElementById("fillPasteSampleBtn");

const kpiTotal = document.getElementById("kpiTotal");
const kpiCompliant = document.getElementById("kpiCompliant");
const kpiReview = document.getElementById("kpiReview");
const kpiDuplicates = document.getElementById("kpiDuplicates");

const templateSelect = document.getElementById("templateSelect");
const includeTNumberCheck = document.getElementById("includeTNumberCheck");
const excludeDupZipCheck = document.getElementById("excludeDupZipCheck");
const downloadZipBtn = document.getElementById("downloadZipBtn");
const downloadCsvBtn = document.getElementById("downloadCsvBtn");
const clearAllBtn = document.getElementById("clearAllBtn");
const actionNotice = document.getElementById("actionNotice");

const filterTabs = [...document.querySelectorAll(".filter-tab")];
const ledgerTableBody = document.getElementById("ledgerTableBody");
const emptyStateBox = document.getElementById("emptyStateBox");

const previewTitle = document.getElementById("previewTitle");
const previewMeta = document.getElementById("previewMeta");
const previewBadges = document.getElementById("previewBadges");
const previewStage = document.getElementById("previewStage");
const extractedTextBox = document.getElementById("extractedTextBox");
const toggleExtractedTextBtn = document.getElementById("toggleExtractedTextBtn");
const openPreviewTabLink = document.getElementById("openPreviewTabLink");

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

function formatBytes(n) {
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function getTodayCompact() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}${m}${day}`;
}

function showNotice(message, tone = "ok") {
  if (!message) {
    actionNotice.hidden = true;
    actionNotice.textContent = "";
    return;
  }
  actionNotice.hidden = false;
  actionNotice.className = `action-notice${tone === "warn" ? " is-warn" : tone === "err" ? " is-err" : ""}`;
  actionNotice.textContent = message;
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function revokeItemPreviewUrl(item) {
  if (item && item.previewUrl) {
    URL.revokeObjectURL(item.previewUrl);
    item.previewUrl = "";
  }
}

function revokeAllPreviewUrls() {
  for (const item of state.items) {
    revokeItemPreviewUrl(item);
  }
}

function ensurePreviewUrl(item) {
  if (!item || !item.bytes || item.bytes.byteLength === 0) return "";
  if (!item.previewUrl) {
    const mime =
      item.mimeType ||
      (item.extension === ".pdf"
        ? "application/pdf"
        : item.extension === ".png"
          ? "image/png"
          : item.extension === ".webp"
            ? "image/webp"
            : "image/jpeg");
    item.previewUrl = URL.createObjectURL(new Blob([item.bytes], { type: mime }));
  }
  return item.previewUrl;
}

function getKiteiOptions() {
  return {
    companyName: companyInput.value.trim() || "株式会社サンプル",
    managerTitle: managerInput.value.trim() || "経理責任者",
    effectiveDate: effectiveDateInput.value.trim() || "2026-11-19",
  };
}

function recomputeAll() {
  const formatted = state.items.map((item) => {
    const res = formatDenchoFilename(
      {
        date: item.dateInput,
        partner: item.partnerInput,
        amountYen: item.amountInput,
        invoiceId: item.invoiceInput,
        extension: item.extension,
      },
      {
        template: state.template,
        includeTNumber: state.includeTNumber,
      },
    );
    return {
      ...item,
      date: res.date,
      partner: res.partner,
      amountYen: res.amountYen,
      invoiceId: res.invoiceId,
      invoiceIdValid: res.invoiceIdValid,
      standardizedFilename: res.filename,
      missingKeys: res.missingKeys,
      compliant: res.compliant,
    };
  });

  const withDups = markDuplicateRecords(formatted);
  state.items = resolveFilenameCollisions(withDups);
}

function getFilteredItems() {
  if (state.filter === "review") {
    return state.items.filter((it) => !it.compliant || it.invoiceIdValid === false);
  }
  if (state.filter === "duplicate") {
    return state.items.filter((it) => it.isDuplicate || it.hasDuplicatePeer);
  }
  return state.items;
}

function updateKpiBar() {
  const total = state.items.length;
  const compliant = state.items.filter((it) => it.compliant && it.invoiceIdValid !== false).length;
  const review = total - compliant;
  const duplicates = state.items.filter((it) => it.isDuplicate).length;

  kpiTotal.textContent = String(total);
  kpiCompliant.textContent = String(compliant);
  kpiReview.textContent = String(review);
  kpiDuplicates.textContent = String(duplicates);

  downloadZipBtn.disabled = total === 0;
  downloadCsvBtn.disabled = total === 0;
}

function buildStatusMarkup(item) {
  const frag = document.createDocumentFragment();
  const top = document.createElement("div");
  top.className = "status-row-top";

  const pill = document.createElement("span");
  if (item.compliant && item.invoiceIdValid !== false) {
    pill.className = "pill pill--ok";
    pill.textContent = "要件充足";
  } else if (!item.compliant) {
    pill.className = "pill pill--warn";
    const keyJa = { date: "日付", partner: "取引先", amount: "金額" };
    pill.textContent = `不足:${item.missingKeys.map((k) => keyJa[k] || k).join("/")}`;
  } else {
    pill.className = "pill pill--warn";
    pill.textContent = "T番号要確認";
  }

  const delBtn = document.createElement("button");
  delBtn.type = "button";
  delBtn.className = "row-del-btn";
  delBtn.title = "この行を一覧から除外";
  delBtn.setAttribute("aria-label", `${item.originalName} を削除`);
  delBtn.textContent = "×";
  delBtn.dataset.action = "delete";

  top.append(pill, delBtn);
  frag.appendChild(top);

  if (item.isDuplicate) {
    const dup = document.createElement("span");
    dup.className = "pill pill--dup";
    dup.title = `SHA-256一致: ${item.duplicateOf}`;
    dup.textContent = "重複ファイル";
    frag.appendChild(dup);
  } else if (item.hasDuplicatePeer) {
    const peer = document.createElement("span");
    peer.className = "pill pill--peer";
    peer.title = `同一ハッシュ計${item.duplicateGroupSize}件`;
    peer.textContent = `同一データ×${item.duplicateGroupSize}`;
    frag.appendChild(peer);
  }

  return frag;
}

function updateTBadgeElement(el, item) {
  const raw = String(item.invoiceInput || "").trim();
  if (!raw) {
    el.className = "t-badge t-badge--none";
    el.textContent = "未記載";
  } else if (item.invoiceId && item.invoiceIdValid) {
    el.className = "t-badge t-badge--ok";
    el.textContent = "Mod-9 妥当";
  } else if (item.invoiceId && item.invoiceIdValid === false) {
    el.className = "t-badge t-badge--err";
    el.textContent = "Mod-9 不整合";
  } else {
    el.className = "t-badge t-badge--err";
    el.textContent = "T+13桁形式で入力";
  }
}

/**
 * Update computed columns & KPIs in place without recreating inputs (preserves IME composition!).
 */
function syncComputedCellsInPlace() {
  updateKpiBar();
  const byId = new Map(state.items.map((it) => [it.id, it]));

  for (const tr of ledgerTableBody.querySelectorAll("tr[data-row-id]")) {
    const id = Number(tr.dataset.rowId);
    const item = byId.get(id);
    if (!item) continue;

    tr.classList.toggle("is-selected", item.id === state.selectedId);
    tr.classList.toggle("is-duplicate-row", item.isDuplicate);

    const dateInp = tr.querySelector('input[data-field="date"]');
    const partnerInp = tr.querySelector('input[data-field="partner"]');
    const amountInp = tr.querySelector('input[data-field="amount"]');
    if (dateInp) dateInp.classList.toggle("is-missing", !item.date);
    if (partnerInp) partnerInp.classList.toggle("is-missing", !item.partner);
    if (amountInp) amountInp.classList.toggle("is-missing", item.amountYen === null);

    const tBadge = tr.querySelector('[data-role="t-badge"]');
    if (tBadge) updateTBadgeElement(tBadge, item);

    const targetEl = tr.querySelector('[data-role="target-name"]');
    if (targetEl) targetEl.textContent = item.standardizedFilename;

    const srcEl = tr.querySelector('[data-role="src-pill"]');
    if (srcEl) {
      const info = SOURCE_BADGES[item.primarySource] || SOURCE_BADGES.manual;
      srcEl.className = info.cls;
      srcEl.textContent = info.label;
    }

    const statusTd = tr.querySelector('[data-role="status-stack"]');
    if (statusTd) {
      statusTd.replaceChildren(buildStatusMarkup(item));
    }
  }

  // Keep right preview header synced with target filename
  const selected = byId.get(state.selectedId);
  if (selected) {
    previewTitle.textContent = selected.standardizedFilename;
  }
}

function renderTable() {
  updateKpiBar();
  const visible = getFilteredItems();

  emptyStateBox.hidden = state.items.length > 0;
  ledgerTableBody.replaceChildren();

  if (visible.length === 0 && state.items.length > 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.style.padding = "1.2rem";
    td.style.color = "var(--muted)";
    td.textContent = "現在のフィルタ条件に一致するファイルはありません。";
    tr.appendChild(td);
    ledgerTableBody.appendChild(tr);
    return;
  }

  for (const item of visible) {
    const tr = document.createElement("tr");
    tr.className = "ledger-row";
    tr.dataset.rowId = String(item.id);
    if (item.id === state.selectedId) tr.classList.add("is-selected");
    if (item.isDuplicate) tr.classList.add("is-duplicate-row");

    // 1. Date cell
    const tdDate = document.createElement("td");
    const dateInput = document.createElement("input");
    dateInput.type = "text";
    dateInput.className = `cell-input cell-input--mono${!item.date ? " is-missing" : ""}`;
    dateInput.placeholder = "YYYYMMDD";
    dateInput.value = item.dateInput;
    dateInput.dataset.field = "date";
    dateInput.setAttribute("aria-label", `${item.originalName} の取引日`);
    tdDate.appendChild(dateInput);

    // 2. Partner cell
    const tdPartner = document.createElement("td");
    const partnerInput = document.createElement("input");
    partnerInput.type = "text";
    partnerInput.className = `cell-input${!item.partner ? " is-missing" : ""}`;
    partnerInput.placeholder = "取引先名";
    partnerInput.value = item.partnerInput;
    partnerInput.dataset.field = "partner";
    partnerInput.setAttribute("aria-label", `${item.originalName} の取引先`);
    tdPartner.appendChild(partnerInput);

    // 3. Amount cell
    const tdAmount = document.createElement("td");
    const amountInput = document.createElement("input");
    amountInput.type = "text";
    amountInput.inputMode = "numeric";
    amountInput.className = `cell-input cell-input--num${item.amountYen === null ? " is-missing" : ""}`;
    amountInput.placeholder = "金額";
    amountInput.value = item.amountInput;
    amountInput.dataset.field = "amount";
    amountInput.setAttribute("aria-label", `${item.originalName} の取引金額`);
    tdAmount.appendChild(amountInput);

    // 4. T-Number cell
    const tdTnum = document.createElement("td");
    const tInput = document.createElement("input");
    tInput.type = "text";
    tInput.className = "cell-input cell-input--mono";
    tInput.placeholder = "T+13桁";
    tInput.value = item.invoiceInput;
    tInput.dataset.field = "invoiceId";
    tInput.setAttribute("aria-label", `${item.originalName} の適格請求書T番号`);
    const tBadge = document.createElement("span");
    tBadge.dataset.role = "t-badge";
    updateTBadgeElement(tBadge, item);
    tdTnum.append(tInput, tBadge);

    // 5. Target filename & provenance cell
    const tdTarget = document.createElement("td");
    const targetSpan = document.createElement("span");
    targetSpan.className = "target-name";
    targetSpan.dataset.role = "target-name";
    targetSpan.textContent = item.standardizedFilename;

    const origMeta = document.createElement("div");
    origMeta.className = "orig-meta";
    const srcInfo = SOURCE_BADGES[item.primarySource] || SOURCE_BADGES.manual;
    const srcPill = document.createElement("span");
    srcPill.className = srcInfo.cls;
    srcPill.dataset.role = "src-pill";
    srcPill.textContent = srcInfo.label;

    const origNameSpan = document.createElement("span");
    origNameSpan.textContent = item.originalName;
    origMeta.append(srcPill, origNameSpan);
    tdTarget.append(targetSpan, origMeta);

    // 6. Status & Duplicate cell
    const tdStatus = document.createElement("td");
    const statusStack = document.createElement("div");
    statusStack.className = "status-stack";
    statusStack.dataset.role = "status-stack";
    statusStack.appendChild(buildStatusMarkup(item));
    tdStatus.appendChild(statusStack);

    tr.append(tdDate, tdPartner, tdAmount, tdTnum, tdTarget, tdStatus);
    ledgerTableBody.appendChild(tr);
  }
}

function renderPreview() {
  const item = state.items.find((it) => it.id === state.selectedId) || null;
  if (!item) {
    previewTitle.textContent = "証憑プレビュー";
    previewMeta.textContent = "左の行を選択するとPDF・領収書画像をブラウザ内で即時表示します";
    previewBadges.hidden = true;
    previewBadges.replaceChildren();
    toggleExtractedTextBtn.hidden = true;
    openPreviewTabLink.hidden = true;
    extractedTextBox.hidden = true;
    previewStage.replaceChildren();

    const ph = document.createElement("div");
    ph.className = "preview-placeholder";
    const strong = document.createElement("strong");
    strong.textContent = "選択中のファイルなし";
    const p = document.createElement("p");
    p.textContent =
      "PDFや領収書画像を選択すると、ここに原本が表示されます。スキャン画像や手書き領収書も、画面を切り替えず左の表へキーボード入力できます。";
    ph.append(strong, p);
    previewStage.appendChild(ph);
    return;
  }

  previewTitle.textContent = item.standardizedFilename;
  const sizePart = item.sizeBytes ? `${formatBytes(item.sizeBytes)} / ` : "テキスト明細 / ";
  const hashPart = item.sha256Short ? `SHA-256: ${item.sha256Short}…` : "ハッシュなし";
  previewMeta.textContent = `元: ${item.originalName} （${sizePart}${hashPart}）`;

  // Badges
  previewBadges.replaceChildren();
  const badges = [];
  if (item.isDuplicate) {
    badges.push({ cls: "pill pill--dup", text: `重複検知（同一原本: ${item.duplicateOf}）` });
  }
  if (item.isEncryptedPdf) {
    badges.push({ cls: "pill pill--warn", text: "暗号化PDF（本文抽出スキップ・手入力可）" });
  } else if (item.isLikelyScannedPdf) {
    badges.push({ cls: "pill pill--warn", text: "スキャン画像PDF（右側を見ながら手入力可）" });
  }
  if (item.invoiceId && item.invoiceIdValid === false) {
    badges.push({ cls: "pill pill--warn", text: `T番号 Mod-9不整合: ${item.invoiceId}` });
  }
  if (item.collisionSuffix) {
    badges.push({ cls: "pill pill--peer", text: `同名衝突回避サフィックス付与 (${item.collisionSuffix})` });
  }

  if (badges.length > 0) {
    previewBadges.hidden = false;
    for (const b of badges) {
      const span = document.createElement("span");
      span.className = b.cls;
      span.textContent = b.text;
      previewBadges.appendChild(span);
    }
  } else {
    previewBadges.hidden = true;
  }

  // Extracted text toggle
  const hasExtractedText = Boolean(item.extractedText && item.extractedText.trim());
  toggleExtractedTextBtn.hidden = !hasExtractedText;
  toggleExtractedTextBtn.textContent = state.showExtractedText ? "抽出テキストを閉じる" : "抽出テキスト確認";
  if (hasExtractedText && state.showExtractedText) {
    extractedTextBox.hidden = false;
    extractedTextBox.textContent = item.extractedText;
  } else {
    extractedTextBox.hidden = true;
  }

  // Main visual stage
  previewStage.replaceChildren();
  const blobUrl = ensurePreviewUrl(item);

  if (blobUrl) {
    openPreviewTabLink.hidden = false;
    openPreviewTabLink.href = blobUrl;

    if (item.extension === ".pdf" || item.mimeType === "application/pdf") {
      const obj = document.createElement("object");
      obj.className = "preview-pdf";
      obj.type = "application/pdf";
      obj.data = blobUrl;

      const iframe = document.createElement("iframe");
      iframe.className = "preview-pdf";
      iframe.src = blobUrl;
      iframe.title = `${item.originalName} プレビュー`;
      obj.appendChild(iframe);
      previewStage.appendChild(obj);
    } else if (/\.(png|jpe?g|webp|gif)$/i.test(item.extension) || item.mimeType.startsWith("image/")) {
      const img = document.createElement("img");
      img.className = "preview-img";
      img.src = blobUrl;
      img.alt = `${item.originalName} 領収書プレビュー`;
      previewStage.appendChild(img);
    } else {
      const card = document.createElement("div");
      card.className = "preview-text-card";
      card.textContent = `${item.originalName} はブラウザ直接描画非対応形式です（リネームとZIP梱包はそのまま実行できます）。`;
      previewStage.appendChild(card);
    }
  } else {
    openPreviewTabLink.hidden = true;
    const card = document.createElement("div");
    card.className = "preview-text-card";
    const heading = document.createElement("strong");
    heading.textContent = "テキスト貼り付け行（ファイル実体なし）";
    const dl = document.createElement("dl");
    const pairs = [
      ["元テキスト", item.originalName],
      ["取引日", item.date || "未検出"],
      ["取引先", item.partner || "未検出"],
      ["取引金額", item.amountYen !== null ? `${item.amountYen.toLocaleString()}円` : "未検出"],
      ["T番号", item.invoiceId ? `${item.invoiceId} (${item.invoiceIdValid ? "Mod-9妥当" : "不整合"})` : "-"],
      ["変更後ファイル名", item.standardizedFilename],
    ];
    for (const [k, v] of pairs) {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      dl.append(dt, dd);
    }
    card.append(heading, dl);
    previewStage.appendChild(card);
  }
}

function selectRow(rowId) {
  if (state.selectedId === rowId) return;
  state.selectedId = rowId;
  for (const tr of ledgerTableBody.querySelectorAll("tr[data-row-id]")) {
    tr.classList.toggle("is-selected", Number(tr.dataset.rowId) === rowId);
  }
  renderPreview();
}

async function ingestFileEntries(fileListWithHandles) {
  const validEntries = fileListWithHandles.filter(({ file }) => {
    if (!file || !file.name || file.name.startsWith(".")) return false;
    return SUPPORTED_EXT_RE.test(file.name);
  });

  if (validEntries.length === 0) {
    showNotice("対応ファイル（PDF / PNG / JPG / WebP / TIFF）が見つかりませんでした。", "warn");
    return;
  }

  let firstAddedId = null;
  for (const { file, fileHandle = null } of validEntries) {
    const buf = await file.arrayBuffer();
    const bytes = new Uint8Array(buf);
    const analyzed = await analyzeUploadedFile({
      name: file.name,
      bytes,
      mimeType: file.type || "",
      template: state.template,
      includeTNumber: state.includeTNumber,
    });

    const id = nextRowId++;
    if (firstAddedId === null) firstAddedId = id;

    state.items.push({
      id,
      ...analyzed,
      bytes,
      fileHandle,
      previewUrl: "",
      dateInput: analyzed.date,
      partnerInput: analyzed.partner,
      amountInput: analyzed.amountYen !== null ? String(analyzed.amountYen) : "",
      invoiceInput: analyzed.invoiceId,
    });
  }

  recomputeAll();
  if (firstAddedId !== null) {
    state.selectedId = firstAddedId;
  }
  renderTable();
  renderPreview();

  const dupCount = state.items.filter((i) => i.isDuplicate).length;
  const pdfExtracted = validEntries.length;
  showNotice(
    `${pdfExtracted}件のファイルをローカル読込しました${dupCount > 0 ? `（SHA-256重複検知: ${dupCount}件）` : ""}。`,
    dupCount > 0 ? "warn" : "ok",
  );
}

/**
 * Recursively collect files dropped via drag-and-drop (handles both files & folders).
 */
async function collectDroppedFiles(dataTransfer) {
  const results = [];
  const items = [...(dataTransfer.items || [])];
  const hasEntryApi = items.some((it) => typeof it.webkitGetAsEntry === "function");

  if (!hasEntryApi) {
    return [...(dataTransfer.files || [])].map((file) => ({ file }));
  }

  async function walkEntry(entry) {
    if (!entry) return;
    if (entry.isFile) {
      await new Promise((resolve) => {
        entry.file(
          (file) => {
            results.push({ file });
            resolve();
          },
          () => resolve(),
        );
      });
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      await new Promise((resolve) => {
        const readNext = () => {
          reader.readEntries(
            async (batch) => {
              if (!batch || batch.length === 0) {
                resolve();
                return;
              }
              for (const child of batch) {
                await walkEntry(child);
              }
              readNext();
            },
            () => resolve(),
          );
        };
        readNext();
      });
    }
  }

  for (const item of items) {
    const entry = item.webkitGetAsEntry();
    if (entry) {
      await walkEntry(entry);
    } else if (item.kind === "file") {
      const f = item.getAsFile();
      if (f) results.push({ file: f });
    }
  }
  return results;
}

/**
 * Render a realistic local thermal receipt PNG in-browser via Canvas2D for the live demo.
 */
async function createSyntheticReceiptPngFile() {
  const canvas = document.createElement("canvas");
  canvas.width = 460;
  canvas.height = 620;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#fcfbf7";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Subtle paper border
  ctx.strokeStyle = "#d6d3c9";
  ctx.lineWidth = 2;
  ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);

  ctx.fillStyle = "#1b232a";
  ctx.textAlign = "center";
  ctx.font = '700 24px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("領 収 書", 230, 76);

  ctx.font = '700 18px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("田中商店（文具・オフィス用品）", 230, 118);

  ctx.font = '13px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillStyle = "#48545e";
  ctx.fillText("東京都千代田区神田小川町2-4-1", 230, 144);
  ctx.fillText("TEL: 03-5555-0192", 230, 166);
  ctx.fillText("登録番号: T7000012050002", 230, 190);

  // Dashed divider
  ctx.strokeStyle = "#8a96a0";
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(42, 214);
  ctx.lineTo(418, 214);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.textAlign = "left";
  ctx.fillStyle = "#1b232a";
  ctx.font = '14px ui-monospace, Menlo, monospace';
  ctx.fillText("日時: 2026/11/15 14:22", 46, 248);
  ctx.fillText("担当: 04  レジ#02", 46, 272);

  ctx.font = '15px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("コピー用紙 A4 5冊パック", 46, 320);
  ctx.fillText("ファイルバインダー 10冊", 46, 352);

  ctx.textAlign = "right";
  ctx.font = '15px ui-monospace, Menlo, monospace';
  ctx.fillText("¥3,800", 414, 320);
  ctx.fillText("¥4,200", 414, 352);

  ctx.strokeStyle = "#8a96a0";
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(42, 378);
  ctx.lineTo(418, 378);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.textAlign = "left";
  ctx.font = '14px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("小計（10%対象）", 46, 412);
  ctx.fillText("消費税（10%）", 46, 440);

  ctx.textAlign = "right";
  ctx.font = '14px ui-monospace, Menlo, monospace';
  ctx.fillText("¥8,000", 414, 412);
  ctx.fillText("¥800", 414, 440);

  // Total highlight
  ctx.fillStyle = "#edf2f6";
  ctx.fillRect(42, 462, 376, 48);
  ctx.fillStyle = "#162028";
  ctx.textAlign = "left";
  ctx.font = '700 18px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("合計（税込）", 56, 493);
  ctx.textAlign = "right";
  ctx.font = '700 22px ui-monospace, Menlo, monospace';
  ctx.fillText("¥8,800", 404, 494);

  ctx.textAlign = "center";
  ctx.fillStyle = "#5c6872";
  ctx.font = '12px "Hiragino Sans", "Yu Gothic", sans-serif';
  ctx.fillText("※右プレビューを見ながら左の表へ手入力するデモ用画像です", 230, 560);

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return new File([blob], "IMG_4821.png", { type: "image/png" });
}

async function loadSyntheticDemoInvoices() {
  loadDemoPdfsBtn.disabled = true;
  try {
    const pdf1Bytes = await createSyntheticInvoicePdfBytes({
      docType: "御請求書",
      invoiceNumber: "INV-2026-1101",
      issueDate: "令和8年11月19日",
      partnerName: "株式会社サンプル商事",
      recipientName: "合同会社ホライゾンラボ 御中",
      amountYen: 110000,
      invoiceId: "T7000012050002",
      itemDescription: "クラウド業務基盤 月額利用料（11月分）",
      compress: true,
    });

    const pdf2Bytes = await createSyntheticInvoicePdfBytes({
      docType: "御請求書",
      invoiceNumber: "INV-2026-1108",
      issueDate: "2026年11月12日",
      partnerName: "合同会社クラウド保守テック",
      recipientName: "合同会社ホライゾンラボ 御中",
      amountYen: 55000,
      invoiceId: "T1234567890123", // Deliberately invalid Mod-9 check digit for audit demo
      itemDescription: "サーバー監視・セキュリティ保守委託費",
      compress: true,
    });

    const receiptPngFile = await createSyntheticReceiptPngFile();

    const demoFiles = [
      { file: new File([pdf1Bytes], "invoice_download_001.pdf", { type: "application/pdf" }) },
      { file: new File([pdf2Bytes], "download_202611.pdf", { type: "application/pdf" }) },
      {
        file: new File([new Uint8Array(pdf1Bytes)], "invoice_download_001_copy.pdf", {
          type: "application/pdf",
        }),
      },
      { file: receiptPngFile },
    ];

    revokeAllPreviewUrls();
    state.items = [];
    state.fsDirHandle = null;
    state.lastUndoOps = [];
    directFsBanner.hidden = true;
    await ingestFileEntries(demoFiles);
    showNotice(
      "合成デモ証憑4件を読込済：PDF本文からの自動抽出（和暦・T番号Mod-9検算）、SHA-256重複検知、画像プレビューをお試しください。",
      "ok",
    );
  } finally {
    loadDemoPdfsBtn.disabled = false;
  }
}

// File System Access API Direct Folder Rename (Chrome / Edge)
async function openDirectFolder() {
  if (typeof window.showDirectoryPicker !== "function") {
    showNotice(
      "このブラウザは File System Access API（ローカルフォルダ直接書換）非対応です。上の「フォルダ一括読込」と「ZIP一括保存」をご利用ください。",
      "warn",
    );
    return;
  }
  try {
    const dirHandle = await window.showDirectoryPicker({ mode: "readwrite" });
    const entries = [];
    for await (const handle of dirHandle.values()) {
      if (handle.kind !== "file") continue;
      if (handle.name.startsWith(".") || handle.name === STUDIO_CSV_FILENAME || handle.name === "undo_rename.json") {
        continue;
      }
      if (!SUPPORTED_EXT_RE.test(handle.name)) continue;
      const file = await handle.getFile();
      entries.push({ file, fileHandle: handle });
    }

    if (entries.length === 0) {
      showNotice("選択したフォルダ内に対象のPDF・画像ファイルがありませんでした。", "warn");
      return;
    }

    revokeAllPreviewUrls();
    state.items = [];
    state.fsDirHandle = dirHandle;
    state.lastUndoOps = [];
    await ingestFileEntries(entries);

    directFsLabel.textContent = `接続フォルダ: ${dirHandle.name}`;
    directFsDetail.innerHTML =
      "一覧で日付・取引先・金額を確認後、そのままローカルフォルダへ安全にリネーム適用できます（<code>undo_rename.json</code> 自動保存）。";
    undoDirectRenameBtn.hidden = true;
    directFsBanner.hidden = false;
  } catch (err) {
    if (err && err.name === "AbortError") return;
    showNotice(`フォルダ接続に失敗しました: ${err?.message || err}`, "err");
  }
}

async function writeTextToDirHandle(dirHandle, filename, content) {
  const fh = await dirHandle.getFileHandle(filename, { create: true });
  const writable = await fh.createWritable();
  await writable.write(content);
  await writable.close();
}

async function renameFileInDirHandle(dirHandle, item, targetName) {
  if (item.fileHandle && typeof item.fileHandle.move === "function") {
    await item.fileHandle.move(targetName);
    return;
  }
  const newHandle = await dirHandle.getFileHandle(targetName, { create: true });
  const writable = await newHandle.createWritable();
  await writable.write(item.bytes);
  await writable.close();
  await dirHandle.removeEntry(item.originalName);
  item.fileHandle = newHandle;
}

async function applyDirectFolderRename() {
  if (!state.fsDirHandle) return;
  recomputeAll();
  const dirHandle = state.fsDirHandle;
  const operations = [];

  applyDirectRenameBtn.disabled = true;
  try {
    for (const item of state.items) {
      if (!item.fileHandle) continue;
      if (item.standardizedFilename === item.originalName) continue;
      const prevName = item.originalName;
      const nextName = item.standardizedFilename;
      await renameFileInDirHandle(dirHandle, item, nextName);
      operations.push({ from: prevName, to: nextName, sha256: item.sha256 });
      item.originalName = nextName;
    }

    const csvContent = buildStudioIndexCsv(state.items);
    const kiteiContent = generateJimuShoriKitei(getKiteiOptions());
    await writeTextToDirHandle(dirHandle, STUDIO_CSV_FILENAME, csvContent);
    await writeTextToDirHandle(dirHandle, STUDIO_KITEI_FILENAME, kiteiContent);

    const undoPayload = {
      tool: "DENCHOGATE Studio v2.0",
      executedAt: new Date().toISOString(),
      directory: dirHandle.name,
      operations,
    };
    await writeTextToDirHandle(dirHandle, "undo_rename.json", JSON.stringify(undoPayload, null, 2));

    state.lastUndoOps = operations;
    undoDirectRenameBtn.hidden = operations.length === 0;
    recomputeAll();
    renderTable();
    renderPreview();
    showNotice(
      `ローカルフォルダ「${dirHandle.name}」へ直接リネーム完了（${operations.length}件改名＋索引簿CSV・事務処理規程・undo_rename.json を保存）。`,
      "ok",
    );
  } catch (err) {
    showNotice(`直接リネーム中にエラーが発生しました: ${err?.message || err}`, "err");
  } finally {
    applyDirectRenameBtn.disabled = false;
  }
}

async function rollbackDirectFolderRename() {
  if (!state.fsDirHandle || state.lastUndoOps.length === 0) return;
  const dirHandle = state.fsDirHandle;
  let restored = 0;

  undoDirectRenameBtn.disabled = true;
  try {
    for (const op of [...state.lastUndoOps].reverse()) {
      const item = state.items.find((it) => it.originalName === op.to);
      if (!item || !item.fileHandle) continue;
      await renameFileInDirHandle(dirHandle, item, op.from);
      item.originalName = op.from;
      restored += 1;
    }
    state.lastUndoOps = [];
    undoDirectRenameBtn.hidden = true;
    recomputeAll();
    renderTable();
    renderPreview();
    showNotice(`直前のリネーム ${restored}件 を元のファイル名へロールバックしました。`, "ok");
  } catch (err) {
    showNotice(`ロールバックに失敗しました: ${err?.message || err}`, "err");
  } finally {
    undoDirectRenameBtn.disabled = false;
  }
}

// Paste-Filename Fallback Import
function importPastedLines() {
  const lines = String(pasteInput.value || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    showNotice("取り込むファイル名・明細行を入力してください。", "warn");
    return;
  }

  let firstId = null;
  for (const line of lines) {
    const rec = normalizeDenchoRecord(line);
    const extMatch = line.match(/(\.(?:pdf|png|jpe?g|webp|tiff?))$/i);
    const extension = extMatch ? extMatch[1].toLowerCase() : ".pdf";
    const id = nextRowId++;
    if (firstId === null) firstId = id;

    state.items.push({
      id,
      originalName: rec.original,
      extension,
      mimeType: "text/plain",
      sizeBytes: 0,
      bytes: null,
      fileHandle: null,
      previewUrl: "",
      sha256: "",
      sha256Short: "",
      extractedText: "",
      isEncryptedPdf: false,
      isLikelyScannedPdf: false,
      extractionWarnings: [],
      primarySource: "filename",
      sources: {},
      dateInput: rec.date,
      partnerInput: rec.partner,
      amountInput: rec.amountYen !== null ? String(rec.amountYen) : "",
      invoiceInput: rec.invoiceId,
      date: rec.date,
      partner: rec.partner,
      amountYen: rec.amountYen,
      invoiceId: rec.invoiceId,
      invoiceIdValid: rec.invoiceIdValid,
      standardizedFilename: rec.standardizedFilename,
      missingKeys: rec.missingKeys,
      compliant: rec.compliant,
      collisionSuffix: "",
      isDuplicate: false,
      hasDuplicatePeer: false,
      duplicateOf: "",
      duplicateGroupSize: 1,
    });
  }

  recomputeAll();
  if (firstId !== null) state.selectedId = firstId;
  renderTable();
  renderPreview();
  showNotice(`${lines.length}件のテキスト明細を一覧へ取り込みました（索引簿CSV出力・手動編集が可能）。`, "ok");
}

// Event Listeners — Dropzone & File Inputs
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("is-dragover");
});

dropzone.addEventListener("dragleave", (e) => {
  if (!dropzone.contains(e.relatedTarget)) {
    dropzone.classList.remove("is-dragover");
  }
});

dropzone.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropzone.classList.remove("is-dragover");
  const dropped = await collectDroppedFiles(e.dataTransfer);
  await ingestFileEntries(dropped);
});

fileInput.addEventListener("change", async () => {
  const files = [...(fileInput.files || [])].map((file) => ({ file }));
  fileInput.value = "";
  await ingestFileEntries(files);
});

folderInput.addEventListener("change", async () => {
  const files = [...(folderInput.files || [])].map((file) => ({ file }));
  folderInput.value = "";
  await ingestFileEntries(files);
});

fsDirectBtn.addEventListener("click", openDirectFolder);
applyDirectRenameBtn.addEventListener("click", applyDirectFolderRename);
undoDirectRenameBtn.addEventListener("click", rollbackDirectFolderRename);
disconnectFsBtn.addEventListener("click", () => {
  state.fsDirHandle = null;
  state.lastUndoOps = [];
  directFsBanner.hidden = true;
});

loadDemoPdfsBtn.addEventListener("click", loadSyntheticDemoInvoices);

togglePasteModeBtn.addEventListener("click", () => {
  const nextHidden = !pasteModeDrawer.hidden;
  pasteModeDrawer.hidden = nextHidden;
  togglePasteModeBtn.setAttribute("aria-expanded", String(!nextHidden));
});

fillPasteSampleBtn.addEventListener("click", () => {
  pasteInput.value = SAMPLE_PASTE_LINES;
});

importPasteLinesBtn.addEventListener("click", importPastedLines);

// Toolbar controls
templateSelect.addEventListener("change", () => {
  state.template = templateSelect.value;
  recomputeAll();
  syncComputedCellsInPlace();
});

includeTNumberCheck.addEventListener("change", () => {
  state.includeTNumber = includeTNumberCheck.checked;
  recomputeAll();
  syncComputedCellsInPlace();
});

excludeDupZipCheck.addEventListener("change", () => {
  state.excludeDuplicatesInZip = excludeDupZipCheck.checked;
});

downloadZipBtn.addEventListener("click", () => {
  if (state.items.length === 0) return;
  recomputeAll();
  const pkg = buildDenchoZipPackage({
    records: state.items,
    kiteiOptions: getKiteiOptions(),
    includeDuplicates: !state.excludeDuplicatesInZip,
  });
  const zipFilename = `DENCHOGATE_電帳法保存パッケージ_${getTodayCompact()}.zip`;
  triggerBlobDownload(new Blob([pkg.zipBytes], { type: "application/zip" }), zipFilename);
  showNotice(
    `ZIP梱包完了：${zipFilename}（証憑${pkg.binaryFileCount}件＋索引簿CSV＋事務処理規程 / 合計 ${formatBytes(pkg.zipBytes.byteLength)}${pkg.excludedDuplicatesCount > 0 ? ` / 重複${pkg.excludedDuplicatesCount}件を除外` : ""}）`,
    "ok",
  );
});

downloadCsvBtn.addEventListener("click", () => {
  if (state.items.length === 0) return;
  recomputeAll();
  const csv = buildStudioIndexCsv(state.items);
  triggerBlobDownload(new Blob([csv], { type: "text/csv;charset=utf-8" }), STUDIO_CSV_FILENAME);
  showNotice(`国税庁検索要件準拠の索引簿CSV（${STUDIO_CSV_FILENAME}・UTF-8 BOM）を保存しました。`, "ok");
});

clearAllBtn.addEventListener("click", () => {
  revokeAllPreviewUrls();
  state.items = [];
  state.selectedId = null;
  state.fsDirHandle = null;
  state.lastUndoOps = [];
  directFsBanner.hidden = true;
  renderTable();
  renderPreview();
  showNotice("");
});

// Filter tabs
for (const tab of filterTabs) {
  tab.addEventListener("click", () => {
    state.filter = tab.dataset.filter || "all";
    for (const t of filterTabs) {
      const active = t === tab;
      t.classList.toggle("is-active", active);
      t.setAttribute("aria-selected", String(active));
    }
    renderTable();
  });
}

// Table delegation — Row selection, inline editing, keyboard speed
ledgerTableBody.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-row-id]");
  if (!tr) return;
  const rowId = Number(tr.dataset.rowId);

  if (e.target.closest('[data-action="delete"]')) {
    const idx = state.items.findIndex((it) => it.id === rowId);
    if (idx >= 0) {
      revokeItemPreviewUrl(state.items[idx]);
      state.items.splice(idx, 1);
      if (state.selectedId === rowId) {
        state.selectedId = state.items[Math.min(idx, state.items.length - 1)]?.id ?? null;
      }
      recomputeAll();
      renderTable();
      renderPreview();
    }
    return;
  }

  selectRow(rowId);
});

ledgerTableBody.addEventListener("focusin", (e) => {
  const tr = e.target.closest("tr[data-row-id]");
  if (!tr) return;
  selectRow(Number(tr.dataset.rowId));
});

ledgerTableBody.addEventListener("input", (e) => {
  const input = e.target.closest("input[data-field]");
  const tr = e.target.closest("tr[data-row-id]");
  if (!input || !tr) return;
  const item = state.items.find((it) => it.id === Number(tr.dataset.rowId));
  if (!item) return;

  const field = input.dataset.field;
  if (field === "date") item.dateInput = input.value;
  else if (field === "partner") item.partnerInput = input.value;
  else if (field === "amount") item.amountInput = input.value;
  else if (field === "invoiceId") item.invoiceInput = input.value;

  item.primarySource = "manual";
  recomputeAll();
  syncComputedCellsInPlace();
});

ledgerTableBody.addEventListener("focusout", (e) => {
  const input = e.target.closest("input[data-field]");
  const tr = e.target.closest("tr[data-row-id]");
  if (!input || !tr) return;
  const item = state.items.find((it) => it.id === Number(tr.dataset.rowId));
  if (!item) return;

  if (input.dataset.field === "date" && input.value.trim()) {
    const parsed = parseJapaneseOrIsoDate(input.value);
    if (parsed.yyyymmdd) {
      item.dateInput = parsed.yyyymmdd;
      input.value = parsed.yyyymmdd;
      recomputeAll();
      syncComputedCellsInPlace();
    }
  } else if (input.dataset.field === "invoiceId" && input.value.trim()) {
    const tCheck = verifyInvoiceTNumber(input.value);
    if (tCheck.present) {
      item.invoiceInput = tCheck.normalized;
      input.value = tCheck.normalized;
      recomputeAll();
      syncComputedCellsInPlace();
    }
  }
});

ledgerTableBody.addEventListener("keydown", (e) => {
  const input = e.target.closest("input[data-field]");
  const tr = e.target.closest("tr[data-row-id]");
  if (!input || !tr) return;

  if (e.key === "Enter" && !e.isComposing) {
    e.preventDefault();
    const field = input.dataset.field;
    const nextRow = tr.nextElementSibling;
    if (nextRow) {
      const nextInput = nextRow.querySelector(`input[data-field="${field}"]`);
      if (nextInput) {
        nextInput.focus();
        nextInput.select();
      }
    }
  } else if (e.altKey && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
    e.preventDefault();
    const field = input.dataset.field;
    const sibling = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
    if (sibling) {
      const targetInput = sibling.querySelector(`input[data-field="${field}"]`);
      if (targetInput) {
        targetInput.focus();
        targetInput.select();
      }
    }
  }
});

toggleExtractedTextBtn.addEventListener("click", () => {
  state.showExtractedText = !state.showExtractedText;
  renderPreview();
});

// Workflow Auditor
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

// Jimu Shori Kitei Generator
function updateKitei() {
  kiteiPreview.textContent = generateJimuShoriKitei(getKiteiOptions());
}

[companyInput, managerInput, effectiveDateInput].forEach((el) =>
  el.addEventListener("input", updateKitei),
);

document.getElementById("downloadKiteiBtn").addEventListener("click", () => {
  updateKitei();
  triggerBlobDownload(
    new Blob([kiteiPreview.textContent], { type: "text/markdown;charset=utf-8" }),
    STUDIO_KITEI_FILENAME,
  );
});

// Clean up Blob URLs on unload
window.addEventListener("beforeunload", revokeAllPreviewUrls);

// Initial UI setup
if (typeof window.showDirectoryPicker === "function") {
  fsSupportHint.textContent = "Chrome/Edge検知：ローカルフォルダ直接リネーム対応";
} else {
  fsSupportHint.textContent = "ZIP一括保存は全ブラウザ対応（直接書換はChrome/Edge対応）";
}

workflowInput.value = RISKY_WORKFLOW;
renderFlowAudit();
updateKitei();
renderTable();
renderPreview();
