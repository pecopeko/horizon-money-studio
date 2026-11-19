/**
 * HANSHAGATE（清廉門）Core Engine
 * 東京都暴排条例・東証上場審査 反社排除条項 / 犯収法第4条 実質的支配者(UBO 25%超・50%超間接支配・7年保存) /
 * 改正公益通報者保護法（従事者指定・フリーランス保護・探索禁止）ローカル診断エンジン（外部通信ゼロ）
 */

const PILLARS = [
  {
    id: 'hansha_5yr_rep',
    title: '反社会的勢力非該当・過去5年＆将来表明保証',
    criterion: '暴排条例・東証ガイドライン 属性要件',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:反社会的勢力|反社|暴力団|暴排|(?:5年|５年).*該当しない|将来にわたって)/i,
    antiPattern: /(?:反社確認不要|5年要件削除|暴力団関係容認)/i,
    detail: '自社・役員・主要株主が現在および過去5年間、かつ将来にわたり反社会的勢力に該当しない表明保証が不足しています。',
    remediation: '暴力団・総会屋・半グレ等および過去5年間非該当・将来保証（暴排条項標準ひな形）を明記してください。',
  },
  {
    id: 'kyoseisha_scope',
    title: '共生者・資金提供・不当要求（暴力的要求行為）網羅',
    criterion: '暴排条例 密接交際者・共生者要件',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:共生者|密接交際|資金提供|利益供与|不当要求|暴力的要求|取引関係)/i,
    antiPattern: /(?:共生者除外|交際関係不問)/i,
    detail: '「自ら反社でない」だけでなく、反社への資金提供・利益供与・不当な利用を行う共生者（密接交際者）の排除が未記載です。',
    remediation: '共生者（資金・便宜供与や不当利用関係）および法螺・脅迫等の不当要求行為の禁止対象への追加を明記してください。',
  },
  {
    id: 'no_notice_termination',
    title: '反社該当時の無催告即時解除条項',
    criterion: '暴排契約条項 解除権限',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:無催告|催告を要せず|催告なく|直ちに解除|即時解除)/i,
    antiPattern: /(?:催告の上解除|事前催告を要し)/i,
    detail: '相手方の反社該当や虚偽申告発覚時に催告期間を置かず直ちに契約解除できる「無催告解除」権限が欠落しています。',
    remediation: '「何らの催告を要せず直ちに本契約の全部または一部を解除できる」無催告解除文言を入れてください。',
  },
  {
    id: 'damage_waiver',
    title: '暴排解除に伴う相手方損害の賠償免責条項',
    criterion: '暴排契約条項 損害賠償免責',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:一切.{0,10}(?:賠償|請求).{0,6}(?:しない|負わない)|損害が生じても.{0,8}請求|損害賠償免責)/i,
    antiPattern: /(?:解除時に損害賠償を負担する|相手方の損失を補償する)/i,
    detail: '反社解除の結果相手方に損害が生じても解除側が賠償責任を負わない旨（損害賠償免責）が契約上明記されていません。',
    remediation: '「解除により相手方に損害が生じても一切賠償・補償責任を負わない」旨の免責条項を追加してください。',
  },
  {
    id: 'kyc_ubo_peps_7yr',
    title: '犯収法 実質的支配者（UBO 25%超）・PEPs・確認記録7年保存',
    criterion: '犯罪収益移転防止法第4条・第6条 / 施行規則11条2項',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:犯収法|実質的支配者|ubo|25%|peps|外国の重要な公的地位|7年|７年|確認記録)/i,
    antiPattern: /(?:確認記録保存なし|ubo確認不要|7年未満廃棄)/i,
    detail: '犯罪収益移転防止法に基づく自然人実質的支配者（25%超間接支配含む）・外国PEPs確認および確認記録7年保存体制が不明確です。',
    remediation: '25%超議決権自然人（50%超支配法人合算）の把握、外国PEPs該当確認、確認記録の取引終了後7年保存を規定化してください。',
  },
  {
    id: 'whistleblower_designated_staff',
    title: '公益通報対応業務従事者の書面指定（刑事罰対象守秘義務）',
    criterion: '公益通報者保護法 第11条・第21条（守秘義務違反30万円以下罰金）',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:従事者.{0,8}指定|公益通報|守秘義務|刑事罰|外部窓口|内部通報)/i,
    antiPattern: /(?:従事者指定なし|守秘義務規定なし)/i,
    detail: '公益通報受付・調査担当者を「公益通報対応業務従事者」として書面等で指定し、第12条の厳格な守秘義務を周知する体制が見当たりません。',
    remediation: '人事・法務等の窓口担当者を社内辞令等で「公益通報対応業務従事者」へ明確指定し、30万円以下罰金対象の守秘義務規程を整備してください。',
  },
  {
    id: 'whistleblower_freelance_1yr',
    title: 'フリーランス・退職後1年以内労働者の公益通報保護範囲',
    criterion: '改正公益通報者保護法（労働者・退職者1年・フリーランス業務委託）',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:フリーランス|業務委託|特定受託|退職後1年|退職後１年|役員.*含む)/i,
    antiPattern: /(?:正社員のみ受付|退職者は対象外|委託先は通報対象外)/i,
    detail: '改正公益通報者保護法が保護対象とする退職後1年以内の元従業員・役員・フリーランス（業務委託従事者）の窓口対象化が漏れています。',
    remediation: '正社員のみならず退職後1年以内の元従業員・役員および業務委託/フリーランスも公益通報窓口の利用対象と明記してください。',
  },
  {
    id: 'whistleblower_no_hunt_retaliation',
    title: '通報者の特定・探索行為禁止＆不利益取扱い・懲戒抑止禁止',
    criterion: '改正公益通報者保護法（探索行為禁止・立証負担軽減）',
    weight: 11,
    severity: 'HIGH',
    pattern: /(?:(?:特定|探索).{0,6}(?:禁止|しない)|犯人探し.{0,4}禁止|不利益.{0,6}(?:禁止|扱いしない)|通報妨害禁止)/i,
    antiPattern: /(?:通報者を特定・探索(?!.{0,4}禁止)|不利益処分を行う)/i,
    detail: '通報者を割り出そうとする「探索行為（犯人探し）」禁止および通報を理由とする解雇・減給・業務委託解除の禁止規定が不足しています。',
    remediation: '「通報者の特定・探索行為を厳禁し、通報・相談を理由とした一切の不利益取扱いを行わない」条項を明文化してください。',
  },
];

export function computeUboBeneficialOwners(holders = [], representativeName = '') {
  const list = Array.isArray(holders) ? holders : [];
  const personTotals = new Map();
  const warnings = [];
  let totalPctChecked = 0;

  for (const h of list) {
    if (!h || typeof h !== 'object') continue;
    const directPct = Number(h.directPct ?? h.direct_pct ?? 0);
    if (!Number.isFinite(directPct) || directPct <= 0) continue;
    totalPctChecked += directPct;
    const hType = String(h.type || 'individual').toLowerCase();
    const hName = String(h.name || '不明株主').trim();

    if (hType === 'individual') {
      personTotals.set(hName, (personTotals.get(hName) || 0) + directPct);
    } else {
      const controllerName = String(h.controllerName ?? h.controller_name ?? '').trim();
      const controllerPct = Number(h.controllerPct ?? h.controller_pct ?? 0);
      if (controllerName && Number.isFinite(controllerPct) && controllerPct > 50) {
        personTotals.set(controllerName, (personTotals.get(controllerName) || 0) + directPct);
      } else {
        warnings.push(`法人株主「${hName} (${directPct}%)」は50%超支配の自然人が未特定のため間接議決権合算から除外されました。`);
      }
    }
  }

  const ubos = [];
  for (const [name, pct] of personTotals.entries()) {
    const rounded = Math.round(pct * 100) / 100;
    if (rounded > 50) {
      ubos.push({ name, effectivePct: rounded, basis: 'dominant_ubo_over_50' });
    } else if (rounded > 25) {
      ubos.push({ name, effectivePct: rounded, basis: 'ubo_over_25' });
    }
  }
  ubos.sort((a, b) => b.effectivePct - a.effectivePct);

  let fallbackRepresentativeUsed = false;
  if (ubos.length === 0) {
    const rep = String(representativeName || '').trim() || '代表取締役（要氏名入力）';
    fallbackRepresentativeUsed = true;
    ubos.push({ name: rep, effectivePct: 0, basis: 'deemed_representative' });
  }

  return {
    ubos,
    fallbackRepresentativeUsed,
    totalPctChecked: Math.round(totalPctChecked * 100) / 100,
    warnings,
  };
}

export function auditHanshaKycPolicy(clauseAndPolicyText = '', options = {}) {
  const normalized = String(clauseAndPolicyText || '').replace(/\u3000/g, ' ').trim();
  const holders = options.holders ?? [];
  const representativeName = options.representativeName ?? '';
  const uboResult = computeUboBeneficialOwners(holders, representativeName);

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
        detail: negated ? `NG条文パターン検出（${pillar.detail}）` : pillar.detail,
        remediation: pillar.remediation,
      });
    }
  }

  const score = Math.min(100, Math.max(0, rawScore));
  let readinessLabel = '未整備・取引開始前是正必須';
  let status = 'fail';
  if (score >= 88 && findings.every((f) => f.severity !== 'HIGH')) {
    readinessLabel = '上場/暴排・犯収法・公益通報 基準充足';
    status = 'pass';
  } else if (score >= 65) {
    readinessLabel = '一部補完推奨（要確認）';
    status = 'warn';
  }

  return {
    score,
    status,
    readinessLabel,
    uboResult,
    passedPillars,
    findings,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
  };
}

export function generateHanshaPledgeMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const rep = String(meta.representativeName || '代表取締役').trim() || '代表取締役';
  const today = new Date().toISOString().slice(0, 10);

  const uboLines = auditResult.uboResult.ubos.map(
    (u) => `- **${u.name}**（判定区分: \`${u.basis}\` / 実質議決権比率: \`${u.effectivePct}%\`）`
  );

  const lines = [
    '# 反社会的勢力排除に関する表明・確約書 兼 犯収法実質的支配者（UBO）・内部通報体制確認書',
    '',
    `- **作成日**: ${today}`,
    `- **表明法人名**: ${org}`,
    `- **代表者名**: ${rep}`,
    `- **ガバナンス監査スコア**: **${auditResult.readinessLabel}**（\`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    '',
    '## 1. 実質的支配者（犯罪収益移転防止法施行規則 第11条第2項に基づく判定結果）',
    '',
    ...uboLines,
    '',
    '## 2. 審査項目別の適合・是正状況',
    '',
    '| 統制項目 | 判定 | 根拠 / 是正事項 |',
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
    '## 3. 標準表明・無催告解除確約（契約反映推奨条項）',
    '',
    '1. 表明者は、現在および過去5年間、暴力団・総会屋・半グレ等の反社会的勢力または共生者に該当せず、将来にわたっても該当しないことを表明・確約します。',
    '2. 表明に反する事実が判明した場合、相手方は何らの催告を要せず直ちに本契約を解除できるものとし、当該解除により表明者に損害が生じても相手方は一切の賠償責任を負わないものとします。',
    '',
    '---',
    '*本確認書は HANSHAGATE（清廉門）により株主データ・契約条項を社外サーバーへ一切送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
