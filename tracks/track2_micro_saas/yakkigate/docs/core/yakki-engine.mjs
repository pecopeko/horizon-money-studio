/**
 * YAKKIGATE (薬影) - 100% Browser-Local Japanese Ad-Copy Compliance Engine
 * Checks Japanese LP / EC / SNS marketing copy against:
 *   1. Yakki-ho (薬機法: unapproved medical / disease-cure / efficacy claims)
 *   2. Keihyo-ho (景品表示法: unsubstantiated No.1 / superlatives / deceptive dual-pricing)
 *   3. Stealth Marketing Regulation (ステマ規制: undisclosed PR / sponsored content)
 * Supports offline fusion with Colab-distilled `yakki-ad-guard-ja` Transformers.js logits.
 * Zero network calls; zero external runtime dependencies.
 */

export const YAKKI_CATEGORIES = Object.freeze([
  "compliant",
  "yakki_medical_claim",
  "keihyo_exaggerated_no1",
  "stealth_marketing_unlabeled",
]);

const MEDICAL_CLAIM_RULES = [
  {
    id: "YAKKI-MED-01",
    ruleName: "疾患の治療・予防・根治表現（薬機法第66条・第68条リスク）",
    severity: 42,
    regex:
      /(?:糖尿病|がん|癌|高血圧|動脈硬化|認知症|うつ病|アトピー|喘息|花粉症|白髪|薄毛|シミ|シワ|ニキビ|痔|関節痛)(?:が|を|に)?(?:完全に|確実に|みるみる|すぐ|100%|一生)?(?:治[るり]|完治|根治|治癒|消え(?:る|ます)?|消滅|改善|予防(?:できる|に|効果)?|撃退)|(?:がん|癌|生活習慣病|認知症)(?:の)?予防/g,
    suggestion:
      "疾患名や症状の「治療・予防・完治・消滅」は医薬品的な効能効果にあたるため削除し、「健康維持のサポート」「保湿により乾燥を防ぐ」等の一般食品・化粧品の範囲に言い換えてください。",
    rationale: "未承認の疾病治療・予防効果の標榜は薬機法上最も重大な違反リスクです。",
  },
  {
    id: "YAKKI-MED-02",
    ruleName: "身体組織の増強・脂肪溶解・細胞若返り表現（薬機法第66条）",
    severity: 36,
    regex:
      /(?:内臓脂肪|皮下脂肪|脂肪)が(?:確実に|どんどん|勝手に)?溶け(?:る|て)|(?:細胞レベルで|DNAレベルで|遺伝子レベルで)若返(?:る|り)|飲むだけで(?:痩せる|減量|血圧が下がる|血糖値が下がる)|バスト(?:が|を)?(?:大きく|成長|増大)させ|発毛効果(?:が|を)保証/g,
    suggestion:
      "「栄養補給として」「適度な運動と併用して」「ハリを与える」等、身体構造の直接変化を断定しない表現へ修正してください。",
    rationale: "身体の組織機能に薬理的・生理的変化をもたらす表現は化粧品・健康食品では認められません。",
  },
  {
    id: "YAKKI-MED-03",
    ruleName: "副作用なし・医師等の効能保証（薬機法第66条第2項・第1項）",
    severity: 32,
    regex:
      /(?:副作用(?:は|が)?(?:一切|ゼロ|なし|全くない)|医師(?:が|も)(?:治療効果|臨床効果)を(?:保証|推薦|実証)|厚生労働省(?:認可|公認)の(?:若返り|痩身|治療))/g,
    suggestion:
      "「副作用ゼロ」等の安全性保証や、医師・公的機関による効能効果保証表現は削除してください。",
    rationale: "安全性・効能の絶対保証や医薬関係者による推薦標榜は誇大広告として禁止されています。",
  },
];

const KEIHYO_RULES = [
  {
    id: "KEIHYO-NO1-01",
    ruleName: "根拠記載なきNo.1・日本一・最高峰表示（景品表示法・優良誤認）",
    severity: 30,
    regex:
      /(?:業界|顧客満足度|リピート率|医師推奨|SNS話題|口コミ|売上)?(?:No\.?\s*1|Ｎｏ\.?\s*１|ナンバーワン|第?1位|日本一|世界一|業界最高峰|唯一無二|圧倒的No\.?\s*1)/gi,
    requiresContextMissing: /(?:調査機関|調査概要|調査期間|調査方法|アンケート概要|自社調べ\s*\(|n\s*=\s*\d+)/i,
    suggestion:
      "第三者機関による客観的調査（調査機関・調査時期・対象母数）の正確な注記を直近に明記するか、No.1表現を削除してください。",
    rationale: "合理的な根拠資料と表示近接注記のないNo.1表示は優良誤認表示の典型です。",
  },
  {
    id: "KEIHYO-ABS-02",
    ruleName: "効果・満足度の絶対断定（優良誤認リスク）",
    severity: 28,
    regex: /(?:100%\s*(?:満足|効果|実感|返金不要)|誰でも必ず|絶対に失敗しない|飲めば必ず|永久に効果が続く)/g,
    suggestion:
      "「100%」「必ず」「絶対」といった断定表現を避け、事実に基づく客観説明と「個人の感想であり効能を保証するものではありません」等の適切な説明（打消し表示の視認性確保）に改稿してください。",
    rationale: "合理的な根拠なく効果・品質を100%断定する表現は景品表示法上の問題となります。",
  },
  {
    id: "KEIHYO-PRICE-03",
    ruleName: "二重価格・永久限定セールの有利誤認表現（景品表示法）",
    severity: 30,
    regex:
      /(?:通常[\s\d,]+円が(?:今だけ|ずっと|永久)(?:半額|500円|無料|0円)|本日限定[\s\S]{0,15}毎日開催|根拠調査なし)/g,
    suggestion:
      "二重価格表示を使う場合は最近相当期間の販売実績がある価格のみを「当店通常価格」等として提示し、常時行っている割引に「今だけ」と記載しないでください。",
    rationale: "架空の通常価格や終了期限を偽る期間限定表示は有利誤認に該当します。",
  },
];

const STEMA_CONTEXT_RE =
  /(?:企業(?:様|から)(?:商品|製品)?(?:を)?ご提供|提供いただきました|ギフティング|モニター(?:として|体験|企画)|アンバサダー(?:活動)?|タイアップ|有償レビュー|報酬を受け取|PR案件|ご招待いただきました|ステマ|ステルス)/g;

const STEMA_EXPLICIT_HIDE_RE =
  /(?:PRであることを伏せて|広告表記なし|自腹購入(?:と|として)投稿|宣伝とバレないよう)/g;

const PR_DISCLOSURE_MARKER_RE =
  /(?:^|[\s\n【\[#(])(?:PR|広告|プロモーション|提供|Sponsored|Ad)(?:[\s\]】:#]|$|を含む)/im;

function matchAllRules(text, rules, category, law) {
  const findings = [];
  for (const rule of rules) {
    const flags = rule.regex.flags.includes("g") ? rule.regex.flags : `${rule.regex.flags}g`;
    const re = new RegExp(rule.regex.source, flags);
    let m;
    while ((m = re.exec(text)) !== null) {
      if (rule.requiresContextMissing && rule.requiresContextMissing.test(text)) {
        continue;
      }
      findings.push({
        id: rule.id,
        category,
        law,
        ruleName: rule.ruleName,
        severity: rule.severity,
        matchedText: m[0],
        start: m.index,
        end: m.index + m[0].length,
        suggestion: rule.suggestion,
        rationale: rule.rationale,
      });
      if (m[0].length === 0) {
        re.lastIndex += 1;
      }
    }
  }
  return findings;
}

/**
 * Audit a single Japanese ad / LP / SNS copy string.
 * @param {string} rawText
 * @returns {object} Structured audit result with spans, severity, category, and rewrite hint.
 */
export function auditJapaneseAdCopy(rawText) {
  const text = String(rawText ?? "");
  if (!text.trim()) {
    return {
      textLength: 0,
      overallRiskScore: 0,
      riskLevel: "LOW",
      predictedLabel: "compliant",
      findings: [],
      categoryCounts: {
        yakki_medical_claim: 0,
        keihyo_exaggerated_no1: 0,
        stealth_marketing_unlabeled: 0,
      },
      hasPrDisclosure: false,
      suggestedRewriteHint: "審査対象のテキストを入力してください。",
    };
  }

  const findings = [
    ...matchAllRules(text, MEDICAL_CLAIM_RULES, "yakki_medical_claim", "薬機法"),
    ...matchAllRules(text, KEIHYO_RULES, "keihyo_exaggerated_no1", "景品表示法"),
  ];

  const hasPrDisclosure = PR_DISCLOSURE_MARKER_RE.test(text);
  const explicitHideMatch = new RegExp(STEMA_EXPLICIT_HIDE_RE.source, "g");
  let hm;
  while ((hm = explicitHideMatch.exec(text)) !== null) {
    findings.push({
      id: "STEMA-HIDE-01",
      category: "stealth_marketing_unlabeled",
      law: "ステマ規制（景品表示法）",
      ruleName: "事業者関与の隠蔽・虚偽自腹表現",
      severity: 55,
      matchedText: hm[0],
      start: hm.index,
      end: hm.index + hm[0].length,
      suggestion: "冒頭に分かりやすく「PR」「広告」「プロモーション」表記を明示してください。",
      rationale: "事業者の広告であることを隠す投稿は景品表示法のステマ告示違反となります。",
    });
  }

  if (!hasPrDisclosure) {
    const stemaRe = new RegExp(STEMA_CONTEXT_RE.source, "g");
    let sm;
    while ((sm = stemaRe.exec(text)) !== null) {
      findings.push({
        id: "STEMA-PR-02",
        category: "stealth_marketing_unlabeled",
        law: "ステマ規制（景品表示法）",
        ruleName: "商品提供・報酬・モニター投稿における明瞭なPR表記欠落",
        severity: 38,
        matchedText: sm[0],
        start: sm.index,
        end: sm.index + sm[0].length,
        suggestion:
          "本文冒頭または視認性の高い位置に「#PR」「【広告】」「プロモーション」等を明記してください（文末の小さい注記のみは不可）。",
        rationale: "対価や無償提供を受けた表示には事業者の関与を明瞭に表示する義務があります。",
      });
    }
  }

  findings.sort((a, b) => a.start - b.start || b.severity - a.severity);

  const categoryCounts = {
    yakki_medical_claim: 0,
    keihyo_exaggerated_no1: 0,
    stealth_marketing_unlabeled: 0,
  };
  const categoryScore = {
    yakki_medical_claim: 0,
    keihyo_exaggerated_no1: 0,
    stealth_marketing_unlabeled: 0,
  };

  for (const f of findings) {
    categoryCounts[f.category] = (categoryCounts[f.category] || 0) + 1;
    categoryScore[f.category] = (categoryScore[f.category] || 0) + f.severity;
  }

  const rawTotal = findings.reduce((acc, item) => acc + item.severity, 0);
  const overallRiskScore = Math.min(100, rawTotal);

  let riskLevel = "LOW";
  if (overallRiskScore >= 70) riskLevel = "CRITICAL";
  else if (overallRiskScore >= 40) riskLevel = "HIGH";
  else if (overallRiskScore >= 20) riskLevel = "MEDIUM";

  let predictedLabel = "compliant";
  if (findings.length > 0) {
    let topCat = "yakki_medical_claim";
    let topVal = -1;
    for (const cat of Object.keys(categoryScore)) {
      if (categoryScore[cat] > topVal) {
        topVal = categoryScore[cat];
        topCat = cat;
      }
    }
    predictedLabel = topCat;
  }

  const suggestedRewriteHint =
    findings.length === 0
      ? "主要な薬機法・景表法・ステマ規制のNGパターンは検出されませんでした（最終出稿時は媒体審査基準と根拠資料の保管を確認してください）。"
      : [...new Set(findings.map((f) => f.suggestion))].join(" / ");

  return {
    textLength: text.length,
    overallRiskScore,
    riskLevel,
    predictedLabel,
    findings,
    categoryCounts,
    hasPrDisclosure,
    suggestedRewriteHint,
  };
}

/**
 * Audit multiple ad copy records locally in batch mode.
 * @param {Array<string|{id?: string, label?: string, text: string}>} items
 */
export function batchAuditAdCopy(items) {
  const list = Array.isArray(items) ? items : [];
  const results = [];
  const summaryByLabel = {
    compliant: 0,
    yakki_medical_claim: 0,
    keihyo_exaggerated_no1: 0,
    stealth_marketing_unlabeled: 0,
  };

  let flaggedCount = 0;
  for (let i = 0; i < list.length; i += 1) {
    const entry = list[i];
    const text = typeof entry === "string" ? entry : String(entry?.text ?? "");
    const id = typeof entry === "object" && entry?.id ? String(entry.id) : `ROW-${i + 1}`;
    const audit = auditJapaneseAdCopy(text);
    if (audit.findings.length > 0) flaggedCount += 1;
    summaryByLabel[audit.predictedLabel] = (summaryByLabel[audit.predictedLabel] || 0) + 1;
    results.push({ id, preview: text.slice(0, 80), ...audit });
  }

  return {
    totalRows: results.length,
    flaggedRows: flaggedCount,
    compliantRows: results.length - flaggedCount,
    summaryByLabel,
    results,
  };
}

/**
 * Generate a downloadable Markdown compliance audit certificate without sending data externally.
 */
export function buildAuditCertificateMarkdown(audit, meta = {}) {
  const checkedAt = meta.checkedAt || new Date().toISOString();
  const lines = [
    "# YAKKIGATE（薬影）広告・LP表現 ローカル事前審査レポート",
    "",
    `- 監査日時: \`${checkedAt}\``,
    "- 実行環境: 100% ブラウザローカル完結（社外サーバ送信・API通信ゼロ）",
    `- 総合リスクスコア: **${audit.overallRiskScore} / 100** (${audit.riskLevel})`,
    `- 判定ラベル: \`${audit.predictedLabel}\``,
    `- 検出件数: ${audit.findings.length} 件`,
    "",
    "## 検出箇所と是正提案",
    "",
  ];

  if (audit.findings.length === 0) {
    lines.push("- 指摘事項なし（主要な禁止表現・ステマ表記欠落は検出されませんでした）。");
  } else {
    for (const f of audit.findings) {
      lines.push(
        `- **[${f.id} / ${f.law}]** \`${f.matchedText}\` (位置 ${f.start}..${f.end}, 重み +${f.severity})`,
      );
      lines.push(`  - 理由: ${f.rationale}`);
      lines.push(`  - 修正案: ${f.suggestion}`);
    }
  }
  lines.push("");
  return lines.join("\n");
}

/**
 * Fuse deterministic rule audit risk with Colab-distilled `yakki-ad-guard-ja` ONNX softmax logits.
 */
export function fuseWithDistilledYakkiModel({
  ruleAudit,
  neuralProbs = [],
  labels = YAKKI_CATEGORIES,
  neuralWeight = 0.65,
} = {}) {
  const ruleRisk = Math.max(0, Math.min(1, (Number(ruleAudit?.overallRiskScore) || 0) / 100));
  if (!Array.isArray(neuralProbs) || neuralProbs.length === 0) {
    return {
      combinedRisk: Number(ruleRisk.toFixed(4)),
      predictedLabel: ruleAudit?.predictedLabel || "compliant",
      neuralRisk: 0,
    };
  }

  let bestIdx = 0;
  for (let i = 1; i < neuralProbs.length; i += 1) {
    if (neuralProbs[i] > neuralProbs[bestIdx]) bestIdx = i;
  }
  const safeIdx = labels.indexOf("compliant");
  const neuralRisk =
    safeIdx >= 0
      ? Math.max(0, Math.min(1, 1 - Number(neuralProbs[safeIdx] || 0)))
      : Math.max(0, Math.min(1, 1 - Number(neuralProbs[0] || 0)));

  const combined = Math.max(ruleRisk, (1 - neuralWeight) * ruleRisk + neuralWeight * neuralRisk);
  return {
    combinedRisk: Number(Math.min(1, combined).toFixed(4)),
    predictedLabel:
      ruleRisk >= 0.4 && ruleAudit?.predictedLabel !== "compliant"
        ? ruleAudit.predictedLabel
        : (labels[bestIdx] ?? "compliant"),
    neuralRisk: Number(neuralRisk.toFixed(4)),
  };
}
