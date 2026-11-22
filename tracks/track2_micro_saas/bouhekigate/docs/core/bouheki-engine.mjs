/**
 * BOUHEKIGATE（防壁門）Core Engine
 * METI 2026 サプライチェーン強化に向けたセキュリティ対策評価制度（★3・★4） /
 * 個人情報保護委員会（PPC）漏えい報告SLA / 不正競争防止法（営業秘密3要件） /
 * SPF & DMARC ローカル診断エンジン（外部通信ゼロ）
 */

const PILLARS = [
  {
    id: 'mfa_privileged',
    title: '特権ID管理・多要素認証（MFA / FIDO2）',
    criterion: 'METI ★3・★4 アカウント認証',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:mfa|多要素認証|二要素|2fa|fido2|webauthn|パスキー|特権id|最小権限|pam)/i,
    antiPattern: /(?:mfa未導入|多要素認証なし|パスワードのみ|id共有|特権共有)/i,
    detail: 'クラウド管理画面・VPN・メール・特権アカウントへのMFA強制および最小権限の明記が確認できません。',
    remediation: '全社員・管理者・VPN/SaaSへのフィッシング耐性MFA（FIDO2/TOTP）必須化と年1回以上の棚卸しを記載してください。',
  },
  {
    id: 'edr_vuln_patch',
    title: 'EDR導入・脆弱性管理（重要脆弱性迅速パッチ）',
    criterion: 'METI ★3・★4 端末・脆弱性対策',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:edr|epp|マルウェア|脆弱性|cve|セキュリティパッチ|sbom|waf|csirt|自動更新)/i,
    antiPattern: /(?:edr未導入|パッチ適用なし|サポート切れ|eol放置)/i,
    detail: '端末のEDR監視、およびインターネット公開機器・VPN・OSS（SBOM）の脆弱性パッチ適用SLAが不足しています。',
    remediation: '全業務端末へのEDR/EPP導入と、CVSS高/緊急脆弱性の迅速パッチ適用（例：公開資産7〜14日以内）方針を明記してください。',
  },
  {
    id: 'backup_321_drill',
    title: 'オフライン/イミュータブル バックアップ＆復旧訓練',
    criterion: 'METI ★3・★4 ランサムウェア耐性',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:バックアップ|backup|3-2-1|オフライン保管|immutable|イミュータブル|暗号化バックアップ|復旧訓練|bcp)/i,
    antiPattern: /(?:バックアップ未実施|バックアップなし|復旧テストなし)/i,
    detail: 'ランサムウェアに暗号化されない隔離/イミュータブル世代管理（3-2-1ルール）および復元テスト実績が確認できません。',
    remediation: '3-2-1方式（変更不可・オフライン隔離コピー1つ以上）と年1回以上のリストア訓練を明記してください。',
  },
  {
    id: 'incident_ppc_sla',
    title: 'インシデント初動・PPC漏えい速報(3〜5日)/確報(30日)体制',
    criterion: '改正APPI第26条 / METI ★4 報告網',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:速報|確報|個人情報保護委員会|ppc|3.{0,3}5日|30日|60日|24時間|72時間|初動対応|緊急連絡)/i,
    antiPattern: /(?:報告期限なし|連絡体制なし|通知義務なし)/i,
    detail: '漏えい発生時の取引先即時通知および個人情報保護委員会（PPC）への速報（概ね3〜5日以内）・確報（30日/60日以内）SLAが未記載です。',
    remediation: '緊急連絡窓口（CSIRT）、取引先への24〜72時間以内の初報、およびPPC速報(3〜5日)・確報(30日/不正目的60日)手順を明文化してください。',
  },
  {
    id: 'trade_secret_3req',
    title: '不正競争防止法 営業秘密3要件（秘密管理性・アクセス制限）',
    criterion: '不競法第2条6項 / 取引先秘密保持',
    weight: 12,
    severity: 'MEDIUM',
    pattern: /(?:営業秘密|秘密管理性|マル秘|アクセス制御|nda|秘密保持|持ち出し制限|dlp|usb禁止|生成ai入力禁止)/i,
    antiPattern: /(?:全社員閲覧可|持ち出し自由|usb制限なし|パブリック共有)/i,
    detail: '取引先から預託された技術・営業秘密の秘密管理性（区分表示・アクセス権分離・外部AI入力制限）が曖昧です。',
    remediation: '機密区分の明示、アクセス権限定、外部媒体/未契約クラウドAIへの入力禁止規程（NDA準拠）を記載してください。',
  },
  {
    id: 'subprocessor_control',
    title: '再委託先・サプライヤー管理（事前承諾＆契約義務）',
    criterion: 'METI ★3・★4 委託先統制',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:再委託|委託先|サプライヤー|事前承諾|書面承諾|契約書|同等水準|年次点検|監査)/i,
    antiPattern: /(?:無断再委託|委託先チェックなし)/i,
    detail: '業務を再委託する際の取引先事前承諾・同等セキュリティ水準の契約義務・定期点検ルールが確認できません。',
    remediation: '再委託時の事前書面承諾、セキュリティ要件のバック・トゥ・バック契約、および年1回の点検実施を明記してください。',
  },
  {
    id: 'log_encryption',
    title: '通信/保存暗号化（TLS1.2+/AES-256）＆監査ログ保全',
    criterion: 'METI ★3・★4 証跡保全・暗号化',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:tls\s*1\.[23]|https|aes-?256|暗号化|監査ログ|syslog|siem|改ざん|1年以上|90日以上)/i,
    antiPattern: /(?:平文保存|http利用|ログ未取得|ログ保存なし)/i,
    detail: '通信経路・保存データの暗号化方式および認証・操作監査ログの保存期間・改ざん防止措置が不足しています。',
    remediation: 'TLS 1.2/1.3・AES-256暗号化と、特権操作/認証ログの安全保管（推奨1年以上・NTP時刻同期）を記載してください。',
  },
];

export function parseEmailAuthPosture(spfRecord = '', dmarcRecord = '') {
  const spf = String(spfRecord || '').trim();
  const dmarc = String(dmarcRecord || '').trim();
  const warnings = [];

  const spfValid = /\bv=spf1\b/i.test(spf);
  let spfQualifier = 'missing';
  let spfLookups = 0;

  if (!spf) {
    warnings.push('SPFレコードが未入力です（例: v=spf1 include:_spf.example.jp -all）。');
  } else if (!spfValid) {
    spfQualifier = 'invalid';
    warnings.push('SPF構文エラー: "v=spf1" で開始してください。');
  } else {
    if (/(?:^|\s)-all(?:\s|$)/i.test(spf)) {
      spfQualifier = '-all';
    } else if (/(?:^|\s)~all(?:\s|$)/i.test(spf)) {
      spfQualifier = '~all';
      warnings.push('SPFがソフトフェイル (~all) です。★4相当には原則ハードフェイル (-all) を推奨します。');
    } else if (/(?:^|\s)\+all(?:\s|$)/i.test(spf)) {
      spfQualifier = '+all';
      warnings.push('重大危険: SPFに +all（全送信元許可）が設定されています。即時 -all へ修正してください。');
    } else if (/(?:^|\s)\?all(?:\s|$)/i.test(spf)) {
      spfQualifier = '?all';
      warnings.push('SPFが中立 (?all) です。-all または ~all に引き締めてください。');
    } else {
      spfQualifier = 'none';
      warnings.push('SPF末尾の all 修飾子 (-all / ~all) が欠落しています。');
    }

    const lookupMatches = spf.match(/(?:^|\s)(?:include:|redirect=|exists:|(?:[+\-~?])?(?:a|mx|ptr)(?:[:/]|(?=\s|$)))/gi);
    spfLookups = lookupMatches ? lookupMatches.length : 0;
    if (spfLookups > 10) {
      warnings.push(`RFC 7208 DNSルックアップ上限超過: ${spfLookups}回（10回以下にしてPermErrorを防止してください）。`);
    }
  }

  const dmarcValid = /\bv=DMARC1\b/i.test(dmarc);
  let dmarcPolicy = 'missing';
  let pct = 100;
  let ruaConfigured = false;

  if (!dmarc) {
    warnings.push('DMARCレコードが未入力です（例: v=DMARC1; p=reject; rua=mailto:dmarc@example.jp）。');
  } else if (!dmarcValid) {
    dmarcPolicy = 'invalid';
    warnings.push('DMARC構文エラー: "v=DMARC1" で開始してください。');
  } else {
    const pMatch = dmarc.match(/(?:^|[;\s])p\s*=\s*(reject|quarantine|none)\b/i);
    dmarcPolicy = pMatch ? pMatch[1].toLowerCase() : 'missing';
    if (dmarcPolicy === 'missing') {
      warnings.push('DMARCポリシー (p=reject / quarantine / none) が未指定です。');
    } else if (dmarcPolicy === 'none') {
      warnings.push('DMARCが監視のみ (p=none) です。なりすまし遮断のため p=quarantine 以上（★4は p=reject）へ移行してください。');
    } else if (dmarcPolicy === 'quarantine') {
      warnings.push('DMARCは p=quarantine です（★3充足、★4には p=reject を推奨）。');
    }

    const pctMatch = dmarc.match(/(?:^|[;\s])pct\s*=\s*(\d{1,3})\b/i);
    if (pctMatch) {
      pct = Number.parseInt(pctMatch[1], 10);
      if (pct < 100) {
        warnings.push(`DMARC適用割合が pct=${pct}% です。全面適用には pct=100 にしてください。`);
      }
    }
    ruaConfigured = /(?:^|[;\s])rua\s*=\s*mailto:/i.test(dmarc);
    if (!ruaConfigured) {
      warnings.push('DMARC集計レポート受信先 (rua=mailto:...) の設定を推奨します。');
    }
  }

  let score = 0;
  if (spfValid) {
    score += 20;
    if (spfQualifier === '-all') score += 20;
    else if (spfQualifier === '~all') score += 12;
    else if (spfQualifier === '?all') score += 4;
    if (spfLookups <= 10) score += 10;
  }
  if (dmarcValid) {
    score += 20;
    if (dmarcPolicy === 'reject') score += 20;
    else if (dmarcPolicy === 'quarantine') score += 14;
    else if (dmarcPolicy === 'none') score += 4;
    if (pct < 100 && dmarcPolicy !== 'none' && dmarcPolicy !== 'missing') {
      score = Math.max(0, score - 5);
    }
    if (ruaConfigured) score += 10;
  }
  score = Math.min(100, Math.max(0, score));

  return {
    spfValid,
    spfQualifier,
    spfLookups,
    dmarcValid,
    dmarcPolicy,
    pct,
    ruaConfigured,
    score,
    warnings,
  };
}

export function auditSupplyChainSecurity(policyText = '', options = {}) {
  const normalized = String(policyText || '').replace(/\u3000/g, ' ').trim();
  const spfRecord = options.spfRecord ?? '';
  const dmarcRecord = options.dmarcRecord ?? '';

  const emailAuth = parseEmailAuthPosture(spfRecord, dmarcRecord);
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
        detail: negated ? `禁止・非推奨表記を検出（${pillar.detail}）` : pillar.detail,
        remediation: pillar.remediation,
      });
    }
  }

  // Pillar 8: Email Auth SPF + DMARC (10 pts max)
  const emailAuthPts = Math.round((emailAuth.score / 100) * 10);
  rawScore += emailAuthPts;

  if (emailAuth.spfValid && emailAuth.dmarcValid && (emailAuth.dmarcPolicy === 'reject' || emailAuth.dmarcPolicy === 'quarantine') && emailAuth.spfLookups <= 10) {
    passedPillars.push({
      id: 'email_auth_dmarc',
      title: 'メール送信ドメイン認証（SPF / DMARC）',
      criterion: 'METI ★3・★4 BECなりすまし防止',
      weight: emailAuthPts,
    });
  } else {
    findings.push({
      id: 'email_auth_dmarc',
      title: 'メール送信ドメイン認証（SPF / DMARC）不備',
      criterion: 'METI ★3・★4 BECなりすまし防止',
      severity: emailAuth.spfQualifier === '+all' || !emailAuth.dmarcValid ? 'HIGH' : 'MEDIUM',
      detail: emailAuth.warnings.join(' ') || 'SPFまたはDMARCポリシーが未達です。',
      remediation: 'SPFを -all（10ルックアップ以下）とし、DMARCを v=DMARC1; p=reject; rua=mailto:... に設定してください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore));

  let starRating = '★3未満（要是正）';
  let status = 'fail';
  if (score >= 88 && emailAuth.dmarcPolicy === 'reject' && emailAuth.spfValid && emailAuth.spfLookups <= 10) {
    starRating = '★4相当';
    status = 'pass';
  } else if (score >= 70) {
    starRating = '★3相当';
    status = 'warn';
  }

  const passedCount = passedPillars.length;
  return {
    score,
    starRating,
    status,
    emailAuth,
    passedPillars,
    findings,
    passedCount,
    totalPillars: PILLARS.length + 1,
    emailAuthSummary: `SPF:${emailAuth.spfQualifier} (${emailAuth.spfLookups}/10 lookups) / DMARC:p=${emailAuth.dmarcPolicy}`,
  };
}

export function generateVendorSecurityResponseMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const contact = String(meta.contactEmail || 'security@example.jp').trim() || 'security@example.jp';
  const spf = String(meta.spfRecord || '（未記載）').trim() || '（未記載）';
  const dmarc = String(meta.dmarcRecord || '（未記載）').trim() || '（未記載）';
  const today = new Date().toISOString().slice(0, 10);

  const lines = [
    '# 取引先提出用 情報セキュリティ対策状況回答書（METI ★3・★4 / PPC漏えい報告 / 営業秘密管理準拠）',
    '',
    `- **作成日**: ${today}`,
    `- **回答組織名**: ${org}`,
    `- **セキュリティ連絡窓口（CSIRT）**: ${contact}`,
    `- **自己評価目安（METI基準）**: **${auditResult.starRating}**（スコア: \`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    `- **メール送信認証設定**: \`${auditResult.emailAuthSummary}\``,
    `  - SPF: \`${spf}\``,
    `  - DMARC: \`${dmarc}\``,
    '',
    '## 1. 基準項目別の適合状況',
    '',
    '| 領域 | 評価 | 準拠根拠 / 要是正事項 |',
    '|---|---|---|',
  ];

  for (const p of auditResult.passedPillars) {
    lines.push(`| ${p.title} | 適合（充足） | ${p.criterion} |`);
  }
  for (const f of auditResult.findings) {
    lines.push(`| ${f.title} | 要是正 (${f.severity}) | ${f.detail} ／ 是正計画: ${f.remediation} |`);
  }

  lines.push(
    '',
    '## 2. インシデント・個人情報漏えい時の報告体制（改正APPI第26条準拠）',
    '',
    '- 個人情報保護委員会（PPC）への **速報（認識後概ね3〜5日以内）** および **確報（30日以内／不正の目的によるおそれがある場合は60日以内）** に向けた社内エスカレーション手順を整備しています。',
    '- 取引先の営業秘密・機密データへの影響が疑われる場合は、一次連絡窓口より速やかに初報を共有します。',
    '',
    '---',
    '*本回答書は BOUHEKIGATE（防壁門）により外部サーバーへ機密文章・チェックシートを一切送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
