import {
  BANK_PRESETS,
  TRANSFER_TYPES,
  decodeZenginBytes,
  diagnoseAndRepairZenginFile,
  encodeZenginShiftJis,
  generateZengin120FromRows,
  parseTransferCsv,
  toZenginHalfWidth,
  validateHeader,
  validateTransferRow,
  validateTransferRows,
  verifyBatchIdentifiers,
} from "./core/zengin-engine.mjs";

const PROFILE_STORAGE_KEY = "zengingate_v2_requester_profile";

const CLEAN_SAMPLE_CSV = [
  "振込先金融機関コード,銀行名,支店コード,支店名,預金種目,口座番号,受取人名義,振込金額,EDI情報,T番号",
  '0005,ﾐﾂﾋﾞｼUFJ,001,ﾎﾝﾃﾝ,普通,1234567,"株式会社テストサプライ","¥125,000","INV-2026-01",T7000012050002',
  '0009,ﾐﾂｲｽﾐﾄﾓ,200,ｼﾝｼﾞﾕｸ,当座,7654321,"ホライゾン合同会社","48,500円","INV-2026-02",',
  '0036,ﾗｸﾃﾝ,201,ｼﾞﾔｽﾞ,普通,0098765,"サトウ ハナコ","32,000","",',
  '0001,ﾐｽﾞﾎ,005,ﾄｳｷﾖｳ,普通,0045678,"税理士法人ぎょうせい","165,000","TAX-11",T7000012050002',
].join("\r\n");

const DIRTY_DEMO_CSV = [
  "振込先金融機関コード,銀行名,支店コード,支店名,預金種目,口座番号,取引先名,振込金額,EDI情報,T番号",
  '5,,1,本店,普通,12345,"株式会社テストサプライ","¥125,000","INV-001",T7000012050002',
  '9,,200,ｼﾝｼﾞﾕｸ,当座,7654321,"株式会社田中商事","48,500円","INV-002",T8000012050002',
  '36,,201,ｼﾞﾔｽﾞ,普通,98765,"ｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱｱガ","32,000","",',
].join("\r\n");

const DEFAULT_PROFILE = {
  preset: "mufg",
  transferType: "21",
  lineEnding: "CRLF",
  includeEof: false,
  clearingHouseCode: "    ",
  requesterCode: "0000123456",
  requesterName: "株式会社ホライゾン",
  transferDateMMDD: "1125",
  bankCode: "0005",
  bankName: "ﾐﾂﾋﾞｼUFJ",
  branchCode: "001",
  branchName: "ﾎﾝﾃﾝ",
  accountType: "1",
  accountNumber: "1234567",
};

const state = {
  activeTab: "builder",
  filterMode: "all", // "all" | "errors"
  inspectorMode: "ruler", // "ruler" | "hex"
  profile: { ...DEFAULT_PROFILE },
  rows: [],
  lastImportRepairs: [],
  lastDetectedCsvPreset: "",
  lastGen: null,
  lastHeaderValidation: null,
  lastRowsValidation: null,
  lastRepairResult: null,
  lastInvoiceBatch: null,
  sha256Hex: "",
};

// -------------------- DOM References --------------------
const $ = (id) => document.getElementById(id);

const tabButtons = Array.from(document.querySelectorAll(".tab[data-tab]"));
const tabPanels = {
  builder: $("panel-builder"),
  repair: $("panel-repair"),
  invoice: $("panel-invoice"),
  sheet: $("panel-sheet"),
};

const tabErrorBadge = $("tabErrorBadge");
const builderHeadlineStatus = $("builderHeadlineStatus");
const openPrintSheetBtn = $("openPrintSheetBtn");
const downloadZenginBtn = $("downloadZenginBtn");

const kpiTotalAmount = $("kpiTotalAmount");
const kpiTransferMeta = $("kpiTransferMeta");
const kpiRowCount = $("kpiRowCount");
const kpiRowHealth = $("kpiRowHealth");
const kpiByteCheck = $("kpiByteCheck");
const kpiByteSub = $("kpiByteSub");
const kpiPresetLabel = $("kpiPresetLabel");
const kpiSpecDetail = $("kpiSpecDetail");

const csvDropzone = $("csvDropzone");
const csvFileInput = $("csvFileInput");
const pickCsvFileBtn = $("pickCsvFileBtn");
const loadSampleCsvBtn = $("loadSampleCsvBtn");
const loadDirtySampleBtn = $("loadDirtySampleBtn");
const togglePasteCsvBtn = $("togglePasteCsvBtn");
const csvPasteDrawer = $("csvPasteDrawer");
const csvRowsInput = $("csvRowsInput");
const applyPasteCsvBtn = $("applyPasteCsvBtn");

const bankPresetSelect = $("bankPresetSelect");
const transferTypeSelect = $("transferTypeSelect");
const lineEndingSelect = $("lineEndingSelect");
const clearingHouseSelect = $("clearingHouseSelect");
const includeEofCheckbox = $("includeEofCheckbox");
const presetNoteText = $("presetNoteText");

const profileSummaryText = $("profileSummaryText");
const profileSavedBadge = $("profileSavedBadge");
const reqCodeInput = $("reqCodeInput");
const reqNameInput = $("reqNameInput");
const reqNamePreview = $("reqNamePreview");
const transferDateInput = $("transferDateInput");
const srcBankCodeInput = $("srcBankCodeInput");
const srcBankNameInput = $("srcBankNameInput");
const srcBranchCodeInput = $("srcBranchCodeInput");
const srcBranchNameInput = $("srcBranchNameInput");
const srcAcctTypeInput = $("srcAcctTypeInput");
const srcAcctNumInput = $("srcAcctNumInput");
const saveProfileBtn = $("saveProfileBtn");
const exportProfileJsonBtn = $("exportProfileJsonBtn");
const importProfileJsonBtn = $("importProfileJsonBtn");
const importProfileFileInput = $("importProfileFileInput");
const headerErrorInline = $("headerErrorInline");

const importRepairBanner = $("importRepairBanner");
const filterAllBtn = $("filterAllBtn");
const filterErrorsBtn = $("filterErrorsBtn");
const addRowBtn = $("addRowBtn");
const clearRowsBtn = $("clearRowsBtn");
const transferTableBody = $("transferTableBody");

const inspectorByteBadge = $("inspectorByteBadge");
const inspectorModeRulerBtn = $("inspectorModeRulerBtn");
const inspectorModeHexBtn = $("inspectorModeHexBtn");
const copyZenginTextBtn = $("copyZenginTextBtn");
const genSummary = $("genSummary");
const byteRulerContainer = $("byteRulerContainer");

// Repair tab
const repairDropzone = $("repairDropzone");
const repairFileInput = $("repairFileInput");
const pickRepairFileBtn = $("pickRepairFileBtn");
const loadBrokenSampleBtn = $("loadBrokenSampleBtn");
const repairPresetSelect = $("repairPresetSelect");
const zenginRawInput = $("zenginRawInput");
const auditZenginBtn = $("auditZenginBtn");
const repairSendToBuilderBtn = $("repairSendToBuilderBtn");
const downloadRepairedBtn = $("downloadRepairedBtn");
const repairForensicsStrip = $("repairForensicsStrip");
const repSrcEncoding = $("repSrcEncoding");
const repSrcBom = $("repSrcBom");
const repFixedCount = $("repFixedCount");
const repBlockingCount = $("repBlockingCount");
const repTotalAmount = $("repTotalAmount");
const repRowCount = $("repRowCount");
const repByteStatus = $("repByteStatus");
const repByteTotal = $("repByteTotal");
const zenginAuditOutput = $("zenginAuditOutput");
const repairDiagnosticsList = $("repairDiagnosticsList");
const repairPreviewCode = $("repairPreviewCode");

// Invoice tab
const idsInput = $("idsInput");
const checkIdsBtn = $("checkIdsBtn");
const exportInvoiceCsvBtn = $("exportInvoiceCsvBtn");
const invTotalCount = $("invTotalCount");
const invValidCount = $("invValidCount");
const invInvalidCount = $("invInvalidCount");
const idsTableBody = $("idsTableBody");

// Approval Sheet tab
const printApprovalSheetBtn = $("printApprovalSheetBtn");
const sheetSubtitle = $("sheetSubtitle");
const sheetMetaGrid = $("sheetMetaGrid");
const sheetErrorWarning = $("sheetErrorWarning");
const sheetTableBody = $("sheetTableBody");
const sheetFooterCount = $("sheetFooterCount");
const sheetFooterTotal = $("sheetFooterTotal");
const sheetFooterIntegrity = $("sheetFooterIntegrity");
const sheetSha256 = $("sheetSha256");

// -------------------- Helpers --------------------
function formatYen(n) {
  const num = Number(n);
  if (!Number.isFinite(num)) return "¥0";
  return `¥${Math.round(num).toLocaleString("ja-JP")}`;
}

function triggerBinaryDownload(uint8Array, filename) {
  // Strictly emit raw Shift-JIS (CP932) Uint8Array bytes — NEVER UTF-8 string Blob!
  const blob = new Blob([uint8Array], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function triggerTextDownload(text, filename, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function computeSha256Hex(uint8Array) {
  if (!uint8Array || uint8Array.length === 0) return "";
  if (globalThis.crypto && globalThis.crypto.subtle) {
    try {
      const digest = await globalThis.crypto.subtle.digest("SHA-256", uint8Array);
      return Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    } catch {
      // Fallback when crypto.subtle is blocked on insecure file:// origin
    }
  }
  return `LOCAL-SIZE-${uint8Array.length}B`;
}

function switchTab(tabId) {
  if (!tabPanels[tabId]) return;
  state.activeTab = tabId;
  for (const btn of tabButtons) {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const [id, panel] of Object.entries(tabPanels)) {
    panel.classList.toggle("is-active", id === tabId);
  }
  if (tabId === "sheet") {
    renderApprovalSheet();
  }
}

// -------------------- Profile Persistence --------------------
function loadSavedProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      state.profile = { ...DEFAULT_PROFILE, ...parsed };
    }
  } catch {
    // Ignore storage access errors in restricted environments
  }
}

function saveProfileToStorage(showNotice = false) {
  try {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(state.profile));
    if (showNotice) {
      profileSavedBadge.textContent = "保存完了";
      profileSavedBadge.className = "badge badge--ok";
      setTimeout(() => {
        profileSavedBadge.textContent = "ブラウザ自動保存";
        profileSavedBadge.className = "badge badge--neutral";
      }, 1800);
    }
  } catch {
    profileSavedBadge.textContent = "ローカル保存不可";
    profileSavedBadge.className = "badge badge--warn";
  }
}

function syncProfileInputsFromState() {
  const p = state.profile;
  bankPresetSelect.value = BANK_PRESETS[p.preset] ? p.preset : "standard";
  transferTypeSelect.value = TRANSFER_TYPES[p.transferType] ? p.transferType : "21";
  lineEndingSelect.value = p.lineEnding === "NONE" ? "NONE" : "CRLF";
  clearingHouseSelect.value = p.clearingHouseCode === "0000" ? "0000" : "    ";
  includeEofCheckbox.checked = Boolean(p.includeEof);
  reqCodeInput.value = p.requesterCode;
  reqNameInput.value = p.requesterName;
  transferDateInput.value = p.transferDateMMDD;
  srcBankCodeInput.value = p.bankCode;
  srcBankNameInput.value = p.bankName;
  srcBranchCodeInput.value = p.branchCode;
  srcBranchNameInput.value = p.branchName;
  srcAcctTypeInput.value = p.accountType;
  srcAcctNumInput.value = p.accountNumber;
  updatePresetNote();
}

function readProfileInputsIntoState() {
  state.profile.preset = bankPresetSelect.value;
  state.profile.transferType = transferTypeSelect.value;
  state.profile.lineEnding = lineEndingSelect.value;
  state.profile.clearingHouseCode = clearingHouseSelect.value;
  state.profile.includeEof = includeEofCheckbox.checked;
  state.profile.requesterCode = reqCodeInput.value;
  state.profile.requesterName = reqNameInput.value;
  state.profile.transferDateMMDD = transferDateInput.value;
  state.profile.bankCode = srcBankCodeInput.value;
  state.profile.bankName = srcBankNameInput.value;
  state.profile.branchCode = srcBranchCodeInput.value;
  state.profile.branchName = srcBranchNameInput.value;
  state.profile.accountType = srcAcctTypeInput.value;
  state.profile.accountNumber = srcAcctNumInput.value;
}

function updatePresetNote() {
  const preset = BANK_PRESETS[state.profile.preset] ?? BANK_PRESETS.standard;
  presetNoteText.textContent = preset.note;
}

function applyBankPreset(presetId) {
  const preset = BANK_PRESETS[presetId] ?? BANK_PRESETS.standard;
  state.profile.preset = preset.id;
  state.profile.lineEnding = preset.lineEnding;
  state.profile.includeEof = preset.includeEof;
  state.profile.clearingHouseCode = preset.clearingHouseCode;
  lineEndingSelect.value = preset.lineEnding;
  includeEofCheckbox.checked = preset.includeEof;
  clearingHouseSelect.value = preset.clearingHouseCode;
  updatePresetNote();
  saveProfileToStorage(false);
  recomputeAndRenderOutputs();
}

// -------------------- CSV / File Import --------------------
function loadCsvTextIntoWorkbench(rawText, sourceLabel = "") {
  const parsed = parseTransferCsv(rawText);
  state.rows = parsed.rows;
  state.lastImportRepairs = parsed.autoRepairs;
  state.lastDetectedCsvPreset = parsed.detectedPreset;
  csvRowsInput.value = rawText;

  if (parsed.autoRepairs.length > 0 || sourceLabel) {
    const repairSummary =
      parsed.autoRepairs.length > 0
        ? `自動補正 ${parsed.autoRepairs.length} 件適用（先頭0補完・金額カンマ除去・預金種目正規化）`
        : "補正不要で読み込み完了";
    const presetTag = parsed.hasHeader ? `ヘッダ自動判定: ${parsed.detectedPreset}` : "ヘッダなし8列形式";
    importRepairBanner.textContent = `${sourceLabel ? `[${sourceLabel}] ` : ""}${parsed.rows.length} 件読込（${presetTag}）— ${repairSummary}`;
    importRepairBanner.classList.remove("is-hidden");
  } else {
    importRepairBanner.classList.add("is-hidden");
  }

  renderTransferTable();
  recomputeAndRenderOutputs();
}

async function handleMainFileDropOrPick(file) {
  if (!file) return;
  const buf = await file.arrayBuffer();
  const decoded = decodeZenginBytes(new Uint8Array(buf));
  const trimmed = decoded.text.trimStart();

  // If user dropped an existing Zengin fixed-width file (.txt starting with 1210/1110/1120), route straight to Repair tab!
  if (/^1(21|11|12)0/.test(trimmed) && !trimmed.includes(",")) {
    repairPresetSelect.value = state.profile.preset;
    runRepairFromInput(new Uint8Array(buf), file.name);
    switchTab("repair");
    return;
  }

  loadCsvTextIntoWorkbench(decoded.text, `${file.name} / ${decoded.encoding.toUpperCase()}`);
}

// -------------------- Interactive Table Rendering (IME-Safe) --------------------
function createCellInput({ value, cls = "", maxLength, placeholder = "", ariaLabel, onInput }) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = `cell-input ${cls}`.trim();
  input.value = value ?? "";
  if (maxLength) input.maxLength = maxLength;
  if (placeholder) input.placeholder = placeholder;
  if (ariaLabel) input.setAttribute("aria-label", ariaLabel);
  input.addEventListener("input", () => onInput(input.value));
  return input;
}

function updateRowDomValidation(tr, row, v) {
  tr.classList.toggle("row-has-err", v.hasErrors);

  const dot = tr.querySelector("[data-role='dot']");
  if (dot) {
    dot.className = v.hasErrors
      ? "status-dot is-err"
      : v.warnings.length > 0
        ? "status-dot is-warn"
        : "status-dot";
  }

  const fieldMap = ["bankCode", "branchCode", "accountType", "accountNumber", "recipientName", "amount", "ediInfo", "invoiceId"];
  for (const f of fieldMap) {
    const el = tr.querySelector(`[data-field='${f}']`);
    if (el) {
      el.classList.toggle("is-err", Boolean(v.fieldErrors[f]));
      el.title = v.fieldErrors[f] || "";
    }
  }

  const payeePreviewEl = tr.querySelector("[data-role='payee-preview']");
  if (payeePreviewEl) {
    const rc = v.recipientPreview;
    if (v.fieldErrors.recipientName) {
      payeePreviewEl.className = "cell-sub is-err";
      payeePreviewEl.textContent = v.fieldErrors.recipientName;
    } else if (rc.truncated) {
      payeePreviewEl.className = "cell-sub is-warn";
      payeePreviewEl.textContent = `${rc.zenginText} · ${rc.byteLength}/30B (${rc.dakutenSafeAdjusted ? "濁点保護切捨" : "30B切捨"})`;
    } else {
      payeePreviewEl.className = "cell-sub is-ok";
      payeePreviewEl.textContent = `${rc.zenginText || "(空)"} · ${rc.byteLength}/30B`;
    }
  }

  const amtNoteEl = tr.querySelector("[data-role='amt-note']");
  if (amtNoteEl) {
    if (v.fieldErrors.amount) {
      amtNoteEl.className = "cell-sub is-err";
      amtNoteEl.textContent = v.fieldErrors.amount;
    } else {
      amtNoteEl.className = "cell-sub";
      amtNoteEl.textContent = v.parsedAmount !== null ? formatYen(v.parsedAmount) : "";
    }
  }

  const ediNoteEl = tr.querySelector("[data-role='edi-note']");
  if (ediNoteEl) {
    if (v.fieldErrors.ediInfo) {
      ediNoteEl.className = "cell-sub is-err";
      ediNoteEl.textContent = v.fieldErrors.ediInfo;
    } else if (v.ediPreview.zenginText.trim().length > 0) {
      ediNoteEl.className = "cell-sub is-ok";
      ediNoteEl.textContent = `識別Y付与 · ${v.ediPreview.byteLength}/20B`;
    } else {
      ediNoteEl.className = "cell-sub";
      ediNoteEl.textContent = "任意(Pos92-111)";
    }
  }

  const invNoteEl = tr.querySelector("[data-role='inv-note']");
  if (invNoteEl) {
    if (v.fieldErrors.invoiceId) {
      invNoteEl.className = "cell-sub is-err";
      invNoteEl.textContent = v.fieldErrors.invoiceId;
    } else if (v.invoiceCheck && v.invoiceCheck.valid) {
      invNoteEl.className = "cell-sub is-ok";
      invNoteEl.textContent = `Mod-9 適格 (${v.invoiceCheck.normalized})`;
    } else {
      invNoteEl.className = "cell-sub";
      invNoteEl.textContent = "任意";
    }
  }
}

function renderTransferTable() {
  transferTableBody.replaceChildren();
  const validations = validateTransferRows(state.rows);
  state.lastRowsValidation = validations;

  if (state.rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 9;
    td.style.padding = "22px 12px";
    td.style.textAlign = "center";
    td.style.color = "var(--muted)";
    td.textContent = "明細がありません。上のドロップゾーンから CSV/TSV を読み込むか「+ 行を追加」を押してください。";
    tr.appendChild(td);
    transferTableBody.appendChild(tr);
    return;
  }

  let visibleCount = 0;
  state.rows.forEach((row, idx) => {
    const v = validations.rows[idx];
    if (state.filterMode === "errors" && !v.hasErrors) return;
    visibleCount += 1;

    const tr = document.createElement("tr");
    tr.dataset.rowIndex = String(idx);

    const onRowEdit = (field, val) => {
      state.rows[idx][field] = val;
      const updatedVal = validateTransferRow(state.rows[idx], idx);
      updateRowDomValidation(tr, state.rows[idx], updatedVal);
      recomputeAndRenderOutputs();
    };

    // Col 1: #
    const tdIdx = document.createElement("td");
    tdIdx.className = "cell-idx";
    const dot = document.createElement("span");
    dot.dataset.role = "dot";
    tdIdx.append(dot, document.createTextNode(String(idx + 1)));
    tr.appendChild(tdIdx);

    // Col 2: Bank
    const tdBank = document.createElement("td");
    const bankPair = document.createElement("div");
    bankPair.className = "cell-pair--inline";
    const bankCodeIn = createCellInput({
      value: row.bankCode,
      cls: "is-mono tabular",
      maxLength: 4,
      placeholder: "0005",
      ariaLabel: `${idx + 1}行目 銀行コード`,
      onInput: (val) => onRowEdit("bankCode", val),
    });
    bankCodeIn.dataset.field = "bankCode";
    const bankNameIn = createCellInput({
      value: row.bankName,
      placeholder: "銀行名カナ",
      ariaLabel: `${idx + 1}行目 銀行名`,
      onInput: (val) => onRowEdit("bankName", val),
    });
    bankNameIn.dataset.field = "bankName";
    bankPair.append(bankCodeIn, bankNameIn);
    tdBank.appendChild(bankPair);
    if (row.autoRepairNotes && row.autoRepairNotes.length > 0) {
      const repNote = document.createElement("div");
      repNote.className = "cell-sub is-warn";
      repNote.textContent = row.autoRepairNotes.slice(0, 2).join(" / ");
      tdBank.appendChild(repNote);
    }
    tr.appendChild(tdBank);

    // Col 3: Branch
    const tdBranch = document.createElement("td");
    const branchPair = document.createElement("div");
    branchPair.className = "cell-pair--inline";
    const branchCodeIn = createCellInput({
      value: row.branchCode,
      cls: "is-mono tabular",
      maxLength: 3,
      placeholder: "001",
      ariaLabel: `${idx + 1}行目 支店コード`,
      onInput: (val) => onRowEdit("branchCode", val),
    });
    branchCodeIn.dataset.field = "branchCode";
    const branchNameIn = createCellInput({
      value: row.branchName,
      placeholder: "支店名カナ",
      ariaLabel: `${idx + 1}行目 支店名`,
      onInput: (val) => onRowEdit("branchName", val),
    });
    branchNameIn.dataset.field = "branchName";
    branchPair.append(branchCodeIn, branchNameIn);
    tdBranch.appendChild(branchPair);
    tr.appendChild(tdBranch);

    // Col 4: Account Type + Number
    const tdAcct = document.createElement("td");
    tdAcct.className = "col-acct";
    const acctPair = document.createElement("div");
    acctPair.className = "cell-pair--inline";
    const acctTypeSel = document.createElement("select");
    acctTypeSel.className = "cell-select";
    acctTypeSel.dataset.field = "accountType";
    acctTypeSel.setAttribute("aria-label", `${idx + 1}行目 預金種目`);
    for (const [val, label] of [
      ["1", "1:普通"],
      ["2", "2:当座"],
      ["4", "4:貯蓄"],
      ["9", "9:他"],
    ]) {
      const opt = document.createElement("option");
      opt.value = val;
      opt.textContent = label;
      if (String(row.accountType) === val) opt.selected = true;
      acctTypeSel.appendChild(opt);
    }
    acctTypeSel.addEventListener("change", () => onRowEdit("accountType", acctTypeSel.value));

    const acctNumIn = createCellInput({
      value: row.accountNumber,
      cls: "is-mono tabular",
      maxLength: 7,
      placeholder: "1234567",
      ariaLabel: `${idx + 1}行目 口座番号`,
      onInput: (val) => onRowEdit("accountNumber", val),
    });
    acctNumIn.dataset.field = "accountNumber";
    acctPair.append(acctTypeSel, acctNumIn);
    tdAcct.appendChild(acctPair);
    tr.appendChild(tdAcct);

    // Col 5: Recipient Name + Live Zengin 30B Preview
    const tdPayee = document.createElement("td");
    const payeeWrap = document.createElement("div");
    payeeWrap.className = "cell-pair";
    const payeeIn = createCellInput({
      value: row.recipientName,
      placeholder: "例: 株式会社テストサプライ",
      ariaLabel: `${idx + 1}行目 受取人名義`,
      onInput: (val) => onRowEdit("recipientName", val),
    });
    payeeIn.dataset.field = "recipientName";
    const payeePreview = document.createElement("div");
    payeePreview.dataset.role = "payee-preview";
    payeeWrap.append(payeeIn, payeePreview);
    tdPayee.appendChild(payeeWrap);
    tr.appendChild(tdPayee);

    // Col 6: Amount
    const tdAmt = document.createElement("td");
    const amtWrap = document.createElement("div");
    amtWrap.className = "cell-pair";
    const amtIn = createCellInput({
      value: String(row.amount ?? ""),
      cls: "is-num",
      placeholder: "100000",
      ariaLabel: `${idx + 1}行目 振込金額`,
      onInput: (val) => onRowEdit("amount", val),
    });
    amtIn.dataset.field = "amount";
    const amtNote = document.createElement("div");
    amtNote.dataset.role = "amt-note";
    amtNote.style.textAlign = "right";
    amtWrap.append(amtIn, amtNote);
    tdAmt.appendChild(amtWrap);
    tr.appendChild(tdAmt);

    // Col 7: EDI Info (Pos 92-111 -> Auto Pos 113 "Y")
    const tdEdi = document.createElement("td");
    const ediWrap = document.createElement("div");
    ediWrap.className = "cell-pair";
    const ediIn = createCellInput({
      value: row.ediInfo ?? "",
      cls: "is-mono",
      placeholder: "INV-001",
      ariaLabel: `${idx + 1}行目 EDI情報`,
      onInput: (val) => onRowEdit("ediInfo", val),
    });
    ediIn.dataset.field = "ediInfo";
    const ediNote = document.createElement("div");
    ediNote.dataset.role = "edi-note";
    ediWrap.append(ediIn, ediNote);
    tdEdi.appendChild(ediWrap);
    tr.appendChild(tdEdi);

    // Col 8: T-Number (Optional Mod-9)
    const tdInv = document.createElement("td");
    const invWrap = document.createElement("div");
    invWrap.className = "cell-pair";
    const invIn = createCellInput({
      value: row.invoiceId ?? "",
      cls: "is-mono tabular",
      placeholder: "T7000012050002",
      ariaLabel: `${idx + 1}行目 適格請求書T番号`,
      onInput: (val) => onRowEdit("invoiceId", val),
    });
    invIn.dataset.field = "invoiceId";
    const invNote = document.createElement("div");
    invNote.dataset.role = "inv-note";
    invWrap.append(invIn, invNote);
    tdInv.appendChild(invWrap);
    tr.appendChild(tdInv);

    // Col 9: Delete
    const tdDel = document.createElement("td");
    tdDel.className = "col-del";
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn-del";
    delBtn.textContent = "削除";
    delBtn.addEventListener("click", () => {
      state.rows.splice(idx, 1);
      renderTransferTable();
      recomputeAndRenderOutputs();
    });
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    updateRowDomValidation(tr, row, v);
    transferTableBody.appendChild(tr);
  });

  if (visibleCount === 0 && state.filterMode === "errors") {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 9;
    td.style.padding = "18px 12px";
    td.style.textAlign = "center";
    td.style.color = "var(--ok)";
    td.style.fontWeight = "600";
    td.textContent = "要修正エラーはありません。すべての明細が全銀120バイト規格を満たしています。";
    tr.appendChild(td);
    transferTableBody.appendChild(tr);
  }
}

// -------------------- Validation, Generation & 120-Byte Inspector --------------------
function recomputeAndRenderOutputs() {
  readProfileInputsIntoState();

  const headerVal = validateHeader(state.profile);
  const rowsVal = validateTransferRows(state.rows);
  state.lastHeaderValidation = headerVal;
  state.lastRowsValidation = rowsVal;

  // Profile summary & meter
  const reqPrev = headerVal.requesterNamePreview;
  if (reqPrev.hasErrors) {
    reqNamePreview.className = "field__meter is-err";
    reqNamePreview.textContent = `不可文字(漢字等): ${reqPrev.invalidChars.join("")}`;
  } else {
    reqNamePreview.className = "field__meter";
    reqNamePreview.textContent = `変換後: ${reqPrev.zenginText || "(空)"} (${reqPrev.byteLength}/40B)`;
  }

  profileSummaryText.textContent = `${state.profile.requesterCode} / ${reqPrev.zenginText || state.profile.requesterName} / 振込日 ${state.profile.transferDateMMDD} / ${state.profile.bankCode}-${state.profile.branchCode}`;
  headerErrorInline.textContent = headerVal.errors.map((e) => e.message).join(" / ");

  const totalBlockingErrors = headerVal.errors.length + rowsVal.totalErrors;
  const totalAmount = rowsVal.rows.reduce((sum, r) => sum + (r.parsedAmount ?? 0), 0);

  // Filter buttons counts
  filterAllBtn.textContent = `すべて (${state.rows.length})`;
  filterErrorsBtn.textContent = `要修正のみ (${rowsVal.errorRowCount})`;

  // Top tab badge
  if (totalBlockingErrors > 0) {
    tabErrorBadge.textContent = String(totalBlockingErrors);
    tabErrorBadge.classList.remove("is-hidden");
  } else {
    tabErrorBadge.classList.add("is-hidden");
  }

  // Try generating Shift-JIS binary payload (even if kanji errors exist, we generate preview safely unless amounts are non-numeric)
  let gen = null;
  let genErr = null;
  try {
    const safeRowsForPreview = state.rows.map((r, i) => ({
      ...r,
      amount: rowsVal.rows[i].parsedAmount ?? 0,
      bankCode: String(r.bankCode || "0000").replace(/\D/g, "").slice(0, 4) || "0000",
      branchCode: String(r.branchCode || "000").replace(/\D/g, "").slice(0, 3) || "000",
      accountNumber: String(r.accountNumber || "0000000").replace(/\D/g, "").slice(0, 7) || "0000000",
    }));
    const safeHeaderForPreview = {
      ...state.profile,
      requesterCode: String(state.profile.requesterCode || "0").replace(/\D/g, "").slice(0, 10) || "0",
      transferDateMMDD: String(state.profile.transferDateMMDD || "0101").replace(/\D/g, "").slice(0, 4) || "0101",
      bankCode: String(state.profile.bankCode || "0001").replace(/\D/g, "").slice(0, 4) || "0001",
      branchCode: String(state.profile.branchCode || "001").replace(/\D/g, "").slice(0, 3) || "001",
      accountNumber: String(state.profile.accountNumber || "0").replace(/\D/g, "").slice(0, 7) || "0",
    };
    gen = generateZengin120FromRows(safeRowsForPreview, safeHeaderForPreview);
  } catch (err) {
    genErr = err;
  }
  state.lastGen = gen;

  // Update KPI strip
  const preset = BANK_PRESETS[state.profile.preset] ?? BANK_PRESETS.standard;
  const tType = TRANSFER_TYPES[state.profile.transferType] ?? TRANSFER_TYPES["21"];

  kpiTotalAmount.textContent = formatYen(totalAmount);
  kpiTransferMeta.textContent = `${tType.label}(${tType.code}) · 指定日 ${state.profile.transferDateMMDD}`;

  kpiRowCount.textContent = `${state.rows.length} 件`;
  if (rowsVal.errorRowCount > 0) {
    kpiRowHealth.textContent = `要修正 ${rowsVal.errorRowCount} 行（エラー ${rowsVal.totalErrors} 件）`;
    kpiRowHealth.style.color = "var(--err)";
  } else {
    kpiRowHealth.textContent = `全 ${state.rows.length} 件 規格適合`;
    kpiRowHealth.style.color = "var(--ok)";
  }

  kpiPresetLabel.textContent = preset.label.split("（")[0];
  const chLabel = state.profile.clearingHouseCode === "0000" ? "交換所0000" : "交換所空白";
  kpiSpecDetail.textContent = `${state.profile.lineEnding === "NONE" ? "改行なし120B" : "CRLF"} · ${state.profile.includeEof ? "EOF(0x1A)有" : "EOFなし"} · ${chLabel}`;

  const readyToDownload = Boolean(gen && !genErr && totalBlockingErrors === 0 && state.rows.length > 0);
  downloadZenginBtn.disabled = !readyToDownload;

  if (readyToDownload) {
    kpiByteCheck.textContent = `120B × ${gen.lineCount}行`;
    kpiByteCheck.className = "summary-cell__value tabular text-ok";
    kpiByteSub.textContent = `Shift-JIS 合計 ${gen.byteLength.toLocaleString()} bytes 検証済`;
    builderHeadlineStatus.className = "page-head__sub is-ok";
    builderHeadlineStatus.textContent = `銀行提出準備完了：全 ${gen.dataCount} 件 / 合計 ${formatYen(gen.totalAmountYen)} / Shift-JIS (CP932) 各レコード厳密120バイト確認済`;
    inspectorByteBadge.className = "badge badge--ok";
    inspectorByteBadge.textContent = `120 bytes / record confirmed · CP932 (${gen.byteLength}B)`;
    genSummary.className = "status-box is-ok";
    genSummary.textContent = `Shift-JIS (CP932) バイナリ検証合格：ヘッダ1 + 明細${gen.dataCount} + トレーラ1 + エンド1 = 全${gen.lineCount}レコード（各120バイト / 合計 ${gen.byteLength} bytes）`;
  } else if (state.rows.length === 0) {
    kpiByteCheck.textContent = "明細0件";
    kpiByteCheck.className = "summary-cell__value tabular";
    kpiByteSub.textContent = "明細を追加してください";
    builderHeadlineStatus.className = "page-head__sub";
    builderHeadlineStatus.textContent = "CSV/TSV を読み込むか明細行を追加すると、Shift-JIS 120バイトバイナリを即時生成します。";
    inspectorByteBadge.className = "badge badge--neutral";
    inspectorByteBadge.textContent = "明細待機中";
    genSummary.className = "status-box";
    genSummary.textContent = "振込明細が0件のためダウンロードは無効です。";
  } else {
    kpiByteCheck.textContent = `要修正 ${totalBlockingErrors} 件`;
    kpiByteCheck.className = "summary-cell__value tabular text-err";
    kpiByteSub.textContent = "漢字・数値・T番号の赤枠を修正してください";
    builderHeadlineStatus.className = "page-head__sub is-err";
    builderHeadlineStatus.textContent = `要修正 ${totalBlockingErrors} 件を検出（組戻し防止のためダウンロード保護中）— 赤枠のセルをインライン修正してください。`;
    inspectorByteBadge.className = "badge badge--err";
    inspectorByteBadge.textContent = `エラー ${totalBlockingErrors} 件のため提出不可`;
    genSummary.className = "status-box is-err";
    const firstErrs = [...headerVal.errors, ...rowsVal.rows.flatMap((r) => r.errors.map((e) => ({ ...e, row: r.index + 1 })))]
      .slice(0, 4)
      .map((e) => (e.row ? `${e.row}行目: ${e.message}` : e.message));
    genSummary.textContent = `提出前チェックエラー (${totalBlockingErrors}件): ${firstErrs.join(" ｜ ")}`;
  }

  renderByteRulerInspector(gen);

  // Update SHA-256 fingerprint asynchronously for Approval Check Sheet
  if (gen && gen.bytes) {
    computeSha256Hex(gen.bytes).then((hex) => {
      state.sha256Hex = hex;
      if (state.activeTab === "sheet") {
        sheetSha256.textContent = `Shift-JIS SHA-256: ${hex}`;
      }
    });
  } else {
    state.sha256Hex = "";
  }
}

function appendSeg(parent, text, cls) {
  const span = document.createElement("span");
  span.className = `ruler-seg ${cls}`;
  span.style.width = `${text.length}ch`;
  span.textContent = text;
  parent.appendChild(span);
}

function renderByteRulerInspector(gen) {
  byteRulerContainer.replaceChildren();
  if (!gen) {
    byteRulerContainer.textContent = "(プレビュー生成待機中)";
    return;
  }

  if (state.inspectorMode === "hex") {
    const bytes = gen.bytes;
    const lines = [];
    const maxBytes = Math.min(bytes.length, 2048);
    for (let offset = 0; offset < maxBytes; offset += 16) {
      const slice = bytes.subarray(offset, Math.min(offset + 16, maxBytes));
      const addr = offset.toString(16).toUpperCase().padStart(6, "0");
      const hexPart = Array.from(slice)
        .map((b) => b.toString(16).toUpperCase().padStart(2, "0"))
        .join(" ")
        .padEnd(16 * 3 - 1, " ");
      const asciiPart = Array.from(slice)
        .map((b) => {
          if (b >= 0x20 && b <= 0x7e) return String.fromCharCode(b);
          if (b >= 0xa1 && b <= 0xdf) return String.fromCharCode(b - 0xa1 + 0xff61);
          return ".";
        })
        .join("");
      lines.push(`${addr}  ${hexPart}  |${asciiPart}|`);
    }
    if (bytes.length > maxBytes) {
      lines.push(`... (${bytes.length - maxBytes} bytes 省略 / 全体 ${bytes.length} bytes)`);
    }
    byteRulerContainer.textContent = lines.join("\n");
    return;
  }

  // Ruler mode: 1..120 scale + color-coded Zengin fixed-width segments
  const rulerDiv = document.createElement("div");
  rulerDiv.className = "ruler-header";
  let tens = "     ";
  let units = "     ";
  for (let i = 1; i <= 120; i += 1) {
    tens += i % 10 === 0 ? String((i / 10) % 10) : " ";
    units += i % 10 === 0 ? "|" : i % 5 === 0 ? "+" : ".";
  }
  rulerDiv.textContent = `${tens}\n${units}`;
  byteRulerContainer.appendChild(rulerDiv);

  const records =
    gen.lineEnding === "NONE"
      ? Array.from({ length: gen.lineCount }, (_, i) => gen.content.slice(i * 120, (i + 1) * 120))
      : gen.content.replace(/\r\n$/, "").split("\r\n");

  records.forEach((rec, i) => {
    const lineDiv = document.createElement("div");
    lineDiv.className = "ruler-line";

    const lno = document.createElement("span");
    lno.className = "ruler-lno";
    lno.textContent = `${String(i + 1).padStart(3, "0")}:`;
    lineDiv.appendChild(lno);

    const recType = rec[0];
    if (recType === "2" && rec.length === 120) {
      appendSeg(lineDiv, rec.slice(0, 1), "seg-type");
      appendSeg(lineDiv, rec.slice(1, 38), "seg-bank");
      appendSeg(lineDiv, rec.slice(38, 42), "seg-clear");
      appendSeg(lineDiv, rec.slice(42, 50), "seg-acct");
      appendSeg(lineDiv, rec.slice(50, 80), "seg-payee");
      appendSeg(lineDiv, rec.slice(80, 90), "seg-amt");
      appendSeg(lineDiv, rec.slice(90, 91), "seg-dim");
      appendSeg(lineDiv, rec.slice(91, 111), "seg-edi");
      appendSeg(lineDiv, rec.slice(111, 113), "seg-flag");
      appendSeg(lineDiv, rec.slice(113, 120), "seg-dim");
    } else if (recType === "1" && rec.length === 120) {
      appendSeg(lineDiv, rec.slice(0, 4), "seg-type");
      appendSeg(lineDiv, rec.slice(4, 14), "seg-acct");
      appendSeg(lineDiv, rec.slice(14, 54), "seg-payee");
      appendSeg(lineDiv, rec.slice(54, 58), "seg-amt");
      appendSeg(lineDiv, rec.slice(58, 103), "seg-bank");
      appendSeg(lineDiv, rec.slice(103, 120), "seg-dim");
    } else if (recType === "8" && rec.length === 120) {
      appendSeg(lineDiv, rec.slice(0, 1), "seg-type");
      appendSeg(lineDiv, rec.slice(1, 7), "seg-acct");
      appendSeg(lineDiv, rec.slice(7, 19), "seg-amt");
      appendSeg(lineDiv, rec.slice(19, 120), "seg-dim");
    } else {
      appendSeg(lineDiv, rec.slice(0, 1), "seg-type");
      appendSeg(lineDiv, rec.slice(1), "seg-dim");
    }

    const byteTag = document.createElement("span");
    byteTag.className = "seg-dim";
    byteTag.textContent = `  [${encodeZenginShiftJis(rec).length}B]`;
    lineDiv.appendChild(byteTag);

    byteRulerContainer.appendChild(lineDiv);
  });
}

// -------------------- Tab 2: Bank-Rejected File Repair --------------------
function runRepairFromInput(input, sourceLabel = "") {
  const targetPreset = repairPresetSelect.value || "standard";
  const result = diagnoseAndRepairZenginFile(input, { preset: targetPreset });
  state.lastRepairResult = result;

  if (typeof input === "string") {
    zenginRawInput.value = input;
  } else {
    zenginRawInput.value = decodeZenginBytes(input).text;
  }

  repairForensicsStrip.classList.remove("is-hidden");
  repSrcEncoding.textContent = result.source.encoding.toUpperCase();
  repSrcEncoding.className =
    result.source.encoding.startsWith("utf-8")
      ? "summary-cell__value text-err"
      : "summary-cell__value text-ok";
  repSrcBom.textContent = `${result.source.hasBom ? "BOMあり" : "BOMなし"} · ${result.source.lineEnding} · 元${result.source.rawByteLength.toLocaleString()}B`;

  repFixedCount.textContent = `${result.fixedCount} 件`;
  repBlockingCount.textContent = `要手動修正 ${result.blockingErrors.length} 件`;
  repBlockingCount.style.color = result.blockingErrors.length > 0 ? "var(--err)" : "var(--ok)";

  repTotalAmount.textContent = formatYen(result.repaired.totalAmountYen);
  repRowCount.textContent = `明細 ${result.repaired.dataCount} 件 / 全 ${result.repaired.lineCount} 行`;

  if (result.repaired.ok) {
    repByteStatus.textContent = "提出可能 (120B)";
    repByteStatus.className = "summary-cell__value text-ok";
    repByteTotal.textContent = `Shift-JIS ${result.repaired.byteLength.toLocaleString()} bytes 検証済`;
    zenginAuditOutput.className = "status-box is-ok";
    zenginAuditOutput.textContent = `${sourceLabel ? `[${sourceLabel}] ` : ""}自動修復完了（${result.fixedCount} 件修復）：全 ${result.repaired.lineCount} レコード × 120 バイト Shift-JIS 検証合格。このまま銀行へ提出できます。`;
  } else {
    repByteStatus.textContent = `要手動修正 (${result.blockingErrors.length})`;
    repByteStatus.className = "summary-cell__value text-err";
    repByteTotal.textContent = "漢字等を確認してください";
    zenginAuditOutput.className = "status-box is-err";
    zenginAuditOutput.textContent = `${sourceLabel ? `[${sourceLabel}] ` : ""}自動修復 ${result.fixedCount} 件適用・要手動修正 ${result.blockingErrors.length} 件残存。「編集テーブルへ取込む」から赤枠セルを修正してください。`;
  }

  repairDiagnosticsList.replaceChildren();
  if (result.diagnostics.length === 0) {
    const li = document.createElement("li");
    li.className = "diag-item";
    const badge = document.createElement("span");
    badge.className = "badge badge--ok";
    badge.textContent = "異常なし";
    const msg = document.createElement("span");
    msg.textContent = "元のファイルはすでに Shift-JIS 120バイト規格・トレーラ検算に完全適合しています。";
    li.append(badge, msg);
    repairDiagnosticsList.appendChild(li);
  } else {
    for (const d of result.diagnostics) {
      const li = document.createElement("li");
      li.className = d.fixed ? "diag-item" : "diag-item is-err";
      const badge = document.createElement("span");
      badge.className = d.fixed ? "badge badge--ok" : "badge badge--err";
      badge.textContent = d.fixed ? "自動修復済" : "要手動修正";
      const code = document.createElement("span");
      code.className = "badge badge--neutral tabular";
      code.textContent = d.line > 0 ? `${d.line}行目 · ${d.code}` : d.code;
      const msg = document.createElement("span");
      msg.textContent = d.message;
      li.append(badge, code, msg);
      repairDiagnosticsList.appendChild(li);
    }
  }

  repairPreviewCode.textContent = result.repaired.content;
  downloadRepairedBtn.disabled = !result.repaired.ok;
  repairSendToBuilderBtn.disabled = result.repaired.rows.length === 0;
}

function buildDemoBrokenZenginBytes() {
  const base = generateZengin120FromRows(
    [
      {
        bankCode: "0005",
        bankName: "ﾐﾂﾋﾞｼUFJ",
        branchCode: "001",
        branchName: "ﾎﾝﾃﾝ",
        accountType: "1",
        accountNumber: "1234567",
        recipientName: "ﾔﾏﾀﾞ ﾀﾛｳ",
        amount: 120000,
        ediInfo: "INV-2026-09",
      },
      {
        bankCode: "0009",
        bankName: "ﾐﾂｲｽﾐﾄﾓ",
        branchCode: "200",
        branchName: "ｼﾝｼﾞﾕｸ",
        accountType: "2",
        accountNumber: "7654321",
        recipientName: "ｻﾄｳ ﾊﾅｺ",
        amount: 85000,
        ediInfo: "",
      },
    ],
    { requesterName: "ｶ)ﾎﾗｲｿﾞﾝ", transferDateMMDD: "1125" },
  );
  const lines = base.content.trimEnd().split("\r\n");
  // Deliberately inject 6 real-world bank rejection causes:
  // 1. UTF-8 BOM + UTF-8 encoding, 2. LF-only, 3. full-width space/kana, 4. trimmed trailing spaces,
  // 5. missing Pos 113 'Y', 6. wrong trailer count & total + missing End record!
  const brokenRow1 =
    lines[1].slice(0, 50) +
    "ヤマダ　タロウ".padEnd(30, " ") +
    lines[1].slice(80, 112) +
    " ";
  const brokenTrailer = "8000005000000999999" + " ".repeat(101);
  const brokenText = "\uFEFF" + [lines[0], brokenRow1, lines[2].trimEnd(), brokenTrailer].join("\n") + "\n";
  return new TextEncoder().encode(brokenText);
}

// -------------------- Tab 3: T-Number Batch Verifier --------------------
function runCheckIds() {
  const res = verifyBatchIdentifiers(idsInput.value);
  state.lastInvoiceBatch = res;
  invTotalCount.textContent = `${res.total} 件`;
  invValidCount.textContent = `${res.validCount} 件`;
  invInvalidCount.textContent = `${res.invalidCount} 件`;

  idsTableBody.replaceChildren();
  for (const item of res.items) {
    const tr = document.createElement("tr");
    if (!item.valid) tr.className = "row-has-err";

    const tdLine = document.createElement("td");
    tdLine.className = "tabular";
    tdLine.textContent = String(item.line);

    const tdKind = document.createElement("td");
    tdKind.textContent =
      item.kind === "INVOICE_ID"
        ? "適格請求書T番号"
        : item.kind === "CORPORATE_ID"
          ? "法人番号(13桁)"
          : "不明形式";

    const tdNorm = document.createElement("td");
    tdNorm.className = "tabular";
    tdNorm.textContent = item.normalized;

    const tdJudge = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = item.valid ? "badge badge--ok" : "badge badge--err";
    badge.textContent = item.valid ? "適格 (VALID)" : "不一致 (INVALID)";
    tdJudge.appendChild(badge);

    const tdReason = document.createElement("td");
    tdReason.textContent = item.reason;

    tr.append(tdLine, tdKind, tdNorm, tdJudge, tdReason);
    idsTableBody.appendChild(tr);
  }
}

// -------------------- Tab 4: Printable Approval Check Sheet --------------------
function renderApprovalSheet() {
  const p = state.profile;
  const preset = BANK_PRESETS[p.preset] ?? BANK_PRESETS.standard;
  const tType = TRANSFER_TYPES[p.transferType] ?? TRANSFER_TYPES["21"];
  const nowStr = new Date().toLocaleString("ja-JP", { hour12: false });

  sheetSubtitle.textContent = `出力日時：${nowStr} ／ 出力仕様：${preset.label}（Shift-JIS CP932・120バイト固定長）`;

  const metaItems = [
    ["振込種別", `${tType.label}（種別コード ${tType.code}）`],
    ["振込指定日", `${p.transferDateMMDD.slice(0, 2)}月${p.transferDateMMDD.slice(2, 4)}日 (${p.transferDateMMDD})`],
    ["委託者コード / 名義", `${p.requesterCode} / ${toZenginHalfWidth(p.requesterName, { maxLength: 40 }).zenginText}`],
    ["引落（仕向）口座", `${p.bankCode} ${p.bankName} / ${p.branchCode} ${p.branchName} (${p.accountType}:${p.accountNumber})`],
    ["改行・EOF・交換所", `${p.lineEnding} / ${p.includeEof ? "EOF(0x1A)有" : "EOFなし"} / ${p.clearingHouseCode === "0000" ? "0000" : "空白"}`],
    ["明細件数", `${state.rows.length} 件`],
    ["振込合計金額", formatYen(state.lastGen ? state.lastGen.totalAmountYen : 0)],
    ["ファイルサイズ", state.lastGen ? `${state.lastGen.byteLength.toLocaleString()} bytes (120B×${state.lastGen.lineCount}行)` : "未生成"],
  ];

  sheetMetaGrid.replaceChildren();
  for (const [k, v] of metaItems) {
    const div = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.className = "tabular";
    dd.textContent = v;
    div.append(dt, dd);
    sheetMetaGrid.appendChild(div);
  }

  const totalErrors =
    (state.lastHeaderValidation ? state.lastHeaderValidation.errors.length : 0) +
    (state.lastRowsValidation ? state.lastRowsValidation.totalErrors : 0);
  if (totalErrors > 0) {
    sheetErrorWarning.classList.remove("is-hidden");
    sheetErrorWarning.textContent = `注意：現在 ${totalErrors} 件のエラーが残存しています。「振込データ作成」タブで修正後に最終承認を行ってください。`;
  } else {
    sheetErrorWarning.classList.add("is-hidden");
  }

  const acctLabels = { "1": "普通", "2": "当座", "4": "貯蓄", "9": "他" };
  sheetTableBody.replaceChildren();
  let sumYen = 0;

  state.rows.forEach((row, idx) => {
    const v = state.lastRowsValidation?.rows[idx] ?? validateTransferRow(row, idx);
    const amt = v.parsedAmount ?? 0;
    sumYen += amt;

    const tr = document.createElement("tr");
    const cells = [
      { text: String(idx + 1), cls: "num" },
      { text: `${row.bankCode} ${row.bankName || ""} / ${row.branchCode} ${row.branchName || ""}` },
      { text: `${acctLabels[row.accountType] || row.accountType} ${row.accountNumber}`, cls: "tabular" },
      {
        text: v.recipientPreview.hasErrors
          ? `[要修正] ${row.recipientName}`
          : v.recipientPreview.zenginText,
      },
      { text: formatYen(amt), cls: "num" },
      { text: v.ediPreview.zenginText ? `${v.ediPreview.zenginText} [Y]` : "-" },
      {
        text: !row.invoiceId
          ? "-"
          : v.invoiceCheck?.valid
            ? `適格 (${v.invoiceCheck.normalized})`
            : `不一致 (${row.invoiceId})`,
      },
    ];
    for (const c of cells) {
      const td = document.createElement("td");
      if (c.cls) td.className = c.cls;
      td.textContent = c.text;
      tr.appendChild(td);
    }
    sheetTableBody.appendChild(tr);
  });

  sheetFooterCount.textContent = String(state.rows.length);
  sheetFooterTotal.textContent = formatYen(sumYen);
  sheetFooterIntegrity.textContent = totalErrors === 0 ? "全銀120B Shift-JIS 検証済" : `要修正 ${totalErrors} 件`;
  sheetSha256.textContent = state.sha256Hex ? `Shift-JIS SHA-256: ${state.sha256Hex}` : "";
}

// -------------------- Event Listeners --------------------
tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

openPrintSheetBtn.addEventListener("click", () => switchTab("sheet"));
printApprovalSheetBtn.addEventListener("click", () => window.print());

// Main CSV/TSV/Zengin Dropzone
function wireDropzone(zone, inputEl, onFile) {
  zone.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    inputEl.click();
  });
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      inputEl.click();
    }
  });
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("is-dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("is-dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("is-dragover");
    const file = e.dataTransfer?.files?.[0];
    if (file) onFile(file);
  });
  inputEl.addEventListener("change", () => {
    const file = inputEl.files?.[0];
    if (file) onFile(file);
    inputEl.value = "";
  });
}

wireDropzone(csvDropzone, csvFileInput, handleMainFileDropOrPick);
pickCsvFileBtn.addEventListener("click", () => csvFileInput.click());

loadSampleCsvBtn.addEventListener("click", () => {
  loadCsvTextIntoWorkbench(CLEAN_SAMPLE_CSV, "正常サンプル明細");
});

loadDirtySampleBtn.addEventListener("click", () => {
  loadCsvTextIntoWorkbench(DIRTY_DEMO_CSV, "エラー修復体験サンプル");
});

togglePasteCsvBtn.addEventListener("click", () => {
  csvPasteDrawer.classList.toggle("is-hidden");
  if (!csvPasteDrawer.classList.contains("is-hidden")) {
    csvRowsInput.focus();
  }
});

applyPasteCsvBtn.addEventListener("click", () => {
  loadCsvTextIntoWorkbench(csvRowsInput.value, "貼付データ");
  csvPasteDrawer.classList.add("is-hidden");
});

// Bank Preset & Format controls
bankPresetSelect.addEventListener("change", () => applyBankPreset(bankPresetSelect.value));
for (const el of [
  transferTypeSelect,
  lineEndingSelect,
  clearingHouseSelect,
  includeEofCheckbox,
  reqCodeInput,
  reqNameInput,
  transferDateInput,
  srcBankCodeInput,
  srcBankNameInput,
  srcBranchCodeInput,
  srcBranchNameInput,
  srcAcctTypeInput,
  srcAcctNumInput,
]) {
  el.addEventListener("input", () => {
    readProfileInputsIntoState();
    saveProfileToStorage(false);
    recomputeAndRenderOutputs();
  });
  el.addEventListener("change", () => {
    readProfileInputsIntoState();
    saveProfileToStorage(false);
    recomputeAndRenderOutputs();
  });
}

saveProfileBtn.addEventListener("click", () => {
  readProfileInputsIntoState();
  saveProfileToStorage(true);
});

exportProfileJsonBtn.addEventListener("click", () => {
  readProfileInputsIntoState();
  const payload = JSON.stringify(state.profile, null, 2);
  triggerTextDownload(payload, "zengingate-requester-profile.json", "application/json;charset=utf-8");
});

importProfileJsonBtn.addEventListener("click", () => importProfileFileInput.click());
importProfileFileInput.addEventListener("change", async () => {
  const file = importProfileFileInput.files?.[0];
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    state.profile = { ...DEFAULT_PROFILE, ...parsed };
    syncProfileInputsFromState();
    saveProfileToStorage(true);
    recomputeAndRenderOutputs();
  } catch (err) {
    headerErrorInline.textContent = `JSON読込失敗: ${err?.message || err}`;
  }
  importProfileFileInput.value = "";
});

// Table controls
filterAllBtn.addEventListener("click", () => {
  state.filterMode = "all";
  filterAllBtn.classList.add("is-active");
  filterErrorsBtn.classList.remove("is-active");
  renderTransferTable();
});

filterErrorsBtn.addEventListener("click", () => {
  state.filterMode = "errors";
  filterErrorsBtn.classList.add("is-active");
  filterAllBtn.classList.remove("is-active");
  renderTransferTable();
});

addRowBtn.addEventListener("click", () => {
  state.rows.push({
    bankCode: "0005",
    bankName: "ﾐﾂﾋﾞｼUFJ",
    branchCode: "001",
    branchName: "ﾎﾝﾃﾝ",
    accountType: "1",
    accountNumber: "0000001",
    recipientName: "",
    amount: "",
    ediInfo: "",
    transferDesignation: "7",
    invoiceId: "",
  });
  state.filterMode = "all";
  filterAllBtn.classList.add("is-active");
  filterErrorsBtn.classList.remove("is-active");
  renderTransferTable();
  recomputeAndRenderOutputs();
});

clearRowsBtn.addEventListener("click", () => {
  state.rows = [];
  importRepairBanner.classList.add("is-hidden");
  renderTransferTable();
  recomputeAndRenderOutputs();
});

// Inspector controls
inspectorModeRulerBtn.addEventListener("click", () => {
  state.inspectorMode = "ruler";
  inspectorModeRulerBtn.classList.add("is-active");
  inspectorModeHexBtn.classList.remove("is-active");
  renderByteRulerInspector(state.lastGen);
});

inspectorModeHexBtn.addEventListener("click", () => {
  state.inspectorMode = "hex";
  inspectorModeHexBtn.classList.add("is-active");
  inspectorModeRulerBtn.classList.remove("is-active");
  renderByteRulerInspector(state.lastGen);
});

copyZenginTextBtn.addEventListener("click", async () => {
  if (!state.lastGen) return;
  try {
    await navigator.clipboard.writeText(state.lastGen.content);
    copyZenginTextBtn.textContent = "コピー済";
    setTimeout(() => {
      copyZenginTextBtn.textContent = "テキストコピー";
    }, 1500);
  } catch {
    copyZenginTextBtn.textContent = "コピー失敗";
  }
});

// Primary Shift-JIS Binary Download
downloadZenginBtn.addEventListener("click", () => {
  if (!state.lastGen || downloadZenginBtn.disabled) return;
  const p = state.profile;
  const fname = `zengin-${p.transferType}-${p.preset}-${p.transferDateMMDD || "0000"}-sjis.txt`;
  triggerBinaryDownload(state.lastGen.bytes, fname);
});

// Repair Tab Events
wireDropzone(repairDropzone, repairFileInput, async (file) => {
  const buf = await file.arrayBuffer();
  runRepairFromInput(new Uint8Array(buf), file.name);
});
pickRepairFileBtn.addEventListener("click", () => repairFileInput.click());

loadBrokenSampleBtn.addEventListener("click", () => {
  const brokenBytes = buildDemoBrokenZenginBytes();
  runRepairFromInput(brokenBytes, "bank-rejected-utf8-broken.txt");
});

auditZenginBtn.addEventListener("click", () => {
  runRepairFromInput(zenginRawInput.value, "貼付テキスト");
});

repairPresetSelect.addEventListener("change", () => {
  if (zenginRawInput.value.trim()) {
    runRepairFromInput(zenginRawInput.value, "プリセット切替再修復");
  }
});

downloadRepairedBtn.addEventListener("click", () => {
  const rep = state.lastRepairResult?.repaired;
  if (!rep || !rep.ok) return;
  const preset = repairPresetSelect.value || "standard";
  triggerBinaryDownload(rep.bytes, `repaired-zengin-${preset}-sjis.txt`);
});

repairSendToBuilderBtn.addEventListener("click", () => {
  const rep = state.lastRepairResult?.repaired;
  if (!rep || rep.rows.length === 0) return;
  if (rep.header) {
    state.profile = {
      ...state.profile,
      ...rep.header,
      preset: repairPresetSelect.value || state.profile.preset,
    };
    const presetObj = BANK_PRESETS[state.profile.preset] ?? BANK_PRESETS.standard;
    state.profile.lineEnding = presetObj.lineEnding;
    state.profile.includeEof = presetObj.includeEof;
    state.profile.clearingHouseCode = presetObj.clearingHouseCode;
    syncProfileInputsFromState();
    saveProfileToStorage(false);
  }
  state.rows = rep.rows.map((r) => ({ ...r, invoiceId: "" }));
  renderTransferTable();
  recomputeAndRenderOutputs();
  switchTab("builder");
});

// Invoice Batch Tab Events
checkIdsBtn.addEventListener("click", runCheckIds);
exportInvoiceCsvBtn.addEventListener("click", () => {
  if (!state.lastInvoiceBatch) runCheckIds();
  const rows = [["行", "種別", "正規化ID", "判定", "詳細"]];
  for (const item of state.lastInvoiceBatch.items) {
    rows.push([
      String(item.line),
      item.kind,
      item.normalized,
      item.valid ? "VALID" : "INVALID",
      item.reason,
    ]);
  }
  const csv =
    "\uFEFF" +
    rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\r\n") +
    "\r\n";
  triggerTextDownload(csv, "invoice-mod9-audit.csv", "text/csv;charset=utf-8");
});

// -------------------- Boot --------------------
loadSavedProfile();
syncProfileInputsFromState();
loadCsvTextIntoWorkbench(CLEAN_SAMPLE_CSV, "");
runCheckIds();
