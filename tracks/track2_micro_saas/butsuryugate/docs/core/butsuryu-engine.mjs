/**
 * BUTSURYUGATE（物流門）Core Engine
 * 改正物資流通効率化法（特定荷主 年間9万トン CLO選任・中長期計画 / 荷待ち＋荷役2時間以内目標）・
 * トラック運送事業法（書面交付 / 標準的運賃・燃料サーチャージ / 実運送体制管理簿 <=2次請け）・
 * 厚労省 自動車運転者の改善基準告示2024（月拘束310h上限 / 1日休息9h下限・11h努力）
 * ブラウザローカル監査エンジン（外部通信ゼロ）
 */

const PILLARS = [
  {
    id: 'written_freight_13_items',
    title: 'トラック運送契約・配送指示書の事前書面交付（附帯業務・運賃明記）',
    criterion: '貨物自動車運送事業法第12条（書面交付義務）',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:書面交付|運送契約書|配送指示書|附帯業務|業務内容明記|契約書交付)/i,
    antiPattern: /(?:口頭配車|書面交付省略|事前書面なし)/i,
    detail: '配車・積込開始前に配送条件・運賃・附帯作業を明記した書面（または承諾済み電磁的記録）を交付する規定が不足しています。',
    remediation: '配車確定前に運送条件・運賃計算方法・附帯作業有無を含む配送指示書・契約書を書面交付してください。',
  },
  {
    id: 'standard_fare_fuel_surcharge',
    title: '国交省『標準的運賃』準拠・燃料サーチャージ／高速代別建て精算',
    criterion: '標準的運賃制度・価格転嫁ガイドライン',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:標準的運賃|燃料サーチャージ|運賃改定協議|高速道路利用料|実費精算|適正運賃)/i,
    antiPattern: /(?:燃料費込み固定|サーチャージ不払|運賃据置強制|一方的運賃減額)/i,
    detail: '国土交通省告示の標準的運賃水準および燃料費・高速料金の別建て収受・適時価格転嫁協議の記載が見当たりません。',
    remediation: '標準的運賃を基準とした運賃交渉および燃料価格連動サーチャージ・有料道路利用料の別途収受条項を設けてください。',
  },
  {
    id: 'wait_handling_2h_target',
    title: 'トラック予約受付・パレット化等による荷待ち＋荷役2時間以内ルール',
    criterion: '改正物資流通効率化法（荷待ち・荷役時間短縮努力／判断基準）',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:荷待ち|荷役|2時間以内|予約受付|バース予約|パレット化|待機時間削減)/i,
    antiPattern: /(?:荷待ち待機時間制限なし|手荷役強制|長距離待機許容)/i,
    detail: '1運行あたりの荷待ち＋荷役作業時間を2時間以内に抑えるためのバース予約・パレット荷役・検品簡素化措置が欠けています。',
    remediation: 'トラック予約受付システム導入やパレット化により、荷待ち・荷役時間を原則2時間以内に管理する計画を策定してください。',
  },
  {
    id: 'clo_medium_plan_shipper_duty',
    title: '特定荷主（9万t/年）物流統括管理者(CLO)選任・中長期計画＆積載率管理',
    criterion: '改正物流効率化法 特定荷主規制（2026年4月CLO義務）',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:物流統括管理者|clo|特定荷主|中長期計画|積載率|定期報告)/i,
    antiPattern: /(?:clo選任不要|特定荷主対応外|積載効率管理なし)/i,
    detail: '年間取扱貨物9万トン以上の特定荷主に義務化される物流統括管理者(CLO)の選任・中長期計画・年次定期報告体制が確認できません。',
    remediation: '取締役等の役員クラスを物流統括管理者(CLO)に選任し、積載効率向上の中長期計画と定期報告体制を整備してください。',
  },
  {
    id: 'actual_transport_ledger_tier2',
    title: '実運送体制管理簿の作成 ＆ 再委託2次請け以内への抑制（多重下請是正）',
    criterion: '改正貨物自動車運送事業法（実運送体制管理簿・健全化措置）',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:実運送体制管理簿|再委託制限|2次請け|二次請け|健全化措置|実運送事業者)/i,
    antiPattern: /(?:3次下請を許容|無制限再委託|管理簿未作成|多重下請容認)/i,
    detail: '実際に運送を担う実運送事業者名・区間を記録する「実運送体制管理簿」作成と2次下請以内への抑制ルールがありません。',
    remediation: '実運送体制管理簿を整備し、事前承諾なき再々委託（3次以上）の禁止・利用運送手数料の透明化を図ってください。',
  },
  {
    id: 'driver_binding_rest_compliance',
    title: '2024年改善基準告示（年960h・月拘束310h・休息11h努力/9h下限）準拠',
    criterion: '厚労省 自動車運転者の労働時間等の改善基準告示（2024年4月）',
    weight: 12,
    severity: 'MEDIUM',
    pattern: /(?:改善基準告示|拘束時間|休息期間|960時間|4時間30分休憩|連続運転|運行計画)/i,
    antiPattern: /(?:休息9時間未満指示|長時間拘束強制|休憩省略)/i,
    detail: 'トラック運転者の1か月拘束上限(原則284h/最大310h)、休息期間(継続11h努力・9h下限)および4時間毎30分休憩の配慮規定が不足しています。',
    remediation: '改善基準告示を超える無理な着時間指定を廃し、拘束・休息・連続運転4時間休憩を担保した運行ダイヤへ見直してください。',
  },
  {
    id: 'unpaid_wait_detention_fee',
    title: '待機時間料・積込/荷卸し等附帯作業料の有償契約（無償荷役禁止）',
    criterion: 'トラックGメン是正指導重点（無償待機・契約外荷役の禁止）',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:待機時間料|積込料|附帯作業料|別途請求|有償作業|付帯作業対価)/i,
    antiPattern: /(?:附帯作業費は運賃込み|待機料無償|タダ働き|無償荷役)/i,
    detail: '予定外待機に対する待機時間料および棚入れ・ピッキング等附帯業務の有償対価収受ルールが明記されていません。',
    remediation: '一定時間超過時の待機時間料テーブルと、運転者に行わせる付帯業務ごとの別建て対価基準を明確化してください。',
  },
  {
    id: 'retention_2yr_dispatch_records',
    title: '荷待ち待機ログ・乗務記録・点呼記録・実運送体制管理簿の保存',
    criterion: '貨物自動車運送事業輸送安全規則（乗務/点呼1〜2年＋管理簿保存）',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:乗務記録|点呼記録|保存|1年|2年|運行記録計|ログ保管)/i,
    antiPattern: /(?:待機ログ未保存|乗務記録破棄|帳簿管理なし)/i,
    detail: '運行記録計（タコグラフ）や乗務/点呼記録・待機時間実績および実運送体制管理簿の保存運用ルールが確認できません。',
    remediation: '乗務/点呼記録（1年）および荷待ち計測ログ・実運送体制管理簿の監査用保存期間を定めて管理してください。',
  },
];

export function evaluateButsuryuThresholds({
  annualCargoTons = 0,
  hasCloAppointed = false,
  contractFareJpy = 0,
  standardTariffJpy = 0,
  waitAndHandlingHours = 0,
  monthlyBindingHours = 0,
  dailyRestHours = 11,
  subcontractTier = 1,
} = {}) {
  const tons = Math.max(0, Number(annualCargoTons) || 0);
  const fare = Math.max(0, Number(contractFareJpy) || 0);
  const tariff = Math.max(0, Number(standardTariffJpy) || 0);
  const waitH = Math.max(0, Number(waitAndHandlingHours) || 0);
  const bindingH = Math.max(0, Number(monthlyBindingHours) || 0);
  const restH = Math.max(0, Number(dailyRestHours) || 0);
  const tier = Math.max(1, Math.trunc(Number(subcontractTier) || 1));

  const specificShipperRequired = tons >= 90000;
  const cloMissingViolation = Boolean(specificShipperRequired && !hasCloAppointed);
  const belowStandardTariff = Boolean(tariff > 0 && fare < tariff * 0.9);
  const excessiveWaitHandling = waitH > 2;
  const driverRestOrBindingBreach = Boolean(bindingH > 310 || (restH > 0 && restH < 9));
  const deepSubcontractRisk = tier > 2;

  return {
    annualCargoTons: tons,
    specificShipperThresholdTons: 90000,
    specificShipperRequired,
    hasCloAppointed: Boolean(hasCloAppointed),
    cloMissingViolation,
    contractFareJpy: fare,
    standardTariffJpy: tariff,
    belowStandardTariff,
    waitAndHandlingHours: waitH,
    excessiveWaitHandling,
    monthlyBindingHours: bindingH,
    dailyRestHours: restH,
    driverRestOrBindingBreach,
    subcontractTier: tier,
    deepSubcontractRisk,
  };
}

export function auditButsuryuContract(contractText = '', options = {}) {
  const normalized = String(contractText || '').replace(/\u3000/g, ' ').trim();
  const thresholds = evaluateButsuryuThresholds(options);

  const findings = [];
  const passedPillars = [];
  let rawScore = 0;

  for (const pillar of PILLARS) {
    const matched = pillar.pattern.test(normalized);
    const negated = pillar.antiPattern.test(normalized);
    if (matched && !negated) {
      rawScore += pillar.weight;
      passedPillars.push({
        id: pillar.id,
        title: pillar.title,
        criterion: pillar.criterion,
        weight: pillar.weight,
      });
    } else {
      findings.push({
        id: pillar.id,
        title: pillar.title,
        criterion: pillar.criterion,
        severity: pillar.severity,
        detail: negated ? `NG商慣行パターン検出（${pillar.detail}）` : pillar.detail,
        remediation: pillar.remediation,
      });
    }
  }

  let penalty = 0;
  if (thresholds.cloMissingViolation) {
    penalty += 20;
    findings.push({
      id: 'clo_missing',
      title: '特定荷主（年間取扱9万トン以上）到達にもかかわらず物流統括管理者(CLO)未選任',
      criterion: `改正物流効率化法（取扱貨物量 ${thresholds.annualCargoTons.toLocaleString('en-US')} t >= 90,000 t）`,
      severity: 'HIGH',
      detail: '特定荷主指定基準（9万トン/年）に達していますが、物流統括管理者(CLO)の選任が未確認です。',
      remediation: '役員クラスのCLO選任と中長期計画・年次定期報告の体制を整備してください。',
    });
  }
  if (thresholds.belowStandardTariff) {
    penalty += 20;
    findings.push({
      id: 'tariff_undercut',
      title: '契約運賃が国交省『標準的運賃』目安の90%未満（不当に低い運賃水準）',
      criterion: `運賃比較（契約 ${thresholds.contractFareJpy.toLocaleString('en-US')}円 vs 標準的運賃 ${thresholds.standardTariffJpy.toLocaleString('en-US')}円）`,
      severity: 'HIGH',
      detail: '標準的運賃を大きく下回る契約運賃となっており、トラックGメンによる働きかけ・要請・社名公表リスクがあります。',
      remediation: '標準的運賃＋燃料サーチャージ＋附帯作業料を基準とした運賃再交渉を行ってください。',
    });
  }
  if (thresholds.excessiveWaitHandling) {
    penalty += 15;
    findings.push({
      id: 'wait_over_2h',
      title: '1運行あたりの荷待ち＋荷役時間が法定目標（2時間以内）を超過',
      criterion: `荷待ち・荷役合計 ${thresholds.waitAndHandlingHours} 時間 > 2.0 時間`,
      severity: 'HIGH',
      detail: 'トラックの荷待ち時間と荷役時間の合計が2時間を超えており、是正勧告および改善計画提出リスクがあります。',
      remediation: '予約バース運用・パレット化・事前出荷通知により2時間以内へ短縮し待機時間料を精算してください。',
    });
  }
  if (thresholds.driverRestOrBindingBreach) {
    penalty += 15;
    findings.push({
      id: 'driver_rest_breach',
      title: '2024年改善基準告示（月拘束310h上限 / 1日休息9h下限）違反',
      criterion: `月拘束 ${thresholds.monthlyBindingHours}h / 休息 ${thresholds.dailyRestHours}h`,
      severity: 'HIGH',
      detail: '運転者の月間拘束時間310h超過または継続休息9時間未満となっており、労基署・国交省監査で違法と指摘されます。',
      remediation: '中継輸送・リードタイム延長・発着時間帯見直しにより拘束上限と休息期間を確保してください。',
    });
  }
  if (thresholds.deepSubcontractRisk) {
    penalty += 10;
    findings.push({
      id: 'deep_tier_subcontract',
      title: '再委託次数が2次請けを超過（多重下請構造）',
      criterion: `実運送階層 Tier ${thresholds.subcontractTier} > Tier 2`,
      severity: 'MEDIUM',
      detail: '多重下請構造（3次請け以降）は実運送事業者への運賃目減りと実運送体制管理簿の不備を招きます。',
      remediation: '利用運送階層を原則2次請け以内に抑制し、全階層の運送事業者名と区間を管理簿へ記載してください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore - penalty));
  let readinessLabel = 'トラックGメン勧告・CLO/基準超過リスクあり';
  let status = 'fail';
  if (score >= 88 && findings.every((f) => f.severity !== 'HIGH')) {
    readinessLabel = '改正物流効率化法・トラック2024年基準 適合';
    status = 'pass';
  } else if (score >= 65) {
    readinessLabel = '一部補完推奨（運賃・待機時間条項見直し）';
    status = 'warn';
  }

  return {
    score,
    status,
    readinessLabel,
    thresholds,
    passedPillars,
    findings,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
  };
}

export function generateButsuryuComplianceMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const lane = String(meta.routeLane || '対象輸送ルート（未設定）').trim() || '対象輸送ルート（未設定）';
  const today = new Date().toISOString().slice(0, 10);
  const t = auditResult.thresholds;

  const lines = [
    '# 改正物流効率化法・トラックGメン・改善基準告示2024 監査証明書',
    '',
    `- **作成日**: ${today}`,
    `- **荷主 / 元請事業者名**: ${org}`,
    `- **対象輸送ルート / 拠点**: ${lane}`,
    `- **法令適合スコア**: **${auditResult.readinessLabel}**（\`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    '',
    '## 1. 定量閾値判定（特定荷主CLO・標準的運賃・荷待ち2h・運転者休息）',
    '',
    `- **特定荷主判定（9万t/年）**: \`${t.annualCargoTons.toLocaleString('en-US')} t/年\` / CLO選任: \`${t.hasCloAppointed ? '選任済み' : '未選任'}\` -> \`${t.cloMissingViolation ? '要選任違反リスク' : '問題なし'}\``,
    `- **運賃適正比較**: 契約運賃 \`${t.contractFareJpy.toLocaleString('en-US')} JPY\` vs 標準的運賃 \`${t.standardTariffJpy.toLocaleString('en-US')} JPY\` -> \`${t.belowStandardTariff ? '90%未満ダンピング警告' : '適正範囲'}\``,
    `- **荷待ち＋荷役時間（目標 2.0h以内）**: \`${t.waitAndHandlingHours} 時間\` -> \`${t.excessiveWaitHandling ? '2時間超過 (要改善)' : '基準内'}\``,
    `- **2024年運転者基準（月拘束<=310h / 休息>=9h）**: 拘束 \`${t.monthlyBindingHours}h\` / 休息 \`${t.dailyRestHours}h\` -> \`${t.driverRestOrBindingBreach ? '基準超過 (NG)' : '適合'}\``,
    `- **実運送体制管理簿（下請階層）**: \`Tier ${t.subcontractTier}\` -> \`${t.deepSubcontractRisk ? '2次請け超過注意' : '2次請け以内'}\``,
    '',
    '## 2. 改正物流法 8大チェック項目の適合・是正状況',
    '',
    '| 法的チェック項目 | 判定 | 根拠 / 是正事項 |',
    '|---|---|---|',
  ];

  for (const p of auditResult.passedPillars) {
    lines.push(`| ${p.title} | 充足 | ${p.criterion} |`);
  }
  for (const f of auditResult.findings) {
    lines.push(`| ${f.title} | 要是正 (${f.severity}) | ${f.detail} ／ 是正案: ${f.remediation} |`);
  }

  lines.push(
    '',
    '---',
    '*本証明書は BUTSURYUGATE（物流門）により運賃明細・取扱重量・待機ログ・乗務記録を社外サーバーへ一切送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
