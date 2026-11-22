/**
 * Interactive Client-Side 2026-2027 Japan Tax, Furusato & Incorporation Calculator
 * 1:1 parity with Python calculator_engines.py and TEDORIGATE statutory formulas.
 */
(function () {
  'use strict';

  var INCOME_BRACKETS = [
    [1949000, 0.05, 0],
    [3299000, 0.10, 97500],
    [6949000, 0.20, 427500],
    [8999000, 0.23, 636000],
    [17999000, 0.33, 1536000],
    [39999000, 0.40, 2796000],
    [Infinity, 0.45, 4796000]
  ];

  var BLUE_MAP = { blue65: 650000, blue55: 550000, blue10: 100000, white: 0 };

  function fmtYen(v) {
    return '¥' + Math.round(v).toLocaleString('ja-JP');
  }

  function fmtMan(v) {
    return (v / 10000).toFixed(1) + '万円';
  }

  function calcBasic(inc) {
    var x = Math.max(0, Math.floor(inc));
    if (x <= 24000000) return { inc: 480000, res: 430000 };
    if (x <= 24500000) return { inc: 320000, res: 290000 };
    if (x <= 25000000) return { inc: 160000, res: 150000 };
    return { inc: 0, res: 0 };
  }

  function calcIncomeTax(raw) {
    var taxable = Math.floor(Math.max(0, raw) / 1000) * 1000;
    if (taxable <= 0) return { taxable: 0, rate: 0.05, total: 0 };
    var br = INCOME_BRACKETS[INCOME_BRACKETS.length - 1];
    for (var i = 0; i < INCOME_BRACKETS.length; i += 1) {
      if (taxable <= INCOME_BRACKETS[i][0]) {
        br = INCOME_BRACKETS[i];
        break;
      }
    }
    var base = Math.max(0, Math.floor(taxable * br[1] - br[2]));
    var recon = Math.floor(base * 0.021);
    return { taxable: taxable, rate: br[1], total: base + recon };
  }

  function calcSalaryDed(sal) {
    var s = Math.max(0, Math.floor(sal));
    if (s === 0) return 0;
    if (s <= 1625000) return Math.min(s, 550000);
    if (s <= 1800000) return Math.floor(s * 0.40 - 100000);
    if (s <= 3600000) return Math.floor(s * 0.30 + 80000);
    if (s <= 6600000) return Math.floor(s * 0.20 + 440000);
    if (s <= 8500000) return Math.floor(s * 0.10 + 1100000);
    return 1950000;
  }

  function calcNhi(bizIncome, age40) {
    var base = Math.max(0, Math.floor(bizIncome) - 430000);
    var med = Math.min(660000, Math.floor(base * 0.0771 + 49100));
    var sup = Math.min(260000, Math.floor(base * 0.0269 + 16500));
    var kai = age40 ? Math.min(170000, Math.floor(base * 0.0225 + 16500)) : 0;
    return med + sup + kai;
  }

  function calcFurusato(resLevy, rate, taxable) {
    if (resLevy <= 0 || taxable <= 0) return { theoretical: 0, safe: 0, warn: false };
    var denom = 0.90 - rate * 1.021;
    var theo = Math.floor((resLevy * 0.20) / denom) + 2000;
    var after = calcIncomeTax(Math.max(0, taxable - (theo - 2000)));
    var warn = after.rate < rate;
    var base = theo;
    if (warn) {
      base = Math.floor((resLevy * 0.20) / (0.90 - after.rate * 1.021)) + 2000;
    }
    var safe = Math.max(0, Math.floor((base * 0.95) / 1000) * 1000);
    return { theoretical: theo, safe: safe, warn: warn };
  }

  function simSole(p) {
    var rawProfit = Math.max(0, p.sales - p.expenses);
    var blueDed = Math.min(rawProfit, BLUE_MAP[p.blue] || 0);
    var bizIncome = Math.max(0, rawProfit - blueDed);
    var nhi = calcNhi(bizIncome, p.age40);
    var pension = 203760;
    var shaho = nhi + pension;
    var bizTax = p.bizTax ? Math.floor(Math.max(0, rawProfit - 2900000) * 0.05) : 0;
    var basic = calcBasic(bizIncome);
    var common = shaho + p.mutualAid + p.ideco;
    var incTax = calcIncomeTax(bizIncome - (common + basic.inc));
    var resTaxable = Math.floor(Math.max(0, bizIncome - (common + basic.res)) / 1000) * 1000;
    var resLevy = Math.floor(resTaxable * 0.10);
    var resPerCap = (resTaxable > 0 || bizIncome > 450000) ? 5000 : 0;
    var resTotal = resLevy + resPerCap;
    var furusato = calcFurusato(resLevy, incTax.rate, incTax.taxable);
    var totalTax = incTax.total + resTotal + bizTax;
    var totalBurden = totalTax + shaho;
    return {
      rawProfit: rawProfit,
      bizIncome: bizIncome,
      incTax: incTax,
      resTotal: resTotal,
      bizTax: bizTax,
      nhi: nhi,
      shaho: shaho,
      furusato: furusato,
      totalTax: totalTax,
      totalBurden: totalBurden,
      netWealth: rawProfit - totalBurden
    };
  }

  function calcCorpShaho(sal, age40) {
    if (sal <= 0) {
      var emp = calcNhi(0, age40) + 203760;
      return { emp: emp, comp: 0, total: emp };
    }
    var koseiBase = Math.min(Math.max(sal, 1056000), 7800000);
    var kenpoBase = Math.min(Math.max(sal, 696000), 16680000);
    var koseiH = Math.floor(koseiBase * 0.0915);
    var kenpoH = Math.floor(kenpoBase * 0.04955);
    var kaigoH = age40 ? Math.floor(kenpoBase * 0.00795) : 0;
    var child = Math.floor(koseiBase * 0.0036);
    var emp = koseiH + kenpoH + kaigoH;
    var comp = emp + child;
    return { emp: emp, comp: comp, total: emp + comp };
  }

  function simCorpAt(p, sal) {
    var rawProfit = Math.max(0, p.sales - p.expenses);
    var acct = p.acctCost;
    var shaho = calcCorpShaho(sal, p.age40);
    var empInc = Math.max(0, sal - calcSalaryDed(sal));
    var basic = calcBasic(empInc);
    var corpIdeco = Math.min(p.ideco, 276000);
    var common = shaho.emp + p.mutualAid + corpIdeco;
    var pInc = calcIncomeTax(empInc - (common + basic.inc));
    var pResTaxable = Math.floor(Math.max(0, empInc - (common + basic.res)) / 1000) * 1000;
    var pResLevy = Math.floor(pResTaxable * 0.10);
    var pResCap = (pResTaxable > 0 || empInc > 450000) ? 5000 : 0;
    var pRes = pResLevy + pResCap;
    var pNet = sal - shaho.emp - pInc.total - pRes;
    var preTax = rawProfit - acct - sal - shaho.comp;
    var corpTax = preTax > 0
      ? Math.floor(Math.min(preTax, 8000000) * 0.23 + Math.max(0, preTax - 8000000) * 0.3358)
      : 0;
    var retained = preTax - corpTax - 70000;
    return {
      sal: sal,
      preTax: preTax,
      combinedNet: pNet + retained,
      pNet: pNet,
      retained: retained,
      totalBurden: rawProfit - (pNet + retained)
    };
  }

  function simCorpOptimal(p) {
    var rawProfit = Math.max(0, p.sales - p.expenses);
    var budget = Math.max(0, rawProfit - p.acctCost);
    var maxF = Math.floor(budget / 1.14);
    var best = simCorpAt(p, 0);
    for (var s = 0; s <= maxF; s += 120000) {
      var r = simCorpAt(p, s);
      if (r.preTax < 0) continue;
      if (r.combinedNet > best.combinedNet) best = r;
    }
    return best;
  }

  function renderCompareSvg(soleNet, corpNet, soleBurden, corpBurden) {
    var maxV = Math.max(soleNet, corpNet, soleBurden, corpBurden, 100000);
    var items = [
      { label: '個人事業主 手取り純資産', val: Math.max(0, soleNet), color: '#1b3b6f' },
      { label: '法人成り 合計純資産', val: Math.max(0, corpNet), color: '#0f5c4d' },
      { label: '個人 税・国保・年金負担', val: Math.max(0, soleBurden), color: '#b45309' },
      { label: '法人 税・社保・維持費', val: Math.max(0, corpBurden), color: '#7b8794' }
    ];
    var lines = ['<svg viewBox="0 0 490 148" role="img" aria-label="個人事業主と法人成りの手取り・総負担比較グラフ">'];
    for (var i = 0; i < items.length; i += 1) {
      var y = 10 + i * 34;
      var w = Math.max(4, Math.round((items[i].val / maxV) * 215));
      lines.push('<text x="0" y="' + (y + 18) + '" font-size="11.5" fill="#13161a">' + items[i].label + '</text>');
      lines.push('<rect x="172" y="' + (y + 6) + '" width="' + w + '" height="16" rx="3" fill="' + items[i].color + '"></rect>');
      lines.push('<text x="' + (172 + w + 7) + '" y="' + (y + 18) + '" font-size="11.5" fill="#13161a" font-family="ui-monospace, monospace">' + fmtMan(items[i].val) + '</text>');
    }
    lines.push('</svg>');
    return lines.join('');
  }

  function initWidget(root, cfg) {
    var elSales = root.querySelector('[data-field="sales_man"]');
    var elExp = root.querySelector('[data-field="expenses_man"]');
    var elBlue = root.querySelector('[data-field="blue"]');
    var elMutual = root.querySelector('[data-field="mutual_man"]');
    var elIdeco = root.querySelector('[data-field="ideco_man"]');
    var elAge = root.querySelector('[data-field="age40"]');
    var elAcct = root.querySelector('[data-field="acct_man"]');

    var lblSales = root.querySelector('[data-lbl="sales_man"]');
    var lblExp = root.querySelector('[data-lbl="expenses_man"]');
    var lblMutual = root.querySelector('[data-lbl="mutual_man"]');

    var outNet = root.querySelector('[data-out="sole_net"]');
    var outNetSub = root.querySelector('[data-out="sole_net_sub"]');
    var outTax = root.querySelector('[data-out="sole_burden"]');
    var outTaxSub = root.querySelector('[data-out="sole_burden_sub"]');
    var outFuru = root.querySelector('[data-out="furusato_safe"]');
    var outFuruSub = root.querySelector('[data-out="furusato_sub"]');
    var outCorp = root.querySelector('[data-out="corp_adv"]');
    var outCorpSub = root.querySelector('[data-out="corp_adv_sub"]');
    var outChart = root.querySelector('[data-out="chart"]');

    function update() {
      var salesMan = parseFloat(elSales.value) || 0;
      var expMan = parseFloat(elExp.value) || 0;
      var mutualMan = parseFloat(elMutual.value) || 0;
      var idecoMan = elIdeco ? (parseFloat(elIdeco.value) || 0) : 24;
      var acctMan = elAcct ? (parseFloat(elAcct.value) || 24) : 24;

      if (lblSales) lblSales.textContent = salesMan.toLocaleString('ja-JP') + '万円';
      if (lblExp) lblExp.textContent = expMan.toLocaleString('ja-JP') + '万円';
      if (lblMutual) lblMutual.textContent = mutualMan.toLocaleString('ja-JP') + '万円';

      var params = {
        sales: Math.round(salesMan * 10000),
        expenses: Math.round(expMan * 10000),
        blue: elBlue ? elBlue.value : 'blue65',
        mutualAid: Math.min(840000, Math.round(mutualMan * 10000)),
        ideco: Math.min(816000, Math.round(idecoMan * 10000)),
        age40: Boolean(elAge && elAge.checked),
        bizTax: true,
        acctCost: Math.round(acctMan * 10000)
      };

      var sole = simSole(params);
      var corp = simCorpOptimal(params);
      var adv = corp.combinedNet - sole.netWealth;

      outNet.textContent = fmtYen(sole.netWealth);
      var ratePct = sole.rawProfit > 0 ? ((sole.totalBurden / sole.rawProfit) * 100).toFixed(1) : '0.0';
      outNetSub.textContent = '利益 ' + fmtMan(sole.rawProfit) + ' / 実効負担率 ' + ratePct + '%';

      outTax.textContent = fmtYen(sole.totalBurden);
      outTaxSub.textContent = '所得税 ' + fmtMan(sole.incTax.total) + ' + 住民税 ' + fmtMan(sole.resTotal) + ' + 国保年金 ' + fmtMan(sole.shaho);

      outFuru.textContent = fmtYen(sole.furusato.safe);
      outFuruSub.textContent = '理論上限 ' + fmtYen(sole.furusato.theoretical) + (sole.furusato.warn ? '（税率境界注意）' : '（95%安全目安）');

      outCorp.textContent = (adv >= 0 ? '+' : '') + fmtYen(adv);
      outCorpSub.textContent = (adv >= 0 ? '法人成り有利' : '個人継続有利') + '（最適役員報酬 年' + fmtMan(corp.sal) + '）';

      if (outChart) {
        outChart.innerHTML = renderCompareSvg(sole.netWealth, corp.combinedNet, sole.totalBurden, corp.totalBurden);
      }
    }

    root.addEventListener('input', update);
    root.addEventListener('change', update);
    var resetBtn = root.querySelector('[data-action="reset"]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        elSales.value = cfg.sales_man;
        elExp.value = cfg.expenses_man;
        if (elBlue) elBlue.value = cfg.blue;
        elMutual.value = cfg.mutual_man;
        if (elIdeco) elIdeco.value = cfg.ideco_man;
        if (elAge) elAge.checked = false;
        if (elAcct) elAcct.value = cfg.acct_man;
        update();
      });
    }
    update();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var nodes = document.querySelectorAll('[data-jptax-widget]');
    for (var i = 0; i < nodes.length; i += 1) {
      var script = nodes[i].querySelector('script[type="application/json"]');
      if (!script) continue;
      try {
        initWidget(nodes[i], JSON.parse(script.textContent));
      } catch (e) {
        // Graceful fallback
      }
    }
  });
})();
