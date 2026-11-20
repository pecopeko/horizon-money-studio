/**
 * Five Agent-Worthy Intelligence Engines backed by live official zero-API-key APIs
 * plus a deterministic Japan NTA Qualified Invoice & Zengin CP932 normalizer.
 *
 * Pure Web-Standard ES Module (zero external dependencies).
 * Never swallows errors or fabricates fallback metrics.
 */

import { assertSafePublicUrl, readBoundedText, safePublicFetch } from "./ssrf.mjs";

export class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ValidationError";
    this.code = "INVALID_PARAMETER";
    this.httpStatus = 400;
  }
}

export class UpstreamError extends Error {
  constructor(message, { status = 502, upstreamStatus = null, source = null } = {}) {
    super(message);
    this.name = "UpstreamError";
    this.code = "UPSTREAM_ERROR";
    this.httpStatus = status;
    this.upstreamStatus = upstreamStatus;
    this.source = source;
  }
}

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const SLUG_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/;

function buildSecUserAgent(contactEmail) {
  const email = String(contactEmail || "").trim();
  const safeEmail = EMAIL_RE.test(email) ? email : "contact@x402-intel.dev";
  return `x402IntelWorker/1.0 (${safeEmail})`;
}

function clampInt(value, { defaultVal, min, max, name }) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return defaultVal;
  }
  const n = Number(value);
  if (!Number.isInteger(n)) {
    throw new ValidationError(`Parameter '${name}' must be an integer.`);
  }
  return Math.max(min, Math.min(max, n));
}

function parseBool(value, defaultVal = false) {
  if (value === undefined || value === null || value === "") return defaultVal;
  if (typeof value === "boolean") return value;
  const s = String(value).trim().toLowerCase();
  if (s === "true" || s === "1" || s === "yes") return true;
  if (s === "false" || s === "0" || s === "no") return false;
  throw new ValidationError(`Invalid boolean parameter value: "${value}".`);
}

function decodeHtmlEntities(input) {
  return String(input || "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#(\d+);/g, (_, dec) => {
      const code = Number.parseInt(dec, 10);
      return Number.isFinite(code) && code > 0 && code <= 0x10ffff
        ? String.fromCodePoint(code)
        : "";
    })
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => {
      const code = Number.parseInt(hex, 16);
      return Number.isFinite(code) && code > 0 && code <= 0x10ffff
        ? String.fromCodePoint(code)
        : "";
    });
}

function htmlToPlainText(html) {
  const unescaped = decodeHtmlEntities(html);
  return unescaped
    .replace(/<(script|style|noscript)[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<(?:br|\/p|\/div|\/li|\/h[1-6])[^>]*>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function fetchJsonStrict(url, { fetchImpl, headers, timeoutMs = 12000, source }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let resp;
  try {
    resp = await fetchImpl(url, {
      method: "GET",
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    throw new UpstreamError(
      `Upstream request failed for ${source}: ${err instanceof Error ? err.message : String(err)}`,
      { status: 502, source },
    );
  } finally {
    clearTimeout(timer);
  }

  if (!resp.ok) {
    throw new UpstreamError(
      `Upstream ${source} returned HTTP ${resp.status}`,
      { status: resp.status === 404 ? 404 : 502, upstreamStatus: resp.status, source },
    );
  }

  try {
    return await resp.json();
  } catch (err) {
    throw new UpstreamError(
      `Upstream ${source} returned invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
      { status: 502, upstreamStatus: resp.status, source },
    );
  }
}

// ===========================================================================
// 1. SEC EDGAR Financials (data.sec.gov ASC 606 XBRL + Submissions)
// ===========================================================================

const ANNUAL_FORMS = new Set(["10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"]);
const QUARTERLY_FORMS = new Set(["10-Q", "10-Q/A"]);
const KEY_SUBMISSION_FORMS = new Set(["10-K", "10-Q", "8-K", "20-F", "40-F", "S-1"]);

const XBRL_DURATION_USD = {
  revenue: [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "InterestAndDividendIncomeOperating",
    "RealEstateRevenueNet",
  ],
  net_income: ["NetIncomeLoss", "ProfitLoss"],
  operating_income: ["OperatingIncomeLoss"],
  operating_cash_flow: ["NetCashProvidedByUsedInOperatingActivities"],
};

const XBRL_INSTANT_USD = {
  assets: ["Assets"],
  liabilities: ["Liabilities"],
  stockholders_equity: ["StockholdersEquity"],
  cash_and_equivalents: [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
  ],
};

const XBRL_INSTANT_SHARES = [
  ["dei", "EntityCommonStockSharesOutstanding"],
  ["us-gaap", "CommonStockSharesOutstanding"],
];

const XBRL_DURATION_SHARES = [
  ["us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"],
  ["us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"],
];

let secTickerCache = null;

function normalizeCik(raw) {
  const cleaned = String(raw || "").trim().toUpperCase().replace(/^CIK/, "").trim();
  const digits = cleaned.replace(/\D/g, "");
  if (!digits || digits.length > 10) {
    throw new ValidationError(`Invalid SEC CIK: "${raw}"`);
  }
  return digits.padStart(10, "0");
}

function periodDays(row) {
  const startS = String(row?.start || "").slice(0, 10);
  const endS = String(row?.end || "").slice(0, 10);
  if (!ISO_DATE_RE.test(startS) || !ISO_DATE_RE.test(endS)) return null;
  const diffMs = Date.parse(`${endS}T00:00:00Z`) - Date.parse(`${startS}T00:00:00Z`);
  if (!Number.isFinite(diffMs)) return null;
  return Math.round(diffMs / 86400_000);
}

function isAnnualRow(row) {
  const form = String(row?.form || "").toUpperCase();
  const fp = String(row?.fp || "").toUpperCase();
  return ANNUAL_FORMS.has(form) || fp === "FY";
}

function isQuarterlyRow(row) {
  const form = String(row?.form || "").toUpperCase();
  const fp = String(row?.fp || "").toUpperCase();
  return QUARTERLY_FORMS.has(form) || fp === "Q1" || fp === "Q2" || fp === "Q3";
}

function selectBestXbrlFact(factsRoot, nsTagPairs, { unit, periodKind, isDuration }) {
  let best = null;
  for (let priorityIdx = 0; priorityIdx < nsTagPairs.length; priorityIdx += 1) {
    const [nsName, tag] = nsTagPairs[priorityIdx];
    const rows = factsRoot?.[nsName]?.[tag]?.units?.[unit];
    if (!Array.isArray(rows) || rows.length === 0) continue;

    let filtered = rows.filter(
      (r) => r && typeof r === "object" && (periodKind === "annual" ? isAnnualRow(r) : isQuarterlyRow(r)),
    );
    if (isDuration) {
      if (periodKind === "annual") {
        const fullYear = filtered.filter((r) => {
          const d = periodDays(r);
          return d === null || d >= 300;
        });
        if (fullYear.length > 0) filtered = fullYear;
      } else {
        const singleQ = filtered.filter((r) => {
          const d = periodDays(r);
          return d !== null && d >= 60 && d <= 120;
        });
        if (singleQ.length > 0) filtered = singleQ;
      }
    }

    for (const row of filtered) {
      const endStr = String(row.end || "");
      const filedStr = String(row.filed || "");
      if (!endStr && !filedStr) continue;
      const candidate = {
        endStr,
        negPriority: -priorityIdx,
        filedStr,
        tag,
        row,
      };
      if (
        !best ||
        candidate.endStr > best.endStr ||
        (candidate.endStr === best.endStr && candidate.negPriority > best.negPriority) ||
        (candidate.endStr === best.endStr &&
          candidate.negPriority === best.negPriority &&
          candidate.filedStr > best.filedStr)
      ) {
        best = candidate;
      }
    }
  }

  if (!best) return null;
  const r = best.row;
  return {
    tag: best.tag,
    val: r.val ?? null,
    unit,
    start: r.start ?? null,
    end: r.end ?? null,
    filed: r.filed ?? null,
    form: r.form ?? null,
    fy: r.fy ?? null,
    fp: r.fp ?? null,
    period_days: periodDays(r),
  };
}

export function extractSecFinancialsFromXbrl(companyFacts) {
  const factsRoot = companyFacts?.facts;
  if (!factsRoot || typeof factsRoot !== "object") {
    return { annual: {}, quarterly: {} };
  }
  const annual = {};
  const quarterly = {};

  for (const [concept, tags] of Object.entries(XBRL_DURATION_USD)) {
    const pairs = tags.map((t) => ["us-gaap", t]);
    const ann = selectBestXbrlFact(factsRoot, pairs, { unit: "USD", periodKind: "annual", isDuration: true });
    if (ann) annual[concept] = ann;
    const qtr = selectBestXbrlFact(factsRoot, pairs, { unit: "USD", periodKind: "quarterly", isDuration: true });
    if (qtr) quarterly[concept] = qtr;
  }

  for (const [concept, tags] of Object.entries(XBRL_INSTANT_USD)) {
    const pairs = tags.map((t) => ["us-gaap", t]);
    const ann = selectBestXbrlFact(factsRoot, pairs, { unit: "USD", periodKind: "annual", isDuration: false });
    if (ann) annual[concept] = ann;
    const qtr = selectBestXbrlFact(factsRoot, pairs, { unit: "USD", periodKind: "quarterly", isDuration: false });
    if (qtr) quarterly[concept] = qtr;
  }

  for (const [periodKind, target] of [
    ["annual", annual],
    ["quarterly", quarterly],
  ]) {
    const sharesOut = selectBestXbrlFact(factsRoot, XBRL_INSTANT_SHARES, {
      unit: "shares",
      periodKind,
      isDuration: false,
    });
    if (sharesOut) target.shares_outstanding = sharesOut;
    const diluted = selectBestXbrlFact(factsRoot, XBRL_DURATION_SHARES, {
      unit: "shares",
      periodKind,
      isDuration: true,
    });
    if (diluted) target.weighted_average_shares_diluted = diluted;
  }

  return { annual, quarterly };
}

function parseSecSubmissions(submissionsJson, limit = 10) {
  const recent = submissionsJson?.filings?.recent || {};
  const forms = recent.form || [];
  const accs = recent.accessionNumber || [];
  const dates = recent.filingDate || [];
  const reportDates = recent.reportDate || [];
  const docs = recent.primaryDocument || [];
  const descs = recent.primaryDocDescription || [];
  const items = recent.items || [];

  const cik10 = String(submissionsJson?.cik || "").replace(/\D/g, "").padStart(10, "0");
  const cikNum = String(Number.parseInt(cik10, 10) || cik10);
  const filings = [];

  for (let i = 0; i < forms.length && filings.length < limit; i += 1) {
    const formName = String(forms[i] || "");
    if (!KEY_SUBMISSION_FORMS.has(formName.toUpperCase())) continue;
    const acc = String(accs[i] || "");
    const doc = String(docs[i] || "");
    const accNoDash = acc.replace(/-/g, "");
    filings.push({
      form: formName,
      filing_date: dates[i] ?? null,
      report_date: reportDates[i] ?? null,
      accession_number: acc || null,
      primary_document: doc || null,
      description: descs[i] || "",
      items: items[i] || [],
      edgar_url:
        accNoDash && doc
          ? `https://www.sec.gov/Archives/edgar/data/${cikNum}/${accNoDash}/${doc}`
          : null,
      filing_index_url:
        accNoDash && acc
          ? `https://www.sec.gov/Archives/edgar/data/${cikNum}/${accNoDash}/${acc}-index.htm`
          : null,
    });
  }

  return {
    cik: cik10,
    entity_name: submissionsJson?.name ?? null,
    tickers: submissionsJson?.tickers || [],
    exchanges: submissionsJson?.exchanges || [],
    sic: submissionsJson?.sic ?? null,
    sic_description: submissionsJson?.sicDescription ?? null,
    fiscal_year_end: submissionsJson?.fiscalYearEnd ?? null,
    recent_filings: filings,
  };
}

export async function fetchSecFinancials(
  { ticker, cik, filings_limit } = {},
  { fetchImpl = fetch, contactEmail = "contact@x402-intel.dev", bypassTickerCache = false } = {},
) {
  const queryToken = String(ticker || cik || "").trim().toUpperCase();
  if (!queryToken) {
    throw new ValidationError("Provide either 'ticker' (e.g. AAPL) or 'cik' (e.g. 0000320193).");
  }
  const filingsLimit = clampInt(filings_limit, {
    defaultVal: 10,
    min: 1,
    max: 25,
    name: "filings_limit",
  });

  const headers = {
    "User-Agent": buildSecUserAgent(contactEmail),
    Accept: "application/json",
  };

  let cik10;
  const rawDigits = queryToken.startsWith("CIK") ? queryToken.slice(3).trim() : queryToken;
  if (/^\d{1,10}$/.test(rawDigits)) {
    cik10 = normalizeCik(rawDigits);
  } else {
    let map = !bypassTickerCache ? secTickerCache : null;
    if (!map) {
      const rawMap = await fetchJsonStrict("https://www.sec.gov/files/company_tickers.json", {
        fetchImpl,
        headers,
        source: "sec_company_tickers",
      });
      map = new Map();
      for (const entry of Object.values(rawMap || {})) {
        if (entry && entry.ticker && entry.cik_str !== undefined) {
          map.set(String(entry.ticker).toUpperCase(), String(entry.cik_str).padStart(10, "0"));
        }
      }
      if (!bypassTickerCache) secTickerCache = map;
    }
    cik10 = map.get(queryToken);
    if (!cik10) {
      throw new ValidationError(`Unknown SEC ticker symbol: "${queryToken}"`);
    }
  }

  const [submissionsJson, factsResult] = await Promise.all([
    fetchJsonStrict(`https://data.sec.gov/submissions/CIK${cik10}.json`, {
      fetchImpl,
      headers,
      source: "sec_edgar_submissions",
    }),
    (async () => {
      const url = `https://data.sec.gov/api/xbrl/companyfacts/CIK${cik10}.json`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      let resp;
      try {
        resp = await fetchImpl(url, { method: "GET", headers, signal: controller.signal });
      } catch (err) {
        throw new UpstreamError(
          `Upstream request failed for sec_edgar_companyfacts: ${err instanceof Error ? err.message : String(err)}`,
          { status: 502, source: "sec_edgar_companyfacts" },
        );
      } finally {
        clearTimeout(timer);
      }
      if (resp.status === 404) return { notAvailable: true, data: null };
      if (!resp.ok) {
        throw new UpstreamError(`Upstream sec_edgar_companyfacts returned HTTP ${resp.status}`, {
          status: 502,
          upstreamStatus: resp.status,
          source: "sec_edgar_companyfacts",
        });
      }
      try {
        return { notAvailable: false, data: await resp.json() };
      } catch (err) {
        throw new UpstreamError(
          `Upstream sec_edgar_companyfacts returned invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
          { status: 502, upstreamStatus: resp.status, source: "sec_edgar_companyfacts" },
        );
      }
    })(),
  ]);

  const parsedSub = parseSecSubmissions(submissionsJson, filingsLimit);
  const xbrl = factsResult.notAvailable
    ? { annual: {}, quarterly: {} }
    : extractSecFinancialsFromXbrl(factsResult.data);

  return {
    source: "sec_edgar_xbrl",
    status: "ok",
    query: queryToken,
    cik: parsedSub.cik,
    entity_name: parsedSub.entity_name,
    tickers: parsedSub.tickers,
    exchanges: parsedSub.exchanges,
    sic: parsedSub.sic,
    sic_description: parsedSub.sic_description,
    fiscal_year_end: parsedSub.fiscal_year_end,
    xbrl_status: factsResult.notAvailable ? "not_available" : "extracted",
    annual_financials: xbrl.annual,
    quarterly_financials: xbrl.quarterly,
    recent_filings: parsedSub.recent_filings,
  };
}

// ===========================================================================
// 2. SEC EFTS Form D Private Startup Funding Rounds (efts.sec.gov)
// ===========================================================================

function validateOptionalDate(raw, name) {
  const s = String(raw || "").trim();
  if (!s) return null;
  if (!ISO_DATE_RE.test(s) || Number.isNaN(Date.parse(`${s}T00:00:00Z`))) {
    throw new ValidationError(`Parameter '${name}' must use YYYY-MM-DD format, got "${raw}".`);
  }
  return s;
}

export async function fetchSecFormD(
  { q, limit, date_from, date_to } = {},
  { fetchImpl = fetch, contactEmail = "contact@x402-intel.dev" } = {},
) {
  const cleanedQ = String(q || "").trim() || null;
  const targetLimit = clampInt(limit, { defaultVal: 10, min: 1, max: 50, name: "limit" });
  const dateFrom = validateOptionalDate(date_from, "date_from");
  const dateTo = validateOptionalDate(date_to, "date_to");

  const url = new URL("https://efts.sec.gov/LATEST/search-index");
  url.searchParams.set("forms", "D,D/A");
  url.searchParams.set("from", "0");
  url.searchParams.set("size", String(targetLimit));
  if (cleanedQ) url.searchParams.set("q", cleanedQ);
  if (dateFrom || dateTo) {
    url.searchParams.set("dateRange", "custom");
    if (dateFrom) url.searchParams.set("startdt", dateFrom);
    if (dateTo) url.searchParams.set("enddt", dateTo);
  }

  const payload = await fetchJsonStrict(url.toString(), {
    fetchImpl,
    headers: {
      "User-Agent": buildSecUserAgent(contactEmail),
      Accept: "application/json",
    },
    source: "sec_efts_form_d",
  });

  const totalHits = Number(payload?.hits?.total?.value || 0);
  const rawHits = Array.isArray(payload?.hits?.hits) ? payload.hits.hits : [];

  const filings = rawHits.slice(0, targetLimit).map((hit) => {
    const src = hit?._source || {};
    const hitId = String(hit?._id || "");
    const primaryDoc = hitId.includes(":") ? hitId.split(":")[1] : "";
    const ciks = (Array.isArray(src.ciks) ? src.ciks : [])
      .map((c) => String(c).trim())
      .filter((c) => /^\d+$/.test(c))
      .map((c) => c.padStart(10, "0"));
    const displayNames = (Array.isArray(src.display_names) ? src.display_names : [])
      .map((n) => String(n).trim())
      .filter(Boolean);
    const entityName = displayNames[0]
      ? displayNames[0].replace(/\s*\(CIK\s*\d+\)\s*$/i, "").trim()
      : null;

    let adsh = String(src.adsh || "").trim();
    if (!adsh && hitId.includes(":")) adsh = hitId.split(":")[0].trim();

    let edgarUrl = null;
    let filingIndexUrl = null;
    if (ciks.length > 0 && adsh) {
      const cikNum = String(Number.parseInt(ciks[0], 10));
      const adshNoDash = adsh.replace(/-/g, "");
      filingIndexUrl = `https://www.sec.gov/Archives/edgar/data/${cikNum}/${adshNoDash}/${adsh}-index.htm`;
      edgarUrl = primaryDoc
        ? `https://www.sec.gov/Archives/edgar/data/${cikNum}/${adshNoDash}/${primaryDoc}`
        : filingIndexUrl;
    }

    return {
      entity_name: entityName,
      form: src.form ?? null,
      file_date: src.file_date ?? null,
      primary_cik: ciks[0] ?? null,
      ciks,
      accession_number: adsh || null,
      biz_locations: src.biz_locations || [],
      biz_states: src.biz_states || [],
      inc_states: src.inc_states || [],
      sics: src.sics || [],
      items: src.items || [],
      edgar_url: edgarUrl,
      filing_index_url: filingIndexUrl,
    };
  });

  return {
    source: "sec_efts_form_d",
    status: "ok",
    query: cleanedQ,
    date_from: dateFrom,
    date_to: dateTo,
    total_hits: totalHits,
    returned_count: filings.length,
    filings,
  };
}

// ===========================================================================
// 3. ATS Jobs (Greenhouse / Lever / Ashby)
// ===========================================================================

const SENIORITY_PATTERNS = [
  ["executive", /\b(?:chief\s+\w+\s+officer|cto|ceo|cfo|coo|ciso|vp|vice\s+president)\b/i],
  ["director", /\b(?:senior\s+director|head\s+of|director)\b/i],
  ["manager", /\b(?:engineering\s+manager|manager|em)\b/i],
  ["principal", /\b(?:distinguished|fellow|principal)\b/i],
  ["staff", /\b(?:senior\s+staff|staff)\b/i],
  ["lead", /\b(?:tech\s+lead|team\s+lead|lead)\b/i],
  ["senior", /\b(?:senior|sr\.?)\b/i],
  ["intern", /\b(?:intern|internship|co-op)\b/i],
  ["entry", /\b(?:junior|jr\.?|entry[- ]level|new\s+grad|associate)\b/i],
];

const TECH_TAG_PATTERNS = [
  ["Python", /\bpython\b/i],
  ["TypeScript", /\btypescript\b/i],
  ["JavaScript", /\bjavascript\b/i],
  ["Go", /\bgolang\b|\bGo\b(?=\s*[,/)|&]|\s+(?:or|and|engineer|developer|backend|services?))/],
  ["Rust", /\brust\b/i],
  ["C++", /(?:^|[^A-Za-z0-9])c\+\+(?=$|[^A-Za-z0-9])/i],
  ["Java", /\bjava\b/i],
  ["Kotlin", /\bkotlin\b/i],
  ["Swift", /\bswift\b/i],
  ["Ruby", /\bruby\b/i],
  ["SQL", /\bsql\b/i],
  ["PostgreSQL", /\bpostgres(?:ql)?\b/i],
  ["Redis", /\bredis\b/i],
  ["Kafka", /\bkafka\b/i],
  ["PyTorch", /\bpytorch\b/i],
  ["CUDA", /\bcuda\b/i],
  ["LLM", /\b(?:llms?|large\s+language\s+models?)\b/i],
  ["MCP", /\b(?:MCP|model\s+context\s+protocol)\b/],
  ["React", /\breact(?:\.js|js)?\b/i],
  ["Next.js", /\bnext\.?js\b/i],
  ["Node.js", /\bnode\.?js\b/i],
  ["GraphQL", /\bgraphql\b/i],
  ["Docker", /\bdocker\b/i],
  ["Kubernetes", /\b(?:kubernetes|k8s)\b/i],
  ["Terraform", /\bterraform\b/i],
  ["AWS", /\baws\b/i],
  ["GCP", /\b(?:gcp|google\s+cloud)\b/i],
  ["Solidity", /\bsolidity\b/i],
];

const SALARY_RANGE_RE =
  /([$£€]|USD\s*|EUR\s*|GBP\s*)(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?[kK])\s*(?:-|–|—|to)\s*(?:[$£€]|USD\s*|EUR\s*|GBP\s*)?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?[kK])/;

function parseSalaryNum(token) {
  let s = String(token || "").trim().replace(/,/g, "");
  let mult = 1;
  if (s.toLowerCase().endsWith("k")) {
    mult = 1000;
    s = s.slice(0, -1);
  }
  const n = Number(s);
  return Number.isFinite(n) ? Math.round(n * mult * 100) / 100 : null;
}

function extractSalary(text) {
  const m = SALARY_RANGE_RE.exec(String(text || ""));
  if (!m) return null;
  const low = parseSalaryNum(m[2]);
  const high = parseSalaryNum(m[3]);
  if (low === null || high === null || (low < 10000 && high < 10000)) return null;
  const rawCur = m[1].trim().toUpperCase();
  const curMap = { $: "USD", "£": "GBP", "€": "EUR" };
  return {
    currency: curMap[rawCur] || rawCur || "USD",
    min: Math.min(low, high),
    max: Math.max(low, high),
    interval: "yearly",
    summary: m[0].trim(),
  };
}

function inferSeniority(title) {
  for (const [level, re] of SENIORITY_PATTERNS) {
    if (re.test(title || "")) return level;
  }
  return null;
}

function extractTechTags(text) {
  const tags = [];
  for (const [tag, re] of TECH_TAG_PATTERNS) {
    if (re.test(text || "")) tags.push(tag);
  }
  return tags;
}

function classifyWorkplace(nativeType, isRemoteFlag, location, title, descPlain) {
  const native = String(nativeType || "").trim().toLowerCase().replace(/[-_]/g, "");
  if (native === "remote") return { workplace_type: "remote", is_remote: true };
  if (native === "hybrid") return { workplace_type: "hybrid", is_remote: false };
  if (native === "onsite" || native === "inoffice") {
    return { workplace_type: "onsite", is_remote: false };
  }
  if (isRemoteFlag === true) return { workplace_type: "remote", is_remote: true };

  const locTitle = `${location || ""} ${title || ""}`.toLowerCase();
  if (locTitle.includes("hybrid")) return { workplace_type: "hybrid", is_remote: false };
  if (/\b(?:remote|distributed|work\s+from\s+home|wfh|anywhere)\b/.test(locTitle)) {
    return { workplace_type: "remote", is_remote: true };
  }
  if (/\b(?:on-?site|in-?office)\b/.test(locTitle)) {
    return { workplace_type: "onsite", is_remote: false };
  }

  const body = String(descPlain || "").slice(0, 6000).toLowerCase();
  if (/\bhybrid\b/.test(body)) return { workplace_type: "hybrid", is_remote: false };
  if (/\b(?:fully\s+remote|100%\s+remote|remote-?first)\b/.test(body)) {
    return { workplace_type: "remote", is_remote: true };
  }
  if (/\b(?:in-?office|on-?site|in\s+person)\b/.test(body)) {
    return { workplace_type: "onsite", is_remote: false };
  }
  return { workplace_type: "unspecified", is_remote: false };
}

function trimExcerpt(text, maxChars = 400) {
  const s = String(text || "").trim();
  return s.length <= maxChars ? s : `${s.slice(0, maxChars).trimEnd()}...`;
}

function normalizeGreenhouseJobs(payload, slug) {
  const rawJobs = Array.isArray(payload?.jobs) ? payload.jobs : [];
  return rawJobs.map((item) => {
    const title = String(item?.title || "").trim();
    const location = String(item?.location?.name || "").trim();
    const depts = (Array.isArray(item?.departments) ? item.departments : [])
      .map((d) => String(d?.name || "").trim())
      .filter(Boolean);
    const descPlain = htmlToPlainText(item?.content || "");
    const wp = classifyWorkplace(null, null, location, title, descPlain);
    const salary = extractSalary(descPlain);
    const techTags = extractTechTags(`${title}\n${descPlain}`);
    const url = String(item?.absolute_url || "").trim() || null;

    return {
      job_id: String(item?.id ?? ""),
      provider: "greenhouse",
      company_slug: slug,
      title,
      department: depts[0] || null,
      team: null,
      location: location || null,
      workplace_type: wp.workplace_type,
      is_remote: wp.is_remote,
      employment_type: null,
      seniority: inferSeniority(title),
      salary,
      tech_tags: techTags,
      published_at: item?.first_published || item?.updated_at || null,
      url,
      apply_url: url,
      description_excerpt: trimExcerpt(descPlain),
      _search: `${title} ${depts.join(" ")} ${location} ${techTags.join(" ")} ${descPlain}`.toLowerCase(),
    };
  });
}

function normalizeLeverJobs(payload, slug) {
  if (!Array.isArray(payload)) return [];
  return payload.map((item) => {
    const title = String(item?.text || "").trim();
    const cats = item?.categories || {};
    const location = String(cats.location || "").trim();
    const department = String(cats.department || "").trim() || null;
    const team = String(cats.team || "").trim() || null;
    const descParts = [String(item?.descriptionPlain || "")];
    for (const sec of Array.isArray(item?.lists) ? item.lists : []) {
      descParts.push(String(sec?.text || ""));
      descParts.push(htmlToPlainText(sec?.content || ""));
    }
    descParts.push(String(item?.additionalPlain || ""));
    const descPlain = descParts.filter(Boolean).join("\n").trim();
    const wp = classifyWorkplace(item?.workplaceType, null, location, title, descPlain);

    let salary = null;
    const sr = item?.salaryRange;
    if (sr && (sr.min !== undefined || sr.max !== undefined)) {
      salary = {
        currency: sr.currency || "USD",
        min: sr.min ?? null,
        max: sr.max ?? null,
        interval: sr.interval || "yearly",
        summary: String(item?.salaryDescriptionPlain || "").trim() || null,
      };
    } else {
      salary = extractSalary(`${item?.salaryDescriptionPlain || ""}\n${descPlain}`);
    }

    const techTags = extractTechTags(`${title}\n${descPlain}`);
    const publishedAt =
      typeof item?.createdAt === "number" && item.createdAt > 0
        ? new Date(item.createdAt).toISOString()
        : null;

    return {
      job_id: String(item?.id ?? ""),
      provider: "lever",
      company_slug: slug,
      title,
      department,
      team,
      location: location || null,
      workplace_type: wp.workplace_type,
      is_remote: wp.is_remote,
      employment_type: cats.commitment || null,
      seniority: inferSeniority(title),
      salary,
      tech_tags: techTags,
      published_at: publishedAt,
      url: item?.hostedUrl || null,
      apply_url: item?.applyUrl || item?.hostedUrl || null,
      description_excerpt: trimExcerpt(descPlain),
      _search: `${title} ${department || ""} ${team || ""} ${location} ${techTags.join(" ")} ${descPlain}`.toLowerCase(),
    };
  });
}

function normalizeAshbyJobs(payload, slug) {
  const rawJobs = Array.isArray(payload?.jobs) ? payload.jobs : [];
  return rawJobs.map((item) => {
    const title = String(item?.title || "").trim();
    const location = String(item?.location || "").trim();
    const department = String(item?.department || "").trim() || null;
    const team = String(item?.team || "").trim() || null;
    const descPlain =
      String(item?.descriptionPlain || "").trim() || htmlToPlainText(item?.descriptionHtml || "");
    const wp = classifyWorkplace(
      item?.workplaceType,
      typeof item?.isRemote === "boolean" ? item.isRemote : null,
      location,
      title,
      descPlain,
    );

    let salary = null;
    const comp = item?.compensation;
    if (comp && typeof comp === "object") {
      const summary = String(
        comp.compensationTierSummary || comp.scrapeableCompensationSalarySummary || "",
      ).trim();
      const firstComp = (Array.isArray(comp.summaryComponents) ? comp.summaryComponents : []).find(
        (sc) => sc && (sc.minValue !== undefined || sc.maxValue !== undefined),
      );
      if (firstComp) {
        salary = {
          currency: firstComp.currencyCode || "USD",
          min: firstComp.minValue ?? null,
          max: firstComp.maxValue ?? null,
          interval: firstComp.interval || "yearly",
          summary: summary || null,
        };
      } else if (summary) {
        salary = extractSalary(summary) || {
          currency: null,
          min: null,
          max: null,
          interval: null,
          summary,
        };
      }
    }
    if (!salary) salary = extractSalary(descPlain);

    const techTags = extractTechTags(`${title}\n${descPlain}`);
    return {
      job_id: String(item?.id ?? ""),
      provider: "ashby",
      company_slug: slug,
      title,
      department,
      team,
      location: location || null,
      workplace_type: wp.workplace_type,
      is_remote: wp.is_remote,
      employment_type: item?.employmentType || null,
      seniority: inferSeniority(title),
      salary,
      tech_tags: techTags,
      published_at: item?.publishedAt || null,
      url: item?.jobUrl || null,
      apply_url: item?.applyUrl || item?.jobUrl || null,
      description_excerpt: trimExcerpt(descPlain),
      _search: `${title} ${department || ""} ${team || ""} ${location} ${techTags.join(" ")} ${descPlain}`.toLowerCase(),
    };
  });
}

export async function fetchAtsJobs(
  { provider, slug, limit, remote_only, keyword } = {},
  { fetchImpl = fetch } = {},
) {
  const prov = String(provider || "").trim().toLowerCase();
  if (!["greenhouse", "lever", "ashby"].includes(prov)) {
    throw new ValidationError(
      `Unsupported ATS provider "${provider}". Expected one of: greenhouse, lever, ashby.`,
    );
  }
  const cleanSlug = String(slug || "").trim();
  if (!cleanSlug || !SLUG_RE.test(cleanSlug) || cleanSlug.includes("..")) {
    throw new ValidationError(`Invalid ATS board slug: "${slug}".`);
  }
  const targetLimit = clampInt(limit, { defaultVal: 20, min: 1, max: 100, name: "limit" });
  const remoteOnly = parseBool(remote_only, false);
  const needle = String(keyword || "").trim().toLowerCase();

  let endpoint;
  if (prov === "greenhouse") {
    endpoint = `https://boards-api.greenhouse.io/v1/boards/${encodeURIComponent(cleanSlug)}/jobs?content=true`;
  } else if (prov === "lever") {
    endpoint = `https://api.lever.co/v0/postings/${encodeURIComponent(cleanSlug)}?mode=json`;
  } else {
    endpoint = `https://api.ashbyhq.com/posting-api/job-board/${encodeURIComponent(cleanSlug)}?includeCompensation=true`;
  }

  const payload = await fetchJsonStrict(endpoint, {
    fetchImpl,
    headers: {
      "User-Agent": "x402IntelWorker/1.0 (+https://github.com/pecopeko/x402-intel-worker)",
      Accept: "application/json",
    },
    source: `ats_${prov}`,
  });

  const allJobs =
    prov === "greenhouse"
      ? normalizeGreenhouseJobs(payload, cleanSlug)
      : prov === "lever"
        ? normalizeLeverJobs(payload, cleanSlug)
        : normalizeAshbyJobs(payload, cleanSlug);

  const filtered = allJobs
    .filter((j) => (!remoteOnly || j.is_remote) && (!needle || j._search.includes(needle)))
    .map(({ _search, ...clean }) => clean);

  const returned = filtered.slice(0, targetLimit);
  return {
    source: `ats_${prov}`,
    status: "ok",
    provider: prov,
    company_slug: cleanSlug,
    api_url: endpoint,
    total_board_jobs: allJobs.length,
    matched_count: filtered.length,
    returned_count: returned.length,
    summary: {
      remote_count: allJobs.filter((j) => j.workplace_type === "remote").length,
      hybrid_count: allJobs.filter((j) => j.workplace_type === "hybrid").length,
      onsite_count: allJobs.filter((j) => j.workplace_type === "onsite").length,
      with_salary_count: allJobs.filter((j) => j.salary !== null).length,
    },
    jobs: returned,
  };
}

// ===========================================================================
// 4. Web Tech Stack & AI Crawler Readiness Audit (Strict SSRF-Safe)
// ===========================================================================

function detectTechStack(headersMap, html) {
  const h = (name) => String(headersMap[name.toLowerCase()] || "");
  const server = h("server").toLowerCase();
  const poweredBy = h("x-powered-by").toLowerCase();
  const via = h("via").toLowerCase();
  const allHeaders = JSON.stringify(headersMap).toLowerCase();
  const sample = String(html || "").slice(0, 180000);

  const cdn = new Set();
  const frameworks = new Set();
  const analytics = new Set();
  const paymentsAndEdge = new Set();

  if (h("cf-ray") || server.includes("cloudflare")) cdn.add("Cloudflare");
  if (h("x-vercel-id") || server.includes("vercel")) cdn.add("Vercel");
  if (h("x-nf-request-id") || server.includes("netlify")) cdn.add("Netlify");
  if (h("x-served-by").includes("cache-") || via.includes("varnish") || h("fastly-debug-digest")) {
    cdn.add("Fastly");
  }
  if (h("x-amz-cf-id") || via.includes("cloudfront")) cdn.add("AWS CloudFront");
  if (h("x-akamai-transformed") || server.includes("akamai")) cdn.add("Akamai");
  if (server.includes("github.com") || h("x-github-request-id")) cdn.add("GitHub Pages");
  if (h("fly-request-id") || server.includes("fly/")) cdn.add("Fly.io");
  if (h("x-shopify-stage") || allHeaders.includes("shopify")) cdn.add("Shopify");
  if (server.includes("nginx")) cdn.add("Nginx");
  if (server.includes("envoy")) cdn.add("Envoy");

  if (poweredBy.includes("next.js") || /__NEXT_DATA__|\/_next\/static\//i.test(sample)) {
    frameworks.add("Next.js");
  }
  if (/window\.__NUXT__|\/_nuxt\//i.test(sample)) frameworks.add("Nuxt");
  if (/astro-island|generator["']?\s+content=["']Astro/i.test(sample)) frameworks.add("Astro");
  if (/__remixContext/i.test(sample)) frameworks.add("Remix");
  if (/data-reactroot|__REACT_DEVTOOLS|react-dom/i.test(sample)) frameworks.add("React");
  if (/data-v-[0-9a-f]{6,}|vue\.runtime/i.test(sample)) frameworks.add("Vue.js");
  if (/svelte-[a-z0-9]+|__sveltekit/i.test(sample)) frameworks.add("Svelte");
  if (/wp-content\/|wp-includes\//i.test(sample)) frameworks.add("WordPress");
  if (/webflow\.com|data-wf-site=/i.test(sample)) frameworks.add("Webflow");
  if (/framerusercontent\.com|data-framer-/i.test(sample)) frameworks.add("Framer");
  if (/tailwindcss|--tw-ring-color/i.test(sample)) frameworks.add("Tailwind CSS");

  if (/googletagmanager\.com\/gtm\.js/i.test(sample)) analytics.add("Google Tag Manager");
  if (/googletagmanager\.com\/gtag\/js|google-analytics\.com/i.test(sample)) {
    analytics.add("Google Analytics");
  }
  if (/cdn\.segment\.com/i.test(sample)) analytics.add("Segment");
  if (/posthog\.com|us\.i\.posthog\.com/i.test(sample)) analytics.add("PostHog");
  if (/plausible\.io\/js\//i.test(sample)) analytics.add("Plausible");
  if (/sentry\.io|browser\.sentry-cdn\.com/i.test(sample)) analytics.add("Sentry");
  if (/widget\.intercom\.io/i.test(sample)) analytics.add("Intercom");
  if (/js\.hs-scripts\.com|hubspot\.com/i.test(sample)) analytics.add("HubSpot");

  if (/js\.stripe\.com/i.test(sample)) paymentsAndEdge.add("Stripe.js");
  if (/challenges\.cloudflare\.com\/turnstile/i.test(sample)) {
    paymentsAndEdge.add("Cloudflare Turnstile");
  }

  return {
    cdn_hosting: [...cdn],
    frameworks: [...frameworks],
    analytics: [...analytics],
    payments_and_security_widgets: [...paymentsAndEdge],
  };
}

function auditSecurityHeaders(headersMap) {
  const checks = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
  ];
  const present = checks.filter((k) => Boolean(headersMap[k]));
  const missing = checks.filter((k) => !headersMap[k]);
  return {
    score: Math.round((present.length / checks.length) * 100),
    present,
    missing,
  };
}

function parseRobotsAiDirectives(robotsText) {
  const sitemaps = [];
  const aiBots = {};
  const watchedBots = ["gptbot", "claudebot", "anthropic-ai", "perplexitybot", "google-extended", "ccbot"];
  let currentAgents = [];

  for (const rawLine of String(robotsText || "").split(/\r?\n/)) {
    const line = rawLine.split("#")[0].trim();
    if (!line) continue;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const key = line.slice(0, colon).trim().toLowerCase();
    const val = line.slice(colon + 1).trim();

    if (key === "sitemap" && val) {
      sitemaps.push(val);
    } else if (key === "user-agent") {
      currentAgents = [val.toLowerCase()];
    } else if (key === "disallow" || key === "allow") {
      for (const ag of currentAgents) {
        if (watchedBots.includes(ag)) {
          if (!aiBots[ag]) aiBots[ag] = [];
          aiBots[ag].push(`${key}: ${val}`);
        }
      }
    }
  }
  return { sitemaps: sitemaps.slice(0, 10), ai_bot_rules: aiBots };
}

async function probeWellKnownText(originUrl, path, { fetchImpl, headers }) {
  const target = `${originUrl}${path}`;
  try {
    const { response } = await safePublicFetch(target, {
      fetchImpl,
      headers,
      maxRedirects: 3,
      timeoutMs: 6000,
    });
    const contentType = response.headers.get("content-type") || "";
    const isOk = response.status >= 200 && response.status < 300;
    const text = isOk ? await readBoundedText(response, 65536) : "";
    return {
      url: target,
      present: isOk && text.trim().length > 0,
      status: response.status,
      content_type: contentType || null,
      byte_preview_length: text.length,
      text,
    };
  } catch (err) {
    return {
      url: target,
      present: false,
      status: null,
      error: err instanceof Error ? err.message : String(err),
      text: "",
    };
  }
}

export async function fetchWebTechStack({ url } = {}, { fetchImpl = fetch } = {}) {
  const safeUrl = assertSafePublicUrl(url);
  const reqHeaders = {
    "User-Agent": "x402IntelWorker/1.0 (+https://github.com/pecopeko/x402-intel-worker)",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  };

  let mainFetch;
  try {
    mainFetch = await safePublicFetch(safeUrl, {
      fetchImpl,
      headers: reqHeaders,
      maxRedirects: 4,
      timeoutMs: 10000,
    });
  } catch (err) {
    if (err && err.name === "SSRFError") throw err;
    throw new UpstreamError(
      `Failed to fetch target URL: ${err instanceof Error ? err.message : String(err)}`,
      { status: 502, source: "web_tech_stack_audit" },
    );
  }

  const { response, finalUrl, redirectChain } = mainFetch;
  const headersMap = {};
  for (const [k, v] of response.headers.entries()) {
    headersMap[k.toLowerCase()] = v;
  }

  const html = await readBoundedText(response, 262144);
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const metaDescMatch = html.match(
    /<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i,
  );
  const generatorMatch = html.match(
    /<meta[^>]+name=["']generator["'][^>]+content=["']([^"']+)["']/i,
  );

  const origin = new URL(finalUrl).origin;
  const [robotsProbe, sitemapProbe, llmsProbe] = await Promise.all([
    probeWellKnownText(origin, "/robots.txt", { fetchImpl, headers: reqHeaders }),
    probeWellKnownText(origin, "/sitemap.xml", { fetchImpl, headers: reqHeaders }),
    probeWellKnownText(origin, "/llms.txt", { fetchImpl, headers: reqHeaders }),
  ]);

  const robotsParsed = robotsProbe.present
    ? parseRobotsAiDirectives(robotsProbe.text)
    : { sitemaps: [], ai_bot_rules: {} };
  const sitemapLocCount = sitemapProbe.present
    ? (sitemapProbe.text.match(/<loc>/gi) || []).length
    : 0;
  const llmsFirstLine = llmsProbe.present
    ? llmsProbe.text
        .split(/\r?\n/)
        .map((l) => l.trim())
        .find(Boolean) || null
    : null;

  return {
    source: "web_tech_stack_audit",
    status: "ok",
    requested_url: safeUrl,
    final_url: finalUrl,
    http_status: response.status,
    redirects: redirectChain,
    page_metadata: {
      title: titleMatch ? decodeHtmlEntities(titleMatch[1]).replace(/\s+/g, " ").trim() : null,
      description: metaDescMatch ? decodeHtmlEntities(metaDescMatch[1]).trim() : null,
      generator: generatorMatch ? decodeHtmlEntities(generatorMatch[1]).trim() : null,
      content_type: headersMap["content-type"] || null,
      server: headersMap.server || null,
    },
    tech_stack: detectTechStack(headersMap, html),
    security_headers: auditSecurityHeaders(headersMap),
    crawler_readiness: {
      robots_txt: {
        url: robotsProbe.url,
        present: robotsProbe.present,
        status: robotsProbe.status,
        declared_sitemaps: robotsParsed.sitemaps,
        ai_bot_rules: robotsParsed.ai_bot_rules,
      },
      sitemap_xml: {
        url: sitemapProbe.url,
        present: sitemapProbe.present,
        status: sitemapProbe.status,
        loc_entries_in_preview: sitemapLocCount,
      },
      llms_txt: {
        url: llmsProbe.url,
        present: llmsProbe.present,
        status: llmsProbe.status,
        heading_preview: llmsFirstLine,
        byte_preview_length: llmsProbe.byte_preview_length || 0,
      },
    },
  };
}

// ===========================================================================
// 5. Japan NTA Qualified Invoice Modulo-9 + Corporate ID + Zengin CP932
// ===========================================================================

const LEGAL_ABBREVIATIONS = [
  { pattern: "認定特定非営利活動法人", abbr: "ﾄｸﾋ" },
  { pattern: "特定非営利活動法人", abbr: "ﾄｸﾋ" },
  { pattern: "NPO法人", abbr: "ﾄｸﾋ" },
  { pattern: "一般社団法人", abbr: "ｼﾔ" },
  { pattern: "公益社団法人", abbr: "ｼﾔ" },
  { pattern: "一般財団法人", abbr: "ｻﾞｲ" },
  { pattern: "公益財団法人", abbr: "ｻﾞｲ" },
  { pattern: "医療法人社団", abbr: "ｲ" },
  { pattern: "医療法人財団", abbr: "ｲ" },
  { pattern: "社会福祉法人", abbr: "ﾌｸ" },
  { pattern: "税理士法人", abbr: "ｾﾞｲ" },
  { pattern: "弁護士法人", abbr: "ﾍﾞﾝ" },
  { pattern: "司法書士法人", abbr: "ｼﾎ" },
  { pattern: "株式会社", abbr: "ｶ" },
  { pattern: "有限会社", abbr: "ﾕ" },
  { pattern: "合同会社", abbr: "ﾄﾞ" },
  { pattern: "合名会社", abbr: "ﾒ" },
  { pattern: "合資会社", abbr: "ｼ" },
  { pattern: "医療法人", abbr: "ｲ" },
  { pattern: "学校法人", abbr: "ｶﾞｸ" },
  { pattern: "監査法人", abbr: "ｶﾝｻ" },
  { pattern: "(株)", abbr: "ｶ" },
  { pattern: "(有)", abbr: "ﾕ" },
  { pattern: "(同)", abbr: "ﾄﾞ" },
  { pattern: "㈱", abbr: "ｶ" },
  { pattern: "㈲", abbr: "ﾕ" },
];

const ZENGIN_KANA_MAP = {
  ア: "ｱ", イ: "ｲ", ウ: "ｳ", エ: "ｴ", オ: "ｵ",
  ァ: "ｱ", ィ: "ｲ", ゥ: "ｳ", ェ: "ｴ", ォ: "ｵ",
  カ: "ｶ", キ: "ｷ", ク: "ｸ", ケ: "ｹ", コ: "ｺ",
  サ: "ｻ", シ: "ｼ", ス: "ｽ", セ: "ｾ", ソ: "ｿ",
  タ: "ﾀ", チ: "ﾁ", ツ: "ﾂ", テ: "ﾃ", ト: "ﾄ", ッ: "ﾂ",
  ナ: "ﾅ", ニ: "ﾆ", ヌ: "ﾇ", ネ: "ﾈ", ノ: "ﾉ",
  ハ: "ﾊ", ヒ: "ﾋ", フ: "ﾌ", ヘ: "ﾍ", ホ: "ﾎ",
  マ: "ﾏ", ミ: "ﾐ", ム: "ﾑ", メ: "ﾒ", モ: "ﾓ",
  ヤ: "ﾔ", ユ: "ﾕ", ヨ: "ﾖ", ャ: "ﾔ", ュ: "ﾕ", ョ: "ﾖ",
  ラ: "ﾗ", リ: "ﾘ", ル: "ﾙ", レ: "ﾚ", ロ: "ﾛ",
  ワ: "ﾜ", ヲ: "ｦ", ン: "ﾝ", ヮ: "ﾜ", ヵ: "ｶ", ヶ: "ｹ",
  ガ: "ｶﾞ", ギ: "ｷﾞ", グ: "ｸﾞ", ゲ: "ｹﾞ", ゴ: "ｺﾞ",
  ザ: "ｻﾞ", ジ: "ｼﾞ", ズ: "ｽﾞ", ゼ: "ｾﾞ", ゾ: "ｿﾞ",
  ダ: "ﾀﾞ", ヂ: "ﾁﾞ", ヅ: "ﾂﾞ", デ: "ﾃﾞ", ド: "ﾄﾞ",
  バ: "ﾊﾞ", ビ: "ﾋﾞ", ブ: "ﾌﾞ", ベ: "ﾍﾞ", ボ: "ﾎﾞ",
  パ: "ﾊﾟ", ピ: "ﾋﾟ", プ: "ﾌﾟ", ペ: "ﾍﾟ", ポ: "ﾎﾟ",
  ヴ: "ｳﾞ",
  ｧ: "ｱ", ｨ: "ｲ", ｩ: "ｳ", ｪ: "ｴ", ｫ: "ｵ", ｯ: "ﾂ", ｬ: "ﾔ", ｭ: "ﾕ", ｮ: "ﾖ",
  ー: "-", ｰ: "-", "－": "-", "―": "-", "−": "-", "‐": "-",
  "　": " ", "．": ".", "（": "(", "）": ")", "／": "/", "，": ",", "、": ",", "・": ".",
  "「": "｢", "」": "｣", "¥": "\\", "￥": "\\",
};

const ZENGIN_LEGAL_CHAR_RE = /^[A-Z0-9ｦｱ-ﾝﾞﾟ \-.()\/,\\｢｣]$/;

function toHalfWidthAscii(raw) {
  return String(raw ?? "").replace(/[！-～]/g, (ch) =>
    String.fromCharCode(ch.charCodeAt(0) - 0xfee0),
  );
}

/**
 * Verify 13-digit Japanese Corporate Number via official NTA Modulo-9 formula:
 *   check_digit = 9 - (sum_{i=1..12} q_i * (i % 2 === 1 ? 1 : 2)) % 9
 */
export function verifyNtaCorporateNumber(rawDigits) {
  const digits = toHalfWidthAscii(rawDigits).replace(/[-\s]/g, "");
  if (!/^\d{13}$/.test(digits)) {
    return {
      valid: false,
      normalized: digits,
      actual_check_digit: null,
      expected_check_digit: null,
      reason: "Japanese Corporate Number must be exactly 13 digits.",
    };
  }
  const actualCheck = Number(digits[0]);
  let weightedSum = 0;
  for (let i = 1; i <= 12; i += 1) {
    const q = Number(digits[13 - i]);
    weightedSum += q * (i % 2 === 1 ? 1 : 2);
  }
  const expectedCheck = 9 - (weightedSum % 9);
  const valid = actualCheck === expectedCheck;
  const suggestedCorp = `${expectedCheck}${digits.slice(1)}`;
  return {
    valid,
    normalized: digits,
    actual_check_digit: actualCheck,
    expected_check_digit: expectedCheck,
    suggested_corporate_number: valid ? digits : suggestedCorp,
    reason: valid
      ? "Valid NTA Modulo-9 check digit."
      : `Check digit mismatch: expected ${expectedCheck}, got ${actualCheck}.`,
  };
}

function applyZenginPositionalAbbreviations(str) {
  const trimmed = str.replace(/　/g, " ").trim();
  if (!trimmed) return "";

  const matches = [];
  let cursor = 0;
  while (cursor < trimmed.length) {
    let found = null;
    for (const entry of LEGAL_ABBREVIATIONS) {
      if (trimmed.startsWith(entry.pattern, cursor)) {
        found = entry;
        break;
      }
    }
    if (found) {
      matches.push({ start: cursor, end: cursor + found.pattern.length, abbr: found.abbr });
      cursor += found.pattern.length;
    } else {
      cursor += 1;
    }
  }
  if (matches.length === 0) return trimmed;

  let out = "";
  let pos = 0;
  for (const m of matches) {
    let before = trimmed.slice(pos, m.start);
    const hasBefore = trimmed.slice(0, m.start).trim().length > 0;
    const hasAfter = trimmed.slice(m.end).trim().length > 0;
    let repl;
    if (!hasBefore && hasAfter) {
      repl = `${m.abbr})`;
    } else if (hasBefore && !hasAfter) {
      before = before.replace(/\s+$/, "");
      repl = `(${m.abbr}`;
    } else {
      before = before.replace(/\s+$/, "");
      repl = `(${m.abbr})`;
    }
    out += before + repl;
    pos = m.end;
    if (hasAfter) {
      while (pos < trimmed.length && /\s/.test(trimmed[pos])) pos += 1;
    }
  }
  out += trimmed.slice(pos);
  return out;
}

export function normalizeZenginCp932(rawName, { maxLength = 30 } = {}) {
  const widthNorm = toHalfWidthAscii(String(rawName ?? "")).toUpperCase();
  const withLegal = applyZenginPositionalAbbreviations(widthNorm);

  const outChars = [];
  const unsupportedChars = [];
  for (const rawCh of withLegal) {
    const code = rawCh.charCodeAt(0);
    const ch = code >= 0x3041 && code <= 0x3096 ? String.fromCharCode(code + 0x60) : rawCh;
    if (Object.prototype.hasOwnProperty.call(ZENGIN_KANA_MAP, ch)) {
      outChars.push(ZENGIN_KANA_MAP[ch]);
    } else if (ZENGIN_LEGAL_CHAR_RE.test(ch)) {
      outChars.push(ch);
    } else {
      unsupportedChars.push(rawCh);
    }
  }

  let normalized = outChars.join("").replace(/\s{2,}/g, " ").trim();
  const truncated = normalized.length > maxLength;
  let dakutenSafeAdjusted = false;
  if (truncated) {
    let cut = maxLength;
    if (cut > 0 && (normalized[cut] === "ﾞ" || normalized[cut] === "ﾟ")) {
      cut -= 1;
      dakutenSafeAdjusted = true;
    }
    normalized = normalized.slice(0, cut).trimEnd();
  }

  // Encode exact CP932 / JIS X 0201 single-byte representation
  const cp932Bytes = [];
  for (let i = 0; i < normalized.length; i += 1) {
    const c = normalized.charCodeAt(i);
    if (c >= 0x20 && c <= 0x7e) cp932Bytes.push(c);
    else if (c === 0x00a5) cp932Bytes.push(0x5c);
    else if (c >= 0xff61 && c <= 0xff9f) cp932Bytes.push(c - 0xff61 + 0xa1);
  }
  const cp932Hex = cp932Bytes.map((b) => b.toString(16).toUpperCase().padStart(2, "0")).join(" ");

  return {
    input: String(rawName ?? ""),
    zengin_kana: normalized,
    cp932_byte_length: cp932Bytes.length,
    cp932_hex: cp932Hex,
    truncated,
    dakuten_safe_adjusted: dakutenSafeAdjusted,
    unsupported_characters: unsupportedChars,
    bank_ready: normalized.length > 0 && unsupportedChars.length === 0 && cp932Bytes.length <= maxLength,
  };
}

export function verifyJapanInvoiceAndZengin({ t_number, payee_name, name } = {}) {
  const rawId = String(t_number || "").trim();
  const rawPayee = String(payee_name ?? name ?? "").trim();
  if (!rawId && !rawPayee) {
    throw new ValidationError(
      "Provide 't_number' (e.g. T7000012050002 or 13-digit corporate ID) and/or 'payee_name'.",
    );
  }

  let invoice = null;
  if (rawId) {
    const compact = toHalfWidthAscii(rawId).replace(/[-\s]/g, "").toUpperCase();
    const isTFormat = compact.startsWith("T");
    const digitsOnly = isTFormat ? compact.slice(1) : compact;
    const mod9 = verifyNtaCorporateNumber(digitsOnly);
    const validFormat = isTFormat ? /^T\d{13}$/.test(compact) : /^\d{13}$/.test(compact);
    invoice = {
      input: rawId,
      kind: isTFormat ? "qualified_invoice_t_number" : "corporate_number",
      format_valid: validFormat,
      valid: validFormat && mod9.valid,
      normalized_t_number: /^\d{13}$/.test(digitsOnly) ? `T${digitsOnly}` : null,
      corporate_number: /^\d{13}$/.test(digitsOnly) ? digitsOnly : null,
      actual_check_digit: mod9.actual_check_digit,
      expected_check_digit: mod9.expected_check_digit,
      suggested_t_number:
        mod9.suggested_corporate_number ? `T${mod9.suggested_corporate_number}` : null,
      reason: validFormat
        ? mod9.reason
        : "Expected T + 13 digits (Qualified Invoice ID) or 13 digits (Corporate Number).",
    };
  }

  const zengin = rawPayee ? normalizeZenginCp932(rawPayee) : null;

  return {
    source: "jp_nta_zengin_deterministic",
    status: "ok",
    invoice,
    zengin,
  };
}

/**
 * Route dispatcher shared by HTTP REST routes and Streamable HTTP MCP tools/call.
 */
export async function executeIntelRoute(routeId, params, { fetchImpl = fetch, config } = {}) {
  switch (routeId) {
    case "sec_financials":
      return fetchSecFinancials(params, {
        fetchImpl,
        contactEmail: config.secContactEmail,
        bypassTickerCache: fetchImpl !== fetch,
      });
    case "sec_form_d":
      return fetchSecFormD(params, {
        fetchImpl,
        contactEmail: config.secContactEmail,
      });
    case "ats_jobs":
      return fetchAtsJobs(params, { fetchImpl });
    case "web_tech_stack":
      return fetchWebTechStack(params, { fetchImpl });
    case "jp_invoice_verify":
      return verifyJapanInvoiceAndZengin(params);
    default:
      throw new ValidationError(`Unknown intelligence route: "${routeId}"`);
  }
}
