export const SPECIFIED_INFRA_SECTORS = new Set([
  'electricity',
  'gas',
  'petroleum',
  'water',
  'railways',
  'freight',
  'maritime',
  'aviation',
  'telecom',
  'broadcasting',
  'postal',
  'banking',
  'payment',
  'credit',
  'trust',
]);

const PILLARS = [
  {
    id: 'essential_infra_prior_notification',
    title: '特定社会基盤役務・特定重要設備の事前届出義務',
    criterion: '経済安全保障推進法 第52条（事前届出・変更勧告対応）',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:特定社会基盤|特定重要設備|事前届出|主務大臣届出|導入前審査)/i,
    antiPattern: /(?:事前届出せず|無届で導入|事後届出のみ|事前届出省略)/i,
    remediation: '基幹インフラ15業種の特定重要設備を導入・委託する際は導入前に主務大臣へ事前届出・変更審査対応を完了する条項を明記してください。',
  },
  {
    id: 'outsourcing_subcontractor_control',
    title: '維持管理等委託・再委託先・実質的支配者審査',
    criterion: '経済安全保障推進法（維持管理等委託・外資支配・再委託統制）',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:維持管理等委託|再委託承認|外国人支配|実質的支配者|供給元国)/i,
    antiPattern: /(?:無届で海外委託|再委託先無審査|海外保守無確認|無承認再委託)/i,
    remediation: '保守・クラウド運用の委託先・再委託先における議決権・外国人支配関係および供給元国情報を事前確認し、事前書面承認制としてください。',
  },
  {
    id: 'security_clearance_consent_eval',
    title: 'セキュリティ・クリアランス適性評価・本人同意・不利益取扱い禁止',
    criterion: '重要経済安保情報保護・活用法（2025年5月施行・適性評価）',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:適性評価|重要経済安保情報|セキュリティ・?クリアランス|本人同意|不利益取扱い禁止)/i,
    antiPattern: /(?:適性評価未了|未クリアランス者共有|本人同意なく調査|同意なし適性調査)/i,
    remediation: '重要経済安保情報は政府による適性評価（本人同意取得・拒否時の不利益取扱い禁止）を完了した取扱担当者のみへ閲覧限定してください。',
  },
  {
    id: 'facility_isolation_penalty_notice',
    title: '適合事業者認定・施設保全・電磁的遮断・漏えい罰則周知',
    criterion: '重要経済安保情報保護・活用法 第10条・第23条',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:適合事業者|施設保全|電磁的遮断|物理的隔離|秘密保持誓約|刑事罰周知)/i,
    antiPattern: /(?:無制限複製|個人端末持ち帰り|非分離ネットワーク保存|施設保全省略)/i,
    remediation: '適合事業者要件に基づき物理的隔離・電磁的遮断（オフライン区画）と個人端末持出禁止、漏えい時刑事罰（5年以下拘禁刑等）の周知を整備してください。',
  },
  {
    id: 'critical_commodity_diversification',
    title: '特定重要物資（半導体・蓄電池・クラウド・重要鉱物等）調達分散＆備蓄',
    criterion: '経済安全保障推進法（サプライチェーン強靱化計画）',
    weight: 12,
    severity: 'MEDIUM',
    pattern: /(?:特定重要物資|供給途絶対策|複数購買|代替調達|備蓄計画|マルチソース)/i,
    antiPattern: /(?:単一国100%依存放置|代替調達計画なし|備蓄ゼロ放置)/i,
    remediation: '特定重要物資の単一国集中リスク（50%以上）を避け、複数地域への分散購買・代替調達ルートおよび安全在庫・備蓄計画を定義してください。',
  },
  {
    id: 'patent_nonpublication_screening',
    title: '特許出願非公開・保全指定対象技術チェック＆外国出願事前確認',
    criterion: '経済安全保障推進法（特許出願の非公開制度）',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:特許出願非公開|保全指定|外国出願禁止|安全保障技術審査|一次審査)/i,
    antiPattern: /(?:保全指定技術を無断外国出願|安全保障技術確認せず公開)/i,
    remediation: '安全保障技術対象（政令指定技術分野）の研究成果について一次審査・保全指定前の外国出願禁止および社内技術審査ゲートを設置してください。',
  },
  {
    id: 'core_program_sbom_foreign_access',
    title: '重要プログラム SBOM管理＆外国政府アクセス・越境遮断',
    criterion: '特定重要設備コアソフトウェア・SBOMガバナンス',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:重要プログラム|SBOM|外国政府アクセス遮断|データ国内保管|ソースコード監査)/i,
    antiPattern: /(?:SBOM不備|ブラックボックス外部プログラム無検査)/i,
    remediation: '重要設備に組み込む重要プログラムについてSBOM管理・ソースコード検証および海外拠点・外国法令に基づく政府アクセス遮断を契約担保してください。',
  },
  {
    id: 'audit_trail_incident_reporting',
    title: '漏えいインシデント即報・主務大臣報告・5年以上アクセス証跡保存',
    criterion: '経済安全保障・適合事業者 内部監査記録要件',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:インシデント即報|主務大臣報告|監査証跡|点検記録|アクセスログ保存)/i,
    antiPattern: /(?:ログ保存なし|漏えい時無報告|アクセス履歴破棄)/i,
    remediation: '不正アクセスや重要経済安保情報漏えい疑い時の主務大臣即報手順とアクセスログ・監査証跡の5年以上保全を規程化してください。',
  },
];

export function evaluateKeizaianpoObligations(options = {}) {
  const sector = String(options.sector || 'telecom').trim().toLowerCase() || 'general';
  const isSpecifiedInfra = Boolean(
    options.isSpecifiedInfrastructureOperator || SPECIFIED_INFRA_SECTORS.has(sector)
  );
  const introducesEquipment = Boolean(options.introducesCriticalEquipment);
  const outsourcesMaintenance = Boolean(options.outsourcesCriticalMaintenance);
  const priorNotificationFiled = Boolean(options.priorNotificationFiled);
  const handlesClassifiedInfo = Boolean(options.handlesClassifiedEconInfo);
  const allHandlersCleared = Boolean(options.allHandlersCleared);
  const isCriticalCommodity = Boolean(options.isCriticalCommodity);
  const singleCountryDependencyPct = Math.max(
    0,
    Math.min(100, Number(options.singleCountryDependencyPct || 0))
  );

  const requiresPriorNotification =
    isSpecifiedInfra && (introducesEquipment || outsourcesMaintenance);
  const missingPriorNotificationViolation =
    requiresPriorNotification && !priorNotificationFiled;
  const unclearedAccessViolation = handlesClassifiedInfo && !allHandlersCleared;
  const singleSourceConcentrationRisk =
    isCriticalCommodity && singleCountryDependencyPct >= 50;

  return {
    sector,
    isSpecifiedInfrastructureOperator: isSpecifiedInfra,
    requiresPriorNotification,
    priorNotificationFiled,
    missingPriorNotificationViolation,
    handlesClassifiedEconInfo: handlesClassifiedInfo,
    allHandlersCleared,
    unclearedAccessViolation,
    isCriticalCommodity,
    singleCountryDependencyPct: Math.round(singleCountryDependencyPct * 100) / 100,
    singleSourceConcentrationRisk,
  };
}

export function auditKeizaianpoPolicy(policyText, options = {}) {
  const normalized = String(policyText || '').trim();
  const metrics = evaluateKeizaianpoObligations(options);

  let rawScore = 0;
  const passedPillars = [];
  const findings = [];

  for (const pillar of PILLARS) {
    const matched = pillar.pattern.test(normalized);
    const negated = pillar.antiPattern.test(normalized);
    if (matched && !negated) {
      rawScore += pillar.weight;
      passedPillars.push(pillar.id);
    } else {
      findings.push({
        id: `ANPO-${pillar.id.toUpperCase()}`,
        title: pillar.title,
        criterion: pillar.criterion,
        severity: pillar.severity,
        detail: negated
          ? '禁止パターン（無届導入・未適性評価者共有・単一国依存放置等）が検出されました。'
          : '経済安全保障・セキュリティクリアランス法上の必須統制記述が不足しています。',
        remediation: pillar.remediation,
      });
    }
  }

  let penalty = 0;
  if (metrics.missingPriorNotificationViolation) {
    penalty += 30;
    findings.unshift({
      id: 'ANPO-MISSING-PRIOR-NOTIFICATION',
      title: '特定社会基盤事業者の特定重要設備・維持管理委託に係る事前届出欠落',
      criterion: '経済安全保障推進法（基幹インフラ役務・事前届出義務）',
      severity: 'HIGH',
      detail: '指定業種かつ設備導入/維持管理委託に該当するにもかかわらず、事前届出完了フラグが未設定です。',
      remediation: '導入・委託前に主務大臣へ特定重要設備導入等計画書を事前提出し、審査期間中の実施を停止してください。',
    });
  }
  if (metrics.unclearedAccessViolation) {
    penalty += 35;
    findings.unshift({
      id: 'ANPO-UNCLEARED-PERSONNEL-ACCESS',
      title: '重要経済安保情報の適性評価未了者への共有・アクセス権限違反',
      criterion: '重要経済安保情報保護・活用法（適性評価必須原則）',
      severity: 'HIGH',
      detail: '重要経済安保情報を取り扱う案件で全担当者の適性評価完了が確認されていません。',
      remediation: '取扱者を適性評価合格済み人員のみへ限定し、アクセス制御と本人同意書面を即時整備してください。',
    });
  }
  if (metrics.singleSourceConcentrationRisk) {
    penalty += 15;
    findings.push({
      id: 'ANPO-CRITICAL-COMMODITY-CONCENTRATION',
      title: `特定重要物資の単一国依存集中リスク (${metrics.singleCountryDependencyPct}% >= 50%)`,
      criterion: '経済安全保障推進法（サプライチェーン分散要件）',
      severity: 'MEDIUM',
      detail: `特定重要物資の単一国依存度が ${metrics.singleCountryDependencyPct}% に達し、供給途絶時の事業継続リスクが高水準です。`,
      remediation: '調達先を複数国・複数ベンダーへ分散（50%未満目安）し、代替調達先と備蓄計画を策定してください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore - penalty));
  const hasHigh = findings.some((f) => f.severity === 'HIGH');
  let status = 'fail';
  if (score >= 88 && !hasHigh) {
    status = 'pass';
  } else if (
    score >= 65 &&
    !metrics.missingPriorNotificationViolation &&
    !metrics.unclearedAccessViolation
  ) {
    status = 'warn';
  }

  return {
    score,
    status,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
    passedPillars,
    findings,
    metrics,
  };
}

export function generateKeizaianpoPlanMarkdown(auditResult, meta = {}) {
  const org = (meta.organizationName || '〇〇株式会社').trim();
  const vendor = (meta.vendorName || '重要システム委託先・設備導入案件').trim();
  const m = auditResult.metrics;
  const issueLines =
    auditResult.findings.length === 0
      ? '- 指摘事項なし（経済安全保障推進法8領域・重要経済安保情報セキュリティクリアランス・事前届出要件を完全充足）'
      : auditResult.findings
          .map((f) => `- **[${f.severity}] ${f.id} — ${f.title}**: ${f.remediation}`)
          .join('\n');

  return [
    '# 経済安全保障・セキュリティクリアランス 事前届出・保全管理計画書',
    '',
    `- **事業者名 / 管理部門**: ${org}`,
    `- **対象システム / 委託先 / 物資名**: ${vendor}`,
    `- **総合適合スコア**: \`${auditResult.score} / 100点\` (判定: \`${auditResult.status.toUpperCase()}\`)`,
    `- **実行環境保証**: **ブラウザ内完全ローカル実行（外部通信 \`0\` 回 / 重要情報非送信）**`,
    '',
    '## 1. 法定要件スクリーニング結果',
    `- **特定社会基盤業種**: ${m.sector} (指定対象: \`${m.isSpecifiedInfrastructureOperator ? '対象業種' : '一般事業者'}\`)`,
    `- **特定重要設備・維持管理委託 事前届出**: ${
      m.missingPriorNotificationViolation
        ? '未届出違反リスク（事前届出必須）'
        : m.requiresPriorNotification
          ? '要届出・届出済'
          : '対象外'
    }`,
    `- **重要経済安保情報 適性評価 (クリアランス)**: ${
      m.unclearedAccessViolation
        ? '適性評価未了者アクセス違反リスク'
        : m.handlesClassifiedEconInfo
          ? '適性評価完了者限定'
          : '該当情報なし'
    }`,
    `- **特定重要物資 単一国依存度**: ${m.isCriticalCommodity ? `${m.singleCountryDependencyPct}%` : '非該当'}`,
    '',
    '## 2. 是正・保全管理アクション項目',
    issueLines,
    '',
    '## 3. 情報保全・監査誓約',
    '1. 重要経済安保情報の閲覧・保存・複写は政府認定適合事業者の電磁的遮断区画および適性評価合格者に限定する。',
    '2. 特定重要設備の保守・クラウド再委託を変更する際は、事前に主務大臣届出要否と外国人支配関係を再確認する。',
    '',
  ].join('\n');
}
