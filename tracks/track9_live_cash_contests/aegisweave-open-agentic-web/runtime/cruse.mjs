/**
 * AegisWeave CRUSE v1 Generative UI Validator & Safe HTML Renderer
 * (MVP Profile 0.3 Section 7 Extension: agent-proposed tables, choices,
 *  forms, info cards, reports, charts, and sanitized HTML validated and
 *  rendered safely by the browser runtime.)
 */

const ALLOWED_KINDS = new Set(["table", "choice", "form", "info", "report", "chart", "html"]);

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Strips scripts, styles, iframes, images, form controls, inline event handlers, and javascript: URLs.
 */
export function sanitizeCruseHtml(rawHtml) {
  let cleaned = String(rawHtml ?? "");
  cleaned = cleaned.replace(/<(script|style|iframe|object|embed|form|input|button|textarea|select|img)[^>]*>[\s\S]*?<\/\1>/gi, "");
  cleaned = cleaned.replace(/<(script|style|iframe|object|embed|form|input|button|textarea|select|img)[^>]*\/?>/gi, "");
  cleaned = cleaned.replace(/\son[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, "");
  cleaned = cleaned.replace(/javascript\s*:/gi, "blocked:");
  return cleaned;
}

export function validateCrusePayload(payload) {
  const errors = [];
  if (!payload || typeof payload !== "object") {
    return { valid: false, errors: ["CRUSE payload must be an object."] };
  }
  if (payload.version !== 1) {
    errors.push(`Unsupported CRUSE version: ${payload.version}. Expected 1.`);
  }
  if (!Array.isArray(payload.components)) {
    errors.push("CRUSE payload must include a 'components' array.");
  } else {
    payload.components.forEach((comp, idx) => {
      if (!comp || typeof comp !== "object") {
        errors.push(`components[${idx}] must be an object.`);
        return;
      }
      if (!comp.id || typeof comp.id !== "string") {
        errors.push(`components[${idx}] must have a stable string 'id'.`);
      }
      if (!ALLOWED_KINDS.has(comp.kind)) {
        errors.push(`components[${idx}] has unsupported kind '${comp.kind}'.`);
      }
      if (comp.kind === "table" && (!Array.isArray(comp.columns) || !Array.isArray(comp.rows))) {
        errors.push(`components[${idx}] (table) requires columns[] and rows[].`);
      }
      if (comp.kind === "chart" && (!Array.isArray(comp.labels) || !Array.isArray(comp.series))) {
        errors.push(`components[${idx}] (chart) requires labels[] and series[].`);
      }
      if (comp.kind === "info" && (!comp.fields || typeof comp.fields !== "object")) {
        errors.push(`components[${idx}] (info) requires a fields object.`);
      }
    });
  }
  return { valid: errors.length === 0, errors };
}

export function renderCruseToHtml(payload) {
  const check = validateCrusePayload(payload);
  if (!check.valid) {
    return `<div class="cruse-error">Invalid CRUSE payload: ${escapeHtml(check.errors.join(" "))}</div>`;
  }

  return payload.components
    .map((comp) => {
      const titleHtml = comp.title ? `<div class="cruse-title">${escapeHtml(comp.title)}</div>` : "";
      if (comp.kind === "info") {
        const rows = Object.entries(comp.fields)
          .map(
            ([k, v]) =>
              `<div class="cruse-kv"><span class="cruse-k">${escapeHtml(k)}</span><span class="cruse-v">${escapeHtml(v)}</span></div>`
          )
          .join("");
        return `<section class="cruse-card cruse-info" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<div class="cruse-kv-grid">${rows}</div></section>`;
      }

      if (comp.kind === "table") {
        const headers = comp.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
        const body = comp.rows
          .map(
            (row) =>
              `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`
          )
          .join("");
        return `<section class="cruse-card cruse-table" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<div class="cruse-table-wrap"><table><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table></div></section>`;
      }

      if (comp.kind === "chart") {
        const allValues = comp.series.flatMap((s) => (Array.isArray(s.values) ? s.values : [])).filter((v) => typeof v === "number");
        const maxVal = Math.max(1, ...allValues);
        const unit = comp.unit ? ` ${escapeHtml(comp.unit)}` : "";
        const bars = comp.labels
          .map((label, idx) => {
            const val = comp.series[0]?.values?.[idx] ?? 0;
            const pct = Math.max(4, Math.round((val / maxVal) * 100));
            return `<div class="cruse-bar-row"><span class="cruse-bar-label">${escapeHtml(label)}</span><div class="cruse-bar-track"><div class="cruse-bar-fill" style="width:${pct}%"></div></div><span class="cruse-bar-val">${escapeHtml(val)}${unit}</span></div>`;
          })
          .join("");
        const summary = comp.summary ? `<div class="cruse-summary">${escapeHtml(comp.summary)}</div>` : "";
        return `<section class="cruse-card cruse-chart" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<div class="cruse-bars">${bars}</div>${summary}</section>`;
      }

      if (comp.kind === "choice") {
        const opts = (comp.options || [])
          .map(
            (opt) =>
              `<button type="button" class="cruse-choice-btn" data-choice-value="${escapeHtml(opt.value)}"><strong>${escapeHtml(opt.title)}</strong>${opt.subtitle ? `<span>${escapeHtml(opt.subtitle)}</span>` : ""}${opt.meta ? `<em>${escapeHtml(opt.meta)}</em>` : ""}</button>`
          )
          .join("");
        return `<section class="cruse-card cruse-choice" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<div class="cruse-choice-list">${opts}</div></section>`;
      }

      if (comp.kind === "report") {
        return `<section class="cruse-card cruse-report" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<pre class="cruse-markdown">${escapeHtml(comp.markdown || "")}</pre></section>`;
      }

      if (comp.kind === "html") {
        return `<section class="cruse-card cruse-html" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}${sanitizeCruseHtml(comp.html || "")}</section>`;
      }

      if (comp.kind === "form") {
        const props = comp.schema?.properties || {};
        const fields = Object.entries(props)
          .map(([k, spec]) => {
            const label = escapeHtml(spec.title || k);
            const def = spec.default !== undefined ? escapeHtml(spec.default) : "";
            return `<label class="cruse-field"><span>${label}</span><input name="${escapeHtml(k)}" value="${def}" /></label>`;
          })
          .join("");
        return `<section class="cruse-card cruse-form" data-cruse-id="${escapeHtml(comp.id)}">${titleHtml}<form class="cruse-form-inner" data-form-id="${escapeHtml(comp.id)}">${fields}<button type="submit">${escapeHtml(comp.submitLabel || "Submit")}</button></form></section>`;
      }

      return "";
    })
    .join("\n");
}
