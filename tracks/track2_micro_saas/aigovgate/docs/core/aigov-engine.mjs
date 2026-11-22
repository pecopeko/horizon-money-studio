/**
 * AIGOVGATE（統治門）Core Engine
 * 総務省・経産省『AI事業者ガイドライン（第1.1版）』 / 著作権法第30条の4 /
 * 学習オプトアウト（シャドーAI統制） / EU AI Act リスク階層 / OSSモデル商用ライセンス ローカル診断エンジン
 */

const PILLARS = [
  {
    id: 'zero_training_shadow_ai',
    title: '学習オプトアウト（ZDR）・シャドーAI禁止統制',
    criterion: '経産省・総務省AI事業者ガイドライン 安全・データガバナンス',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:オプトアウト|zero.{0,4}data.{0,4}retention|zdr|学習(?:利用|に使わ|対象外)|シャドーai.{0,4}(?:禁止|統制)|法人契約|enterprise)/i,
    antiPattern: /(?:無料個人アカウント許可|学習オプトアウト不要|シャドーai容認|個人アカウント利用可)/i,
    detail: '無償個人アカウント（シャドーAI）禁止およびモデルの二次学習オプトアウト（Zero Data Retention）強制が未確認です。',
    remediation: '業務利用は法人契約API・オプトアウト有効環境のみに限定し、無認可の個人無料AIアカウント利用を禁止してください。',
  },
  {
    id: 'copyright_art30_4',
    title: '著作権法第30条の4（享受目的除外・作風狙い撃ち禁止）',
    criterion: '文化庁AIと著作権に関する考え方 / 第30条の4但書',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:第?30条の4|著作権法|享受目的|類似性|依拠性|特定作家|作風.{0,6}(?:禁止|回避)|出典確認|既存著作物)/i,
    antiPattern: /(?:特定作家の作風模倣(?!.{0,6}(?:禁止|しない|不可))|著作物無断学習許可|作風コピー(?!.{0,6}(?:禁止|しない|不可))|既存キャラそのまま)/i,
    detail: '著作権法第30条の4但書（享受目的併存・特定クリエイターの作風狙い撃ち）および生成物の類似性・依拠性チェック基準が不足しています。',
    remediation: '特定作家・作品の作風模倣プロンプトを禁止し、公開前・商用利用前に既存著作物との類似性調査を実施する規定を入れてください。',
  },
  {
    id: 'pii_trade_secret_gate',
    title: '個人情報（APPI）・営業秘密マスキング事前ゲート',
    criterion: '個人情報保護委員会 注意喚起 / 不競法営業秘密',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:個人情報|pii|営業秘密|機密情報|マスキング|伏せ字|黒門|kurogate|秘密区分|入力禁止)/i,
    antiPattern: /(?:個人情報そのまま入力|機密入力許可|マイナンバー入力可)/i,
    detail: 'プロンプトへの個人情報（氏名・マイナンバー・T番号等）や未公開営業秘密の直接投入を遮断するルールが不明確です。',
    remediation: '外部AI送信前のローカルPIIマスキング（KUROGATE等）と顧客データ入力原則禁止ルールを明文化してください。',
  },
  {
    id: 'human_in_the_loop',
    title: '人間による最終確認（Human-in-the-Loop）',
    criterion: 'AI事業者ガイドライン 人間中心・意思決定統制',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:人間(?:による)?確認|human[- ]in[- ]the[- ]loop|hitl|最終判断|上長確認|ダブルチェック|レビュー必須|目視確認)/i,
    antiPattern: /(?:人間確認不要で自動決定|完全自動決定|ノーチェック公開|レビュー省略)/i,
    detail: 'AI出力を採用・採用判定・与信・顧客通知・コード本番反映する際の人間による責任確認プロセスが記載されていません。',
    remediation: '重要な業務判断や対外発信では必ず人間が事実関係・公平性・法令適合を確認してから承認するHITL原則を明記してください。',
  },
  {
    id: 'prompt_injection_output_eval',
    title: 'プロンプトインジェクション防御・ハルシネーション検証',
    criterion: 'AIセキュリティ・出力品質保証',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:プロンプトインジェクション|prompt injection|ハルシネーション|ファクトチェック|事実確認|出力検証|脆弱性検査)/i,
    antiPattern: /(?:検証不要|ファクトチェック省略|出力そのまま利用)/i,
    detail: '外部文書・WebページをRAG/エージェント読込する際のプロンプトインジェクション対策および誤情報検証ルールが不足しています。',
    remediation: 'RAG入力サニタイズ、AI生成コードの静的セキュリティ検証、および数値・法令引用の一次ソース照合を義務付けてください。',
  },
  {
    id: 'eu_high_risk_transparency',
    title: '透明性表示（AI生成明記）・用途別リスク評価',
    criterion: 'EU AI Act / AI事業者ガイドライン 透明性・アカウンタビリティ',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:ai生成.{0,6}(?:明記|表示)|透かし|チャットボット明示|eu\s*ai\s*act|リスク評価|影響評価|透明性)/i,
    antiPattern: /(?:ai利用非公開|表記隠蔽|人間になりすまし)/i,
    detail: '対話チャットボット・合成画像音声等のAI関与明示および高リスク領域（採用・与信等）の事前影響評価ルールが見当たりません。',
    remediation: 'チャット窓口や合成コンテンツへの「AI生成・応答」明示、および高リスク用途導入時の事前リスク評価手続を定めてください。',
  },
  {
    id: 'audit_log_incident',
    title: '利用ログ・プロンプト証跡保管＆インシデント連絡網',
    criterion: 'AIガバナンス 証跡保全・漏えい初動',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:利用ログ|プロンプトログ|監査証跡|監査ログ|インシデント|緊急停止|連絡窓口|csirt)/i,
    antiPattern: /(?:ログ保存なし|監査ログ不要|連絡体制なし)/i,
    detail: 'AI誤送信・情報漏えい・権利侵害申立て発生時の利用ログ追跡体制および即時利用停止窓口が不足しています。',
    remediation: 'APIプロンプト・承認記録の保管期間と、不適切出力・漏えい検知時のCSIRT/法務連絡およびAPIキー失効手順を明記してください。',
  },
  {
    id: 'governance_owner_caio',
    title: 'AI統括責任者（CAIO）・利用申請＆社内リテラシー研修',
    criterion: 'METI AIガバナンス・リテラシー教育',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:caio|統括責任者|推進責任者|利用申請|台帳|研修|リテラシー教育|定期見直し)/i,
    antiPattern: /(?:責任者不在|申請不要|研修なし)/i,
    detail: 'ツール認可台帳の管理者（CAIO/情シス/法務）および全社員向けAIリスク研修・ガイドライン改定サイクルが未設定です。',
    remediation: '利用ツール登録申請制、AI推進責任部署の明確化、および年1回以上の社内AIコンプライアンス研修を定めてください。',
  },
];

export function classifyAiUseCaseRisk(useCase = '', modelLicense = '') {
  const uc = String(useCase || '').trim();
  const lic = String(modelLicense || '').trim().toLowerCase();
  const warnings = [];

  let riskTier = 'minimal';
  if (/(?:サブリミナル|subliminal|社会スコア|social\s*scoring|無差別.*顔|untargeted.*facial|生体分類|職場.*感情監視|emotion\s*recognition.*workplace)/i.test(uc)) {
    riskTier = 'prohibited';
    warnings.push('EU AI Act 禁止AI領域（社会スコアリング・職場感情監視・無差別顔収集等）に該当する恐れがあり、導入不可です。');
  } else if (/(?:採用|人事評価|recruitment|hr\s*eval|与信|信用スコア|credit\s*scor|医療トリアージ|medical\s*triage|入試|成績評価|education.*grad)/i.test(uc)) {
    riskTier = 'high_risk';
    warnings.push('高リスクAI領域（採用・人事評価・与信・医療・教育判定等）に該当します。人間による最終審査・バイアス監査・説明責任が必須です。');
  } else if (/(?:チャットボット|chatbot|ディープフェイク|deepfake|合成メディア|synthetic\s*media|顧客窓口|customer\s*support|音声合成)/i.test(uc)) {
    riskTier = 'transparency';
    warnings.push('透明性義務対象（AIチャットボット・合成メディア）：相手方へAI生成・応答である旨の明示が必要です。');
  }

  let licenseStatus = 'review_required';
  if (/(?:cc-by-nc|non-commercial|nc-nd|research-only|academic-only)/i.test(lic)) {
    licenseStatus = 'restricted_non_commercial';
    warnings.push(`ライセンス違反リスク: モデルライセンス (${modelLicense}) は商用利用制限付きです。本番営利業務への組み込みは避けてください。`);
  } else if (/(?:apache-2\.0|mit|bsd|mpl-2\.0|commercial|enterprise-api)/i.test(lic)) {
    licenseStatus = 'commercial_ok';
  } else if (lic) {
    warnings.push(`ライセンス確認推奨: "${modelLicense}" の商用許諾・生成物著作権帰属条項を法務確認してください。`);
  } else {
    warnings.push('利用モデル・APIのライセンス種別が未記載です（Apache-2.0 / 法人契約API / CC-BY-NC等）。');
  }

  return {
    riskTier,
    licenseStatus,
    warnings,
  };
}

export function auditAiGovernancePolicy(policyText = '', options = {}) {
  const normalized = String(policyText || '').replace(/\u3000/g, ' ').trim();
  const useCase = options.useCase ?? '';
  const modelLicense = options.modelLicense ?? '';
  const riskClassification = classifyAiUseCaseRisk(useCase, modelLicense);

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
        detail: negated ? `危険・不適切容認ルールを検出（${pillar.detail}）` : pillar.detail,
        remediation: pillar.remediation,
      });
    }
  }

  if (riskClassification.riskTier === 'prohibited') {
    rawScore = Math.min(rawScore, 20);
    findings.unshift({
      id: 'eu_prohibited_ai',
      title: 'EU AI Act 禁止AI用途（導入停止要）',
      criterion: 'EU AI Act Art. 5 / AIガバナンス',
      severity: 'HIGH',
      detail: riskClassification.warnings.find((w) => w.includes('禁止AI')) || '禁止対象AI用途が指定されています。',
      remediation: '職場での感情監視・社会スコアリング・無差別顔収集を含む用途を設計から完全に除外してください。',
    });
  }

  if (riskClassification.licenseStatus === 'restricted_non_commercial') {
    rawScore = Math.max(0, rawScore - 15);
    findings.push({
      id: 'model_license_nc',
      title: '非商用モデルの業務利用リスク',
      criterion: 'OSSモデルライセンス・商用コンプライアンス',
      severity: 'HIGH',
      detail: `指定ライセンス (${modelLicense}) は非商用限定（NC/Research Only）の可能性があります。`,
      remediation: 'Apache-2.0 / MIT モデルのセルフホスト、または商用契約済みエンタープライズAPIへ切り替えてください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore));

  let readinessLabel = '整備不足・導入前是正必須';
  let status = 'fail';
  if (riskClassification.riskTier === 'prohibited') {
    readinessLabel = '禁止用途リスク検出（停止要）';
    status = 'fail';
  } else if (score >= 85 && findings.every((f) => f.severity !== 'HIGH')) {
    readinessLabel = 'ガイドライン第1.1版 充足';
    status = 'pass';
  } else if (score >= 65) {
    readinessLabel = '基本整備（一部強化推奨）';
    status = 'warn';
  }

  return {
    score,
    status,
    readinessLabel,
    riskClassification,
    passedPillars,
    findings,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
  };
}

export function generateAiGovernanceGuidelineMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const owner = String(meta.ownerTitle || 'CAIO / 情報セキュリティ・法務推進責任者').trim() || 'CAIO / 情報セキュリティ・法務推進責任者';
  const useCase = String(meta.useCase || '社内文書要約・コード補助').trim() || '社内文書要約・コード補助';
  const modelLicense = String(meta.modelLicense || 'enterprise-api').trim() || 'enterprise-api';
  const today = new Date().toISOString().slice(0, 10);

  const lines = [
    '# 社内生成AI利活用ガイドライン（総務省・経産省AI事業者ガイドライン第1.1版 / 著作権法第30条の4準拠）',
    '',
    `- **制定日**: ${today}`,
    `- **対象組織名**: ${org}`,
    `- **統括責任体制**: ${owner}`,
    `- **対象ユースケース**: ${useCase}（リスク区分: \`${auditResult.riskClassification.riskTier}\`）`,
    `- **利用モデル / ライセンス**: \`${modelLicense}\`（商用判定: \`${auditResult.riskClassification.licenseStatus}\`）`,
    `- **ガバナンス適合スコア**: **${auditResult.readinessLabel}**（\`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    '',
    '## 1. 統制項目別の準拠・是正ステータス',
    '',
    '| 統制領域 | 判定 | 詳細 / 是正アクション |',
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
    '## 2. 全従業員が遵守すべき禁止事項・必須手順',
    '',
    '1. **シャドーAIの禁止**: 会社認可外の無料・個人契約AIアカウントへ社内情報や取引先データを入力しません。',
    '2. **著作権法第30条の4の遵守**: 特定作家・既存著作物の作風や表現を狙い撃ちで模倣させる指示を行わず、対外公開前に類似性・権利侵害確認を行います。',
    '3. **個人情報・営業秘密の遮断**: 個人情報・マイナンバー・機密情報は事前マスキング後に許可APIへ投入し、人間による最終確認（HITL）を経て業務へ反映します。',
    '',
    '---',
    '*本ガイドライン草案は AIGOVGATE（統治門）により外部サーバーへ機密規程を送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
