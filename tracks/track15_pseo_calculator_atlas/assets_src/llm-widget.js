/**
 * Interactive Client-Side LLM API Cost Calculator Widget
 * Supports both Head-to-Head Model Comparison mode and All-Model Workload mode.
 * Zero external dependencies, live custom price overrides, and inline SVG cost chart.
 */
(function () {
  'use strict';

  function fmtUsd(val) {
    if (!Number.isFinite(val)) return '$0.00';
    if (val >= 1000) return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (val >= 1) return '$' + val.toFixed(2);
    if (val >= 0.01) return '$' + val.toFixed(3);
    return '$' + val.toFixed(4);
  }

  function fmtJpy(val) {
    if (!Number.isFinite(val)) return '¥0';
    return '¥' + Math.round(val).toLocaleString('ja-JP');
  }

  function calcCost(m, inputM, outputM, cacheRatio, useBatch, isJapanese, usdJpy) {
    var langMult = isJapanese ? (m.jp_token_multiplier || 1.8) : 1.0;
    var effIn = Math.max(0, inputM) * langMult;
    var effOut = Math.max(0, outputM) * langMult;
    var cacheR = Math.min(1, Math.max(0, cacheRatio));
    var batchMult = (useBatch && m.batch_discount > 0) ? (1 - m.batch_discount) : 1.0;

    var uncachedCost = effIn * (1 - cacheR) * m.input_per_1m * batchMult;
    var cachedCost = effIn * cacheR * m.cached_input_per_1m * batchMult;
    var outCost = effOut * m.output_per_1m * batchMult;
    var totalUsd = uncachedCost + cachedCost + outCost;
    var noCacheUsd = (effIn * m.input_per_1m + effOut * m.output_per_1m) * batchMult;
    var totalTokensM = effIn + effOut;
    var blended = totalTokensM > 0 ? totalUsd / totalTokensM : 0;

    return {
      totalUsd: totalUsd,
      totalJpy: totalUsd * usdJpy,
      blended: blended,
      cacheSavingsUsd: Math.max(0, noCacheUsd - totalUsd),
      effIn: effIn,
      effOut: effOut,
      tokensPer1kUsdM: blended > 0 ? 1000 / blended : 0
    };
  }

  function renderBarSvg(items, accentHex) {
    var maxVal = 0.0001;
    for (var i = 0; i < items.length; i += 1) {
      if (items[i].value > maxVal) maxVal = items[i].value;
    }
    var rowH = 34;
    var padTop = 8;
    var h = padTop + items.length * rowH + 8;
    var labelW = 158;
    var barMaxW = 240;
    var svgW = 490;
    var lines = ['<svg viewBox="0 0 ' + svgW + ' ' + h + '" role="img" aria-label="Monthly USD API cost comparison chart">'];
    for (var j = 0; j < items.length; j += 1) {
      var item = items[j];
      var y = padTop + j * rowH;
      var bw = Math.max(4, Math.round((item.value / maxVal) * barMaxW));
      var fill = item.highlight ? accentHex : '#7b8794';
      var safeLabel = String(item.label).replace(/&/g, '&amp;').replace(/</g, '&lt;');
      lines.push('<text x="0" y="' + (y + 18) + '" font-size="12" fill="#13161a" font-weight="' + (item.highlight ? '700' : '500') + '">' + safeLabel + '</text>');
      lines.push('<rect x="' + labelW + '" y="' + (y + 6) + '" width="' + bw + '" height="16" rx="3" fill="' + fill + '"></rect>');
      lines.push('<text x="' + (labelW + bw + 8) + '" y="' + (y + 18) + '" font-size="12" fill="#13161a" font-family="ui-monospace, monospace">' + fmtUsd(item.value) + '</text>');
    }
    lines.push('</svg>');
    return lines.join('');
  }

  function initPairWidget(root, cfg) {
    var mA = Object.assign({}, cfg.model_a);
    var mB = Object.assign({}, cfg.model_b);

    var elIn = root.querySelector('[data-field="input_m"]');
    var elOut = root.querySelector('[data-field="output_m"]');
    var elCache = root.querySelector('[data-field="cache_pct"]');
    var elBatch = root.querySelector('[data-field="use_batch"]');
    var elJp = root.querySelector('[data-field="is_japanese"]');
    var elFx = root.querySelector('[data-field="usd_jpy"]');
    var elAIn = root.querySelector('[data-field="a_in"]');
    var elAOut = root.querySelector('[data-field="a_out"]');
    var elBIn = root.querySelector('[data-field="b_in"]');
    var elBOut = root.querySelector('[data-field="b_out"]');

    var outA = root.querySelector('[data-out="cost_a"]');
    var outAJpy = root.querySelector('[data-out="cost_a_jpy"]');
    var outB = root.querySelector('[data-out="cost_b"]');
    var outBJpy = root.querySelector('[data-out="cost_b_jpy"]');
    var outDiff = root.querySelector('[data-out="savings"]');
    var outDiffSub = root.querySelector('[data-out="savings_sub"]');
    var outAnnual = root.querySelector('[data-out="annual_savings"]');
    var outChart = root.querySelector('[data-out="chart"]');
    var lblIn = root.querySelector('[data-lbl="input_m"]');
    var lblOut = root.querySelector('[data-lbl="output_m"]');
    var lblCache = root.querySelector('[data-lbl="cache_pct"]');

    function update() {
      var inM = parseFloat(elIn.value) || 0;
      var outM = parseFloat(elOut.value) || 0;
      var cachePct = parseFloat(elCache.value) || 0;
      var useBatch = Boolean(elBatch.checked);
      var isJp = Boolean(elJp.checked);
      var fx = Math.max(1, parseFloat(elFx.value) || 150);

      var curA = Object.assign({}, mA, {
        input_per_1m: Math.max(0, parseFloat(elAIn.value) || 0),
        output_per_1m: Math.max(0, parseFloat(elAOut.value) || 0)
      });
      var curB = Object.assign({}, mB, {
        input_per_1m: Math.max(0, parseFloat(elBIn.value) || 0),
        output_per_1m: Math.max(0, parseFloat(elBOut.value) || 0)
      });
      // Scale cached rate proportionally if user edits input rate
      if (mA.input_per_1m > 0) curA.cached_input_per_1m = curA.input_per_1m * (mA.cached_input_per_1m / mA.input_per_1m);
      if (mB.input_per_1m > 0) curB.cached_input_per_1m = curB.input_per_1m * (mB.cached_input_per_1m / mB.input_per_1m);

      lblIn.textContent = inM.toFixed(1) + 'M';
      lblOut.textContent = outM.toFixed(1) + 'M';
      lblCache.textContent = Math.round(cachePct) + '%';

      var rA = calcCost(curA, inM, outM, cachePct / 100, useBatch, isJp, fx);
      var rB = calcCost(curB, inM, outM, cachePct / 100, useBatch, isJp, fx);

      outA.textContent = fmtUsd(rA.totalUsd);
      outAJpy.textContent = fmtJpy(rA.totalJpy) + ' / mo (' + fmtUsd(rA.blended) + '/1M)';
      outB.textContent = fmtUsd(rB.totalUsd);
      outBJpy.textContent = fmtJpy(rB.totalJpy) + ' / mo (' + fmtUsd(rB.blended) + '/1M)';

      var diff = Math.abs(rA.totalUsd - rB.totalUsd);
      var hi = Math.max(rA.totalUsd, rB.totalUsd);
      var pct = hi > 0 ? (diff / hi) * 100 : 0;
      if (diff < 1e-6) {
        outDiff.textContent = '$0.00 (Tie)';
        outDiffSub.textContent = 'Identical total spend at these settings';
      } else if (rA.totalUsd < rB.totalUsd) {
        outDiff.textContent = fmtUsd(diff) + ' (-' + pct.toFixed(1) + '%)';
        outDiffSub.textContent = mA.name + ' is cheaper';
      } else {
        outDiff.textContent = fmtUsd(diff) + ' (-' + pct.toFixed(1) + '%)';
        outDiffSub.textContent = mB.name + ' is cheaper';
      }
      outAnnual.textContent = fmtUsd(diff * 12) + ' / yr';

      outChart.innerHTML = renderBarSvg([
        { label: mA.name, value: rA.totalUsd, highlight: rA.totalUsd <= rB.totalUsd },
        { label: mB.name, value: rB.totalUsd, highlight: rB.totalUsd < rA.totalUsd }
      ], '#0f5c4d');
    }

    root.addEventListener('input', update);
    root.addEventListener('change', update);
    var resetBtn = root.querySelector('[data-action="reset"]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        elIn.value = cfg.defaults.input_m;
        elOut.value = cfg.defaults.output_m;
        elCache.value = cfg.defaults.cache_pct;
        elBatch.checked = Boolean(cfg.defaults.use_batch);
        elJp.checked = Boolean(cfg.defaults.is_japanese);
        elFx.value = cfg.defaults.usd_jpy;
        elAIn.value = mA.input_per_1m;
        elAOut.value = mA.output_per_1m;
        elBIn.value = mB.input_per_1m;
        elBOut.value = mB.output_per_1m;
        update();
      });
    }
    update();
  }

  function initWorkloadWidget(root, cfg) {
    var models = cfg.models || [];
    var elIn = root.querySelector('[data-field="input_m"]');
    var elOut = root.querySelector('[data-field="output_m"]');
    var elCache = root.querySelector('[data-field="cache_pct"]');
    var elBatch = root.querySelector('[data-field="use_batch"]');
    var elJp = root.querySelector('[data-field="is_japanese"]');
    var elFx = root.querySelector('[data-field="usd_jpy"]');
    var elFast = root.querySelector('[data-field="fast_model"]');
    var elFrontier = root.querySelector('[data-field="frontier_model"]');

    var lblIn = root.querySelector('[data-lbl="input_m"]');
    var lblOut = root.querySelector('[data-lbl="output_m"]');
    var lblCache = root.querySelector('[data-lbl="cache_pct"]');

    var outCheapest = root.querySelector('[data-out="cheapest"]');
    var outCheapestSub = root.querySelector('[data-out="cheapest_sub"]');
    var outFlagship = root.querySelector('[data-out="flagship"]');
    var outFlagshipSub = root.querySelector('[data-out="flagship_sub"]');
    var outRouted = root.querySelector('[data-out="routed_80_20"]');
    var outRoutedSub = root.querySelector('[data-out="routed_sub"]');
    var outChart = root.querySelector('[data-out="chart"]');

    function findModel(id) {
      for (var i = 0; i < models.length; i += 1) {
        if (models[i].id === id) return models[i];
      }
      return models[0];
    }

    function update() {
      var inM = parseFloat(elIn.value) || 0;
      var outM = parseFloat(elOut.value) || 0;
      var cachePct = parseFloat(elCache.value) || 0;
      var useBatch = Boolean(elBatch.checked);
      var isJp = Boolean(elJp.checked);
      var fx = Math.max(1, parseFloat(elFx.value) || 150);

      lblIn.textContent = inM.toFixed(1) + 'M';
      lblOut.textContent = outM.toFixed(1) + 'M';
      lblCache.textContent = Math.round(cachePct) + '%';

      var scored = models.map(function (m) {
        return { model: m, res: calcCost(m, inM, outM, cachePct / 100, useBatch, isJp, fx) };
      });
      scored.sort(function (a, b) { return a.res.totalUsd - b.res.totalUsd; });

      var best = scored[0];
      var fastM = findModel(elFast ? elFast.value : 'gemini-2-5-flash');
      var frontM = findModel(elFrontier ? elFrontier.value : 'claude-sonnet-4');
      var rFast = calcCost(fastM, inM, outM, cachePct / 100, useBatch, isJp, fx);
      var rFront = calcCost(frontM, inM, outM, cachePct / 100, useBatch, isJp, fx);
      var routedUsd = rFast.totalUsd * 0.8 + rFront.totalUsd * 0.2;
      var routedSavePct = rFront.totalUsd > 0 ? ((rFront.totalUsd - routedUsd) / rFront.totalUsd) * 100 : 0;

      outCheapest.textContent = fmtUsd(best.res.totalUsd);
      outCheapestSub.textContent = best.model.name + ' (' + fmtJpy(best.res.totalJpy) + ')';
      outFlagship.textContent = fmtUsd(rFront.totalUsd);
      outFlagshipSub.textContent = frontM.name + ' (' + fmtJpy(rFront.totalJpy) + ')';
      outRouted.textContent = fmtUsd(routedUsd);
      outRoutedSub.textContent = '80% ' + fastM.name + ' / 20% ' + frontM.name + ' (-' + routedSavePct.toFixed(1) + '%)';

      var topItems = scored.slice(0, 6).map(function (s, idx) {
        return { label: s.model.name, value: s.res.totalUsd, highlight: idx === 0 };
      });
      outChart.innerHTML = renderBarSvg(topItems, '#0f5c4d');
    }

    root.addEventListener('input', update);
    root.addEventListener('change', update);
    var resetBtn = root.querySelector('[data-action="reset"]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        elIn.value = cfg.defaults.input_m;
        elOut.value = cfg.defaults.output_m;
        elCache.value = cfg.defaults.cache_pct;
        elBatch.checked = Boolean(cfg.defaults.use_batch);
        elJp.checked = Boolean(cfg.defaults.is_japanese);
        elFx.value = cfg.defaults.usd_jpy;
        update();
      });
    }
    update();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var nodes = document.querySelectorAll('[data-llm-widget]');
    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      var script = node.querySelector('script[type="application/json"]');
      if (!script) continue;
      try {
        var cfg = JSON.parse(script.textContent);
        if (cfg.mode === 'pair') initPairWidget(node, cfg);
        else initWorkloadWidget(node, cfg);
      } catch (e) {
        // Ignore malformed inline config gracefully
      }
    }
  });
})();
