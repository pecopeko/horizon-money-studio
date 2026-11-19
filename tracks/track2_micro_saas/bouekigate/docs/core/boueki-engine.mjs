/**
 * BOUEKIGATE（貿易門）Core Engine
 * 外為法第25条・輸出令別表第1（1〜15項リスト規制 / 16項キャッチオール規制 / みなし輸出特定類型①〜③）/
 * 経産省外国ユーザーリスト / 米国EAR（De Minimis 25%/0%・ECCN 5D002 TSU公開免除）
 * ローカル診断エンジン（外部通信ゼロ）
 */

const PILLARS = [
  {
    id: 'list_control_1_15',
    title: '外為法・輸出令別表第1（1〜15項）リスト規制該非判定',
    criterion: '輸出令別表第1 / 外為令別表 1〜15項パラメータシート',
    weight: 15,
    severity: 'HIGH',
    pattern: /(?:輸出令別表第?1|外為令|リスト規制|1[〜~\-]15項|パラメータシート|該非判定)/i,
    antiPattern: /(?:該非判定不要|リスト規制対象外とみなす|パラメータシート省略)/i,
    detail: '輸出令別表第1・外為令別表（1〜15項）の仕様マトリクスに基づくリスト規制該非判定・パラメータシート確認手順が不足しています。',
    remediation: '貨物・プログラム・技術ごとに1〜15項パラメータシートで項番該当有無（非該当/該当）を一次判定・記録してください。',
  },
  {
    id: 'catchall_16_wmd',
    title: '16項キャッチオール規制（WMD・通常兵器用途 / インフォーム・客観要件）',
    criterion: '輸出令別表第1の16項（大量破壊兵器・通常兵器補完輸出規制）',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:16項|キャッチオール|大量破壊兵器|wmd|通常兵器|インフォーム要件|客観要件|用途確認)/i,
    antiPattern: /(?:キャッチオール不要|用途確認なし|16項省略)/i,
    detail: 'リスト規制非該当品目に対する16項キャッチオール規制（大量破壊兵器等開発用途の客観要件・経産大臣インフォーム要件確認）が未記載です。',
    remediation: 'ホワイト国（グループA）以外の仕向地について最終用途確認書（EUC）等で大量破壊兵器・通常兵器用途でないことを審査してください。',
  },
  {
    id: 'meti_foreign_user_list',
    title: '経産省『外国ユーザーリスト』・OFAC SDN等懸念需要者照合',
    criterion: '需要者要件（経産省外国ユーザーリスト / 米国EL・SDNリスト）',
    weight: 13,
    severity: 'HIGH',
    pattern: /(?:外国ユーザーリスト|ofac|sdn|エンティティリスト|需要者要件|制裁リスト|懸念需要者)/i,
    antiPattern: /(?:制裁リスト照合なし|外国ユーザーリスト未確認)/i,
    detail: '経済産業省「外国ユーザーリスト」や米国BIS Entity List・OFAC SDNリストとの取引先・最終需要者・仲介者スクリーニングが漏れています。',
    remediation: '契約前・出荷前に外国ユーザーリストおよび米国/EU主要制裁リストと相手先・最終需要者を照合し証跡保存してください。',
  },
  {
    id: 'deemed_export_cat_1_3',
    title: '外為法第25条『みなし輸出』特定類型①②③該当性確認・誓約書',
    criterion: '外国為替及び外国貿易法第25条第1項（2022年5月施行特定類型）',
    weight: 14,
    severity: 'HIGH',
    pattern: /(?:みなし輸出|特定類型|外為法25条|外為法第25条|類型[123①②③]|居住者判定|誓約書)/i,
    antiPattern: /(?:特定類型確認不要|みなし輸出対象外|誓約書不要)/i,
    detail: '国内居住者（役職員・研究者・共同開発先等）への機微技術提供時に必要な「みなし輸出管理（特定類型①②③該当性チェック＆誓約書）」が見当たりません。',
    remediation: '採用・プロジェクト参画時に特定類型①（外国政府等の強い影響下）・②・③該当有無の確認および自己申告誓約書を取得してください。',
  },
  {
    id: 'ear_reexport_deminimis',
    title: '米国EAR再輸出規制（ECCN・米国原産比率 De Minimis・FDPR）',
    criterion: '15 CFR Part 734（ECCN / 25%・懸念国0% / 外国直接製品ルール）',
    weight: 12,
    severity: 'HIGH',
    pattern: /(?:ear|eccn|de\s*minimis|デミニミス|再輸出規制|米国原産|fdpr|direct\s*product)/i,
    antiPattern: /(?:ear適用外と断定|再輸出確認不要)/i,
    detail: '米国製部品・ソフトウェア・開発ツール組込み時の米国輸出管理規則（EAR ECCN判定・25%/0% De Minimis計算・FDPR）評価が不足しています。',
    remediation: '米国原産規制品目のECCNと組込原価比率（懸念国E:1/D:5等向けは0%以上・一般国25%超でEAR対象）およびFDPRを確認してください。',
  },
  {
    id: 'encryption_9_5d002',
    title: '暗号規制（外為令9項 市販暗号特例・米国EAR ECCN 5D002 / TSU公開免除）',
    criterion: '輸出令別表第1の9項 市販暗号特例 & EAR 742.15(b) TSU',
    weight: 10,
    severity: 'MEDIUM',
    pattern: /(?:9項|暗号特例|市販暗号|5d002|tsu|742\.15|公開暗号|oss暗号)/i,
    antiPattern: /(?:暗号機能確認なし|5d002届出省略)/i,
    detail: '暗号機能を含む製品・SaaS・OSS公開時の9項暗号特例要件（市販暗号該当性・鍵長制限）およびEAR 5D002 TSU/ENC要件の確認が不明確です。',
    remediation: 'HTTPS/AES等の暗号機能が市販暗号特例や一般公開OSS（EAR TSU 742.15(b)通知）に該当するか確認・記録してください。',
  },
  {
    id: 'cp_dual_approval',
    title: '安全保障貿易管理内部規程（CP）・最終統括審査＆出荷差止権限',
    criterion: '輸出管理内部規程（CP）組織体制・ダブルチェック原則',
    weight: 11,
    severity: 'MEDIUM',
    pattern: /(?:安全保障貿易管理規程|内部規程|cp|輸出管理統括責任者|最高責任者|審査部門|出荷差止)/i,
    antiPattern: /(?:自己承認のみ|審査部門なし|出荷停止権限なし)/i,
    detail: '営業部門から独立した輸出管理統括責任者・審査部門によるダブルチェック承認および不審取引時の出荷差止権限規定が欠落しています。',
    remediation: '営業担当による自己判断を禁じ、安全保障貿易管理規程（CP）に基づき最高責任者・管理部門が出荷停止・最終承認を行う体制を規定化してください。',
  },
  {
    id: 'record_7yr_retention',
    title: '該非判定書・特定類型誓約書・取引関連帳簿の7年間保存',
    criterion: '外為法関連省令（規制品目7年・その他法定保存・監査証跡）',
    weight: 11,
    severity: 'HIGH',
    pattern: /(?:7年|７年|七年|保存期間|帳簿保存|判定書保管)/i,
    antiPattern: /(?:判定記録保存なし|保存期間1年|帳簿廃棄)/i,
    detail: '該非判定書（パラメータシート）・取引審査記録・特定類型誓約書の7年間（法定保存期間）保管および立入検査対応体制が明記されていません。',
    remediation: '輸出・技術提供ごとに判定根拠資料・EUC・特定類型確認書を案件単位で紐づけ、少なくとも7年間検索可能に保管する規程を設けてください。',
  },
];

export function evaluateEarDeMinimis({
  usOriginValueJpy = 0,
  totalProductValueJpy = 0,
  destinationGroup = 'general',
  isPublicOssEncryption = false,
} = {}) {
  const usVal = Math.max(0, Number(usOriginValueJpy) || 0);
  const totalVal = Math.max(0, Number(totalProductValueJpy) || 0);
  const group = String(destinationGroup || 'general').trim() || 'general';
  const publicOss = Boolean(isPublicOssEncryption);

  const usRatioPct = totalVal > 0 ? Math.round((usVal / totalVal) * 10000) / 100 : 0;
  const thresholdPct = group === 'embargo_e1_d5' ? 0 : 25;

  let subjectToEar = false;
  let basis = 'below_de_minimis_25';
  if (publicOss) {
    subjectToEar = false;
    basis = 'tsu_742_15b_exempt';
  } else if (totalVal > 0 && group === 'embargo_e1_d5') {
    if (usVal > 0) {
      subjectToEar = true;
      basis = 'embargo_zero_de_minimis';
    } else {
      subjectToEar = false;
      basis = 'below_de_minimis_25';
    }
  } else if (totalVal > 0 && usRatioPct > 25) {
    subjectToEar = true;
    basis = 'ear_over_25_pct';
  }

  return {
    usOriginValueJpy: usVal,
    totalProductValueJpy: totalVal,
    usRatioPct,
    thresholdPct,
    destinationGroup: group,
    isPublicOssEncryption: publicOss,
    subjectToEar,
    basis,
  };
}

export function auditExportControlPolicy(policyText = '', options = {}) {
  const normalized = String(policyText || '').replace(/\u3000/g, ' ').trim();
  const earResult = evaluateEarDeMinimis(options);
  const hasEarLicenseOrException = Boolean(options.hasEarLicenseOrException);

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
  if (earResult.subjectToEar && !hasEarLicenseOrException) {
    penalty = 15;
    findings.push({
      id: 'ear_license_missing',
      title: '米国EAR De Minimis超過にもかかわらずEAR許可・ライセンス例外未確認',
      criterion: `15 CFR Part 734 (${earResult.basis} / 米国原産比率 ${earResult.usRatioPct}% / 閾値 ${earResult.thresholdPct}%)`,
      severity: 'HIGH',
      detail: `米国原産規制品目の比率が ${earResult.usRatioPct}%（仕向地区分 ${earResult.destinationGroup} の閾値 ${earResult.thresholdPct}%）によりEAR域外適用対象ですが、BIS輸出許可またはライセンス例外の保有が未確認です。`,
      remediation: 'BIS再輸出許可の取得、ライセンス例外（TSU/ENC等）該当性確認、または米国原産部材比率の引下げを実施してください。',
    });
  }

  const score = Math.min(100, Math.max(0, rawScore - penalty));
  let readinessLabel = '管理不備・輸出/技術提供差止必須';
  let status = 'fail';
  if (score >= 88 && findings.every((f) => f.severity !== 'HIGH')) {
    readinessLabel = '外為法・みなし輸出・米国EAR 基準充足';
    status = 'pass';
  } else if (score >= 65) {
    readinessLabel = '一部補完推奨（要法務/統括審査）';
    status = 'warn';
  }

  return {
    score,
    status,
    readinessLabel,
    earResult,
    passedPillars,
    findings,
    passedCount: passedPillars.length,
    totalPillars: PILLARS.length,
  };
}

export function generateGaihiCertificateMarkdown(auditResult, meta = {}) {
  const org = String(meta.organizationName || '貴社（未設定）').trim() || '貴社（未設定）';
  const product = String(meta.productName || '対象製品・技術（未設定）').trim() || '対象製品・技術（未設定）';
  const today = new Date().toISOString().slice(0, 10);
  const ear = auditResult.earResult;

  const lines = [
    '# 安全保障貿易管理 該非判定書（パラメータシート要約）兼 みなし輸出特定類型確認書',
    '',
    `- **作成日**: ${today}`,
    `- **判定実施法人名**: ${org}`,
    `- **対象貨物 / プログラム / 技術名称**: ${product}`,
    `- **貿易管理統制スコア**: **${auditResult.readinessLabel}**（\`${auditResult.score}/100\` / 充足 \`${auditResult.passedCount}/${auditResult.totalPillars}\`）`,
    '',
    '## 1. 米国EAR（15 CFR Part 734 De Minimis）再輸出判定結果',
    '',
    `- **対象品目総額**: \`${ear.totalProductValueJpy.toLocaleString('en-US')} JPY\` / **組込米国原産規制分**: \`${ear.usOriginValueJpy.toLocaleString('en-US')} JPY\``,
    `- **米国原産比率 / 仕向地閾値**: \`${ear.usRatioPct}%\` / \`${ear.thresholdPct}%\`（仕向地区分: \`${ear.destinationGroup}\`）`,
    `- **公開OSS暗号 (TSU 742.15(b)) 免除**: \`${ear.isPublicOssEncryption ? '該当' : '非該当'}\``,
    `- **米国EAR 域外適用判定**: \`${ear.subjectToEar ? 'EAR対象（要許可・例外確認）' : '対象外 / 免除'}\`（根拠: \`${ear.basis}\`）`,
    '',
    '## 2. 安全保障貿易管理 8大統制項目の適合・是正状況',
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
    '## 3. 外為法第25条『みなし輸出』特定類型①②③ 確認記録テンプレート',
    '',
    '- [ ] **類型①**: 外国政府等と雇用・委任・請負関係にあるか（該当 / 非該当）',
    '- [ ] **類型②**: 外国政府等から多額の金銭その他の重大な利益を受けているか（該当 / 非該当）',
    '- [ ] **類型③**: 日本国内において外国政府等の指示・依頼に基づき行動するか（該当 / 非該当）',
    '',
    '---',
    '*本判定書は BOUEKIGATE（貿易門）により製品原価・技術情報を社外サーバーへ一切送信せずブラウザローカルで生成されました（ネットワーク通信: `0`回）。*'
  );

  return lines.join('\n');
}
