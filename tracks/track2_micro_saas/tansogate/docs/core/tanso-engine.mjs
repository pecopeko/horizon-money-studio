/**
 * TANSOGATE（炭素門）Core Engine
 * SSBJサステナビリティ開示基準（S1/S2）・温対法SHK制度（特定排出者 3,000 t-CO2/年）・
 * Scope 1/2 Dual Reporting（ロケーション基準 vs マーケット基準 - 非化石証書）・Scope 3・
 * J-クレジット・環境表示ガイドライン（グリーンウォッシュ防止）ローカル監査エンジン（外部通信ゼロ）
 */

const PILLARS = [
  {
    id: 'ssbj_s1_s2_governance',
    title: 'SSBJ基準 S1/S2（ガバナンス・気候関連リスク戦略・移行計画）',
    criterion: 'SSBJサステナビリティ開示基準 S1 / S2（TCFD・ISSB整合）',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:ssbj|s1|s2|tcfd|ガバナンス|気候関連リスク|移行計画|取締役会監督)/i,
    antiPattern: /(?:ssbj未対応|気候リスク開示不要|ガバナンス監督なし)/i,
    detail: 'SSBJ S1/S2に沿ったガバナンス体制（取締役会監督・経営責任）、気候関連リスク/機会および移行計画・シナリオ分析の記載が不足しています。',
    remediation: '取締役会での気候課題監督体制、1.5℃/2℃移行リスク評価、および削減目標・移行計画を明確化してください。',
  },
  {
    id: 'scope1_2_dual_method',
    title: 'Scope 1直接排出 ＆ Scope 2 デュアルレポーティング（ロケーション基準＋マーケット基準）',
    criterion: 'GHGプロトコル Scope 2 ガイダンス / 温対法基礎・調整後排出係数',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:scope\s*1|scope\s*2|ロケーション基準|マーケット基準|基礎排出係数|調整後排出係数|電力排出係数)/i,
    antiPattern: /(?:マーケット基準のみ|scope\s*2算定省略|排出係数未設定)/i,
    detail: '電力由来Scope 2について、ロケーション基準（全国/電力系統平均係数）とマーケット基準（調整後係数・非化石証書反映）の併記体制が欠けています。',
    remediation: 'Scope 1の燃料燃焼算定に加え、Scope 2は必ずロケーション基準とマーケット基準の両方を並列開示してください。',
  },
  {
    id: 'scope3_value_chain',
    title: 'Scope 3 バリューチェーン排出算定（カテゴリ1等重要カテゴリ網羅）',
    criterion: 'SSBJ S2 バリューチェーン Scope 3 開示要件',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:scope\s*3|バリューチェーン|カテゴリ\s*1|サプライチェーン排出|産業連関|idea)/i,
    antiPattern: /(?:scope\s*3算定対象外|scope\s*3除外|バリューチェーン未算定)/i,
    detail: '調達製品・輸送等（Scope 3 カテゴリ1〜15）の算定バウンダリおよび金額法/物量法（IDEA等の排出原単位データベース）の設計が見当たりません。',
    remediation: '重要なScope 3カテゴリ（特に購入した製品・サービス カテゴリ1等）の算定対象・排出原単位ソースを規程化してください。',
  },
  {
    id: 'shk_3000t_eegs',
    title: '温対法（SHK制度）3,000 t-CO2/年 特定排出者判定 ＆ EEGS定期報告',
    criterion: '地球温暖化対策の推進に関する法律（温対法・省エネ法EEGS報告）',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:温対法|shk|3,?000\s*t|特定排出者|eegs|省エネ法|定期報告書)/i,
    antiPattern: /(?:温対法届出省略|shk報告不要|特定排出者確認なし)/i,
    detail: 'エネルギー起源CO2等が年間3,000t-CO2以上となる事業者・特定事業所向けの温対法SHK算定・EEGS電子報告手続きが確認できません。',
    remediation: '毎年度、ロケーション基準Scope 1+2合計が3,000 t-CO2以上か判定し、該当する場合はEEGSによる定期報告書提出を実施してください。',
  },
  {
    id: 'non_fossil_jcredit_tracking',
    title: '非化石証書（トラッキング付）・J-クレジット無効化シリアル番号管理',
    criterion: '再エネ価値・オフセット二重計上防止 / 無効化口座記録',
    weight: 12,
    severity: 'MEDIUM',
    pattern: /(?:非化石証書|j-?クレジット|jクレジット|トラッキング|再エネ証書|無効化|シリアル番号)/i,
    antiPattern: /(?:証書二重計上|無効化手続なし|jクレジット根拠省略)/i,
    detail: '非化石証書（FIT/非FIT・トラッキング属性）やJ-クレジット償却のシリアル番号・償却期間・二重計上防止ルールが未整備です。',
    remediation: '購入した非化石証書の電源属性とJ-クレジット無効化通知（シリアル番号・対象年度）を証憑台帳に紐づけて保管してください。',
  },
  {
    id: 'greenwash_claim_substantiation',
    title: '環境表示（グリーンウォッシュ防止）・カーボンニュートラル根拠開示',
    criterion: '景品表示法・環境省「環境表示ガイドライン」/ ISO 14021',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:グリーンウォッシュ|景品表示法|環境表示ガイドライン|算定範囲明記|オフセット前総量|残余排出)/i,
    antiPattern: /(?:根拠省略でカーボンニュートラル|総量非開示|実質ゼロと無条件表示)/i,
    detail: '「カーボンニュートラル」「実質CO2ゼロ」等の表示を行う際の、対象範囲明記・オフセット前総排出量の並列開示・根拠照合が不足しています。',
    remediation: '環境表示を行う製品・事業範囲・オフセット前の総排出量・償却済みクレジット量を明示し、残余排出がある場合は実質ゼロ表示を控えてください。',
  },
  {
    id: 'third_party_limited_assurance',
    title: '第三者保証（限定的保証 / ISO 14064-3・ISSA 5000）受審準備',
    criterion: 'サステナビリティ情報の第三者保証基準（ISSA 5000 / ISO 14064-3）',
    weight: 12,
    severity: 'MEDIUM',
    pattern: /(?:第三者保証|限定的保証|iso\s*14064-3|issa\s*5000|検証機関|算定根拠資料)/i,
    antiPattern: /(?:第三者検証拒否|保証準備なし|算定ワークシート破棄)/i,
    detail: 'SSBJ基準・機関投資家開示で求められる第三者限定的保証（バウンダリ整合・算定シート再現性検証）への準備が記載されていません。',
    remediation: 'ISO 14064-3 / ISSA 5000水準の検証に耐える組織バウンダリ図・係数出典一覧・集計ワークシートを整備してください。',
  },
  {
    id: 'audit_trail_retention',
    title: '電気検針票・燃料伝票・排出係数出典の監査証跡＆多年度保存',
    criterion: 'SHK/SSBJ 算定根拠証憑保管（5〜7年保存・内部統制）',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:請求書|検針票|燃料伝票|証憑保存|7年|5年|算定ファイル|内部統制)/i,
    antiPattern: /(?:検針票保存なし|根拠証憑未保管|概算手入力のみ)/i,
    detail: '各事業所・子会社の電気検針票、都市ガス/軽油等伝票および年次電力排出係数の元帳証憑を長期保存する内部統制ルールがありません。',
    remediation: '活動量元伝票（検針票・請求書）と係数更新履歴を少なくとも5〜7年間検索可能に保存する内部統制規程を制定してください。',
  },
];

function round3(n) {
  return Math.round(Number(n) * 1000) / 1000;
}

export function calculateGhgInventory({
  scope1FuelTco2 = 0,
  electricityKwh = 0,
  locationFactorKgKwh = 0.434,
  marketFactorKgKwh = 0.434,
  nonFossilCertKwh = 0,
  scope3SpendMjpy = 0,
  spendIntensityTco2PerMjpy = 2.5,
  jcreditOffsetTco2 = 0,
  claimedCarbonNeutral = false,
} = {}) {
  const s1 = Math.max(0, Number(scope1FuelTco2) || 0);
  const elec = Math.max(0, Number(electricityKwh) || 0);
  const locFac = Math.max(0, Number(locationFactorKgKwh) || 0);
  const mktFac = Math.max(0, Number(marketFactorKgKwh) || 0);
  const nonFossil = Math.max(0, Number(nonFossilCertKwh) || 0);
  const s3Spend = Math.max(0, Number(scope3SpendMjpy) || 0);
  const s3Intensity = Math.max(0, Number(spendIntensityTco2PerMjpy) || 0);
  const jcredit = Math.max(0, Number(jcreditOffsetTco2) || 0);
  const claimed = Boolean(claimedCarbonNeutral);

  const scope1Tco2 = round3(s1);
  const scope2LocationTco2 = round3((elec * locFac) / 1000);
  const billableMarketKwh = Math.max(0, elec - nonFossil);
  const scope2MarketTco2 = round3((billableMarketKwh * mktFac) / 1000);
  const scope3Cat1Tco2 = round3(s3Spend * s3Intensity);

  const scope12LocationTco2 = round3(scope1Tco2 + scope2LocationTco2);
  const scope12MarketTco2 = round3(scope1Tco2 + scope2MarketTco2);
  const totalGrossTco2 = round3(scope1Tco2 + scope2MarketTco2 + scope3Cat1Tco2);
  const residualNetTco2 = round3(Math.max(0, totalGrossTco2 - jcredit));

  const shkMandatoryReporting = scope12LocationTco2 >= 3000;
  const greenwashOverclaim = Boolean(claimed && residualNetTco2 > 0);

  return {
    scope1Tco2,
    scope2LocationTco2,
    scope2MarketTco2,
    scope3Cat1Tco2,
    scope12LocationTco2,
    scope12MarketTco2,
    totalGrossTco2,
    jcreditOffsetTco2: round3(jcredit),
    residualNetTco2,
    shkMandatoryReporting,
    claimedCarbonNeutral: claimed,
    greenwashOverclaim,
  };
}

export function auditSsbjCarbonPolicy(policyText = '', options = {}) {
  const normalized = String(policyText || '').replace(/\u3000/g, ' ').trim();
  const inventory = calculateGhgInventory(options);
  const hasShkFilingPlan = Boolean(options.hasShkFilingPlan);

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
        detail: negated ? `NG運用パターン検出（${pillar.detail}）` : pillar.detail,
        remediation: pillar.remediation,
      });
    }
  }

  let penalty = 0;
  if (inventory.shkMandatoryReporting && !hasShkFilingPlan) {
    penalty += 15;
    findings.push({
      id: 'shk_filing_missing',
      title: '温対法SHK特定排出者（3,000 t-CO2/年以上）到達にもかかわらずEEGS報告計画未登録',
      criterion: `温対法（Scope 1+2 ロケーション基準 ${inventory.scope12LocationTco2} t-CO2 >= 3,000 t-CO2）`,
      severity: 'HIGH',
      detail: `Scope 1+2ロケーション基準合計が ${inventory.scope12LocationTco2} t-CO2 に達していますが、EEGS定期報告の提出計画が確認されていません。`,
      remediation: 'EEGS電子報告システムによる年次特定排出者報告のスケジュールと算定担当体制を登録してください。',
    });
  }

  if (inventory.greenwashOverclaim) {
    penalty += 20;
    findings.push({
      id: 'greenwash_overclaim',
      title: '残余排出（Net > 0 t-CO2）残存状態でのカーボンニュートラル表示（グリーンウォッシュリスク）',
      criterion: `景品表示法・環境表示ガイドライン（総量 ${inventory.totalGrossTco2} t - オフセット ${inventory.jcreditOffsetTco2} t = 残余 ${inventory.residualNetTco2} t）`,
      severity: 'HIGH',
      detail: `J-クレジット等控除後も残余排出量が ${inventory.residualNetTco2} t-CO2 残っている状態でカーボンニュートラル訴求を行っており、景品表示法上の優良誤認となる恐れがあります。`,
      remediation: 'オフセット量を総排出量まで積み増すか、対象バウンダリを限定明記した上で「一部オフセット済み」等正確な表現へ修正してください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore - penalty));
  let readinessLabel = '開示不備・グリーンウォッシュ是正必須';
  let status = 'fail';
  if (score >= 88 && findings.every((f) => f.severity !== 'HIGH')) {
    readinessLabel = 'SSBJ・温対法SHK・環境表示 基準充足';
    status = 'pass';
  } else if (score >= 65) {
    readinessLabel = '一部補完推奨（開示注記・保証準備確認）';
    status = 'warn';
  }

  return {
    score,
    status,
    readinessLabel,
    inventory,
    passedPillars,
    findings,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
  };
}

export function generateSsbjCertificateMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const period = String(meta.reportingPeriod || '2026年度').trim() || '2026年度';
  const today = new Date().toISOString().slice(0, 10);
  const inv = auditResult.inventory;

  const lines = [
    '# SSBJ サステナビリティ（気候関連 GHG Scope 1〜3）算定・環境表示監査証明書',
    '',
    `- **作成日**: ${today}`,
    `- **対象事業者名**: ${org}`,
    `- **算定対象期間**: ${period}`,
    `- **総合適合スコア**: **${auditResult.readinessLabel}**（\`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    '',
    '## 1. GHG インベントリ算定結果サマリ（t-CO2）',
    '',
    `- **Scope 1（燃料直接排出）**: \`${inv.scope1Tco2}\` t-CO2`,
    `- **Scope 2（ロケーション基準 / マーケット基準）**: \`${inv.scope2LocationTco2}\` t-CO2 / \`${inv.scope2MarketTco2}\` t-CO2`,
    `- **温対法SHK 特定排出者判定（Scope 1+2 Loc >= 3,000 t）**: \`${inv.shkMandatoryReporting ? '特定排出者該当 (EEGS報告義務)' : '閾値未満'}\`（\`${inv.scope12LocationTco2}\` t-CO2）`,
    `- **Scope 3（カテゴリ1 金額ベース推計）**: \`${inv.scope3Cat1Tco2}\` t-CO2`,
    `- **オフセット前総量 (S1+S2 Mkt+S3)**: \`${inv.totalGrossTco2}\` t-CO2 / **J-クレジット等償却量**: \`${inv.jcreditOffsetTco2}\` t-CO2`,
    `- **残余純排出量 (Net Emissions)**: \`${inv.residualNetTco2}\` t-CO2 / **グリーンウォッシュ超過警告**: \`${inv.greenwashOverclaim ? '警告あり（残余排出>0）' : '問題なし'}\``,
    '',
    '## 2. SSBJ / 温対法 / 環境表示 8大要件の適合・是正状況',
    '',
    '| 統制要件 | 判定 | 根拠 / 是正アクション |',
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
    '*本証明書は TANSOGATE（炭素門）により社外サーバー・外部LLMへ原価や検針票データを一切送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
