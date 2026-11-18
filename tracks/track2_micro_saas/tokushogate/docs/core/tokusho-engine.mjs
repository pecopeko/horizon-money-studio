const MANDATORY_DISCLOSURES = [
  {
    key: "seller",
    label: "販売事業者（法人名・屋号等）",
    law: "特定商取引法第11条第1項",
    patterns: [/(?:販売業者|事業者名|提供元|運営会社)/],
    suggestion: "販売業者：株式会社○○（または個人事業主名）",
  },
  {
    key: "representative",
    label: "運営統括責任者（代表者氏名）",
    law: "特定商取引法第11条第1項",
    patterns: [/(?:運営統括責任者|代表者|運営責任者)/],
    suggestion: "運営統括責任者：代表取締役 ○○ ○○",
  },
  {
    key: "address",
    label: "所在地（または請求時遅滞なく開示文言）",
    law: "特定商取引法第11条第1項・通達",
    patterns: [/(?:所在地|住所|本店)/, /請求があった(?:ら|場合)[^。\n]{0,16}(?:遅滞なく|速やかに)(?:開示|提供)/],
    suggestion: "所在地：〒○○○-○○○○ 東京都○○区…（個人事業主の省略時は「請求があったら遅滞なく開示いたします」＋開示請求先を記載）",
  },
  {
    key: "phone",
    label: "電話番号（または請求時遅滞なく開示＋即時対応手段）",
    law: "特定商取引法第11条第1項",
    patterns: [/(?:電話番号|連絡先TEL|TEL)/i, /請求があった(?:ら|場合)[^。\n]{0,16}(?:遅滞なく|速やかに)(?:開示|提供)/],
    suggestion: "電話番号：03-XXXX-XXXX（受付時間 平日10:00〜17:00）",
  },
  {
    key: "email",
    label: "メールアドレス・問合せ窓口",
    law: "特定商取引法第11条第1項",
    patterns: [/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, /(?:メールアドレス|お問い合わせフォーム|support@)/],
    suggestion: "メールアドレス：support@example.co.jp",
  },
  {
    key: "price",
    label: "販売価格（消費税込表記）",
    law: "特定商取引法第11条第1号・消費税法第63条",
    patterns: [/(?:販売価格|利用料金|月額|年額|各プラン)/],
    suggestion: "販売価格：各商品・料金ページに表示された金額（消費税10%込）",
  },
  {
    key: "extraFees",
    label: "商品代金以外の必要料金（送料・振込手数料・通信料等）",
    law: "特定商取引法第11条第2号",
    patterns: [/(?:商品代金以外の必要料金|送料|振込手数料|インターネット接続料金|通信料)/],
    suggestion: "商品代金以外の必要料金：インターネット接続にかかる通信料・銀行振込手数料はお客様負担",
  },
  {
    key: "paymentMethodAndTiming",
    label: "代金の支払方法および支払時期",
    law: "特定商取引法第11条第3号",
    patterns: [/(?:支払方法|決済方法)/, /(?:支払時期|課金時期|決済確定|請求日)/],
    checkBothPatterns: true,
    suggestion: "支払方法：クレジットカード（Stripe決済）／支払時期：初回申込時即時課金、以降毎月契約応当日に自動決済",
  },
  {
    key: "deliveryTiming",
    label: "商品の引渡時期・役務の提供時期",
    law: "特定商取引法第11条第4号",
    patterns: [/(?:引渡時期|引き渡し時期|提供時期|利用開始)/],
    suggestion: "引渡・提供時期：決済完了後直ちに（ダウンロードリンク送付またはアカウント有効化）",
  },
  {
    key: "cancellationReturn",
    label: "返品・交換・解約・中途解約条件",
    law: "特定商取引法第11条第5号・第6号",
    patterns: [/(?:返品|キャンセル|解約|中途解約)/],
    suggestion: "返品・解約：デジタルコンテンツの特性上、決済後の返金には原則応じられません。ただし表示仕様と著しく異なる瑕疵がある場合は全額返金します。定期課金は次回更新日の前日までに管理画面よりいつでも解約可能です。",
  },
];

const OPERATING_ENV_PATTERNS = [/(?:動作環境|推奨環境|対応ブラウザ|OS)/];

const DARK_PATTERN_RULES = [
  {
    ruleId: "SUB-TEASER-TRAP",
    severity: "high",
    severityLabel: "高",
    weight: 30,
    law: "特定商取引法第12条の6（最終確認画面の表示義務：定期購入2回目以降・総額）",
    title: "初回割引（お試し価格）に対する2回目以降料金・総額・契約期間の説明不足",
    teaserRe: /(?:初回\s*(?:無料|0円|[0-9,]+円)|初月\s*(?:無料|半額|[0-9,]+円)|お試し価格)/,
    requireAllRe: [
      /(?:2回目以降|翌月以降|通常価格|更新後)/,
      /(?:支払総額|合計|最低利用期間|契約期間の定めなし|いつでも解約)/,
    ],
    explanation:
      "定期購入で「初回○円」「初月無料」を訴求する場合、最終確認画面および特商法表記で2回目以降の通常価格・課金周期・最低契約期間または縛りがない旨・支払総額目安を近接して明示しないと第12条の6違反（行政処分・取消対象）となります。",
    counterClause:
      "初回お試し価格○○円（税込）適用後、解約手続きがない限り自動更新となり、2回目以降は月額○,○○○円（税込）が毎月請求されます。最低契約回数の縛りはなく（12ヶ月総額目安○○,○○○円）、次回決済日の前日までにマイページから1クリックで解約できます。",
  },
  {
    ruleId: "SUB-CANCEL-OBSTRUCTION",
    severity: "high",
    severityLabel: "高",
    weight: 28,
    law: "特定商取引法第12条の6第2項・消費者契約法（解約方法の容易性）",
    title: "電話限定・FAX限定・平日の極端な短時間指定による解約妨害リスク",
    directRe: /(?:解約(?:は|手続きは)電話(?:のみ|に限る)|電話以外の解約は不可|書面郵送のみ|平日の1[0-4]時[^\n]{0,12}電話)/,
    explanation:
      "Web上で完結する申込にもかかわらず解約手段を電話や郵送のみに限定し、つながりにくい窓口で実質的に解約を阻む設計は行政指導・カード会社加盟店審査否決の典型原因です。",
    counterClause:
      "解約はサービス内の「契約設定・請求」画面または登録メール宛の自動認証フォームから24時間いつでもオンライン完結で手続きできます。",
  },
  {
    ruleId: "NO-REFUND-ABSOLUTE",
    severity: "medium",
    severityLabel: "中",
    weight: 16,
    law: "特定商取引法第11条第5号・民法契約不適合責任・クレジットカード加盟店審査基準",
    title: "瑕疵・誤課金例外なしの「いかなる理由でも返金不可」表現",
    directRe: /(?:いかなる理由(?:であっても|を問わず)|理由の如何を問わず)(?:一切)?返金(?:いたしません|は不可|に応じかねます)/,
    guardRe: /(?:不良品|瑕疵|システム障害|当社責め|契約不適合)/,
    explanation:
      "決済事業者の加盟店審査および消費者法上、「いかなる理由でも一切返金不可」と断定し提供側の不具合・二重課金時の返金義務まで排除する表現は差し戻し対象になりやすいです。",
    counterClause:
      "デジタル役務およびダウンロード商品の性質上、お客様都合による決済完了後の返金には応じられません。ただし、システム重大障害や提供ファイル破損等の契約不適合が判明した場合は、事実確認のうえ速やかに返金または代替提供いたします。",
  },
];

export function auditTokushoAndCheckout({
  tokushoText = "",
  checkoutText = "",
  isDigitalOrSaas = true,
  isSubscription = true,
} = {}) {
  const tokusho = String(tokushoText || "").replace(/\r\n/g, "\n");
  const checkout = String(checkoutText || "").replace(/\r\n/g, "\n");
  const combined = `${tokusho}\n${checkout}`;

  const missingItems = [];
  const findings = [];

  for (const item of MANDATORY_DISCLOSURES) {
    const matched = item.checkBothPatterns
      ? item.patterns.every((re) => re.test(tokusho))
      : item.patterns.some((re) => re.test(tokusho));
    if (!matched) {
      missingItems.push({
        key: item.key,
        label: item.label,
        law: item.law,
        suggestion: item.suggestion,
      });
      findings.push({
        ruleId: `TOKUSHO-MISSING-${item.key.toUpperCase()}`,
        severity: "high",
        severityLabel: "高",
        weight: 10,
        law: item.law,
        title: `必須表示事項の欠落：${item.label}`,
        matched: "記載未検出",
        explanation: "特定商取引法第11条の通信販売必須記載項目（および決済代行会社の公開審査基準）に該当する記載が見つかりません。",
        counterClause: item.suggestion,
      });
    }
  }

  if (isDigitalOrSaas && !OPERATING_ENV_PATTERNS.some((re) => re.test(tokusho))) {
    missingItems.push({
      key: "operatingEnv",
      label: "動作環境（ソフトウェア・SaaS・デジタルコンテンツ）",
      law: "特定商取引法第11条・施行規則第8条",
      suggestion: "動作環境：Google Chrome / Safari / Edge 最新版（インターネット接続必須）",
    });
    findings.push({
      ruleId: "TOKUSHO-MISSING-ENV",
      severity: "medium",
      severityLabel: "中",
      weight: 8,
      law: "特定商取引法第11条・施行規則第8条第3号",
      title: "ソフトウェア・デジタル商品における動作環境（OS・ブラウザ等）の記載不足",
      matched: "動作環境未記載",
      explanation: "電子計算機を用いて利用するデジタル商品・SaaSでは、購入前に必要な動作環境の表示が義務付けられています。",
      counterClause: "動作環境：Google Chrome / Edge / Safari 最新安定版（macOS / Windows 対応）",
    });
  }

  for (const rule of DARK_PATTERN_RULES) {
    if (rule.ruleId === "SUB-TEASER-TRAP") {
      if ((isSubscription || rule.teaserRe.test(combined)) && rule.teaserRe.test(combined)) {
        const missingSub = !rule.requireAllRe.every((re) => re.test(combined));
        if (missingSub) {
          const hit = combined.match(rule.teaserRe);
          findings.push({
            ruleId: rule.ruleId,
            severity: rule.severity,
            severityLabel: rule.severityLabel,
            weight: rule.weight,
            law: rule.law,
            title: rule.title,
            matched: hit ? hit[0] : "初回割引表記",
            explanation: rule.explanation,
            counterClause: rule.counterClause,
          });
        }
      }
      continue;
    }

    if (rule.directRe) {
      if (rule.guardRe && rule.guardRe.test(combined)) {
        continue;
      }
      const m = combined.match(rule.directRe);
      if (m) {
        findings.push({
          ruleId: rule.ruleId,
          severity: rule.severity,
          severityLabel: rule.severityLabel,
          weight: rule.weight,
          law: rule.law,
          title: rule.title,
          matched: m[0],
          explanation: rule.explanation,
          counterClause: rule.counterClause,
        });
      }
    }
  }

  const penalty = findings.reduce((sum, item) => sum + item.weight, 0);
  const complianceScore = Math.max(0, 100 - penalty);
  const underwritingStatus =
    complianceScore >= 90 && missingItems.length === 0
      ? "審査通過水準・法定要件充足"
      : complianceScore >= 60
        ? "要追記・一部表現修正推奨"
        : "行政処分リスク・決済審査差し戻し懸念";

  return {
    complianceScore,
    underwritingStatus,
    missingCount: missingItems.length,
    findingsCount: findings.length,
    missingItems,
    findings,
  };
}

export function generateTokushoTemplate({
  seller = "株式会社サンプル",
  representative = "代表 太郎",
  address = "請求があったら遅滞なく開示いたします（開示請求先メール記載）",
  phone = "請求があったら遅滞なく開示いたします（お問い合わせはメールにて受付）",
  email = "support@example.com",
  price = "各サービス・商品ページに表示（消費税込）",
  extraFees = "インターネット接続に必要な通信料・銀行振込時の振込手数料",
  payment = "クレジットカード決済（注文確定時即時決済、定期プランは毎月契約応当日に自動決済）",
  delivery = "決済完了後直ちにアカウント有効化またはダウンロードリンクを発行",
  cancellation = "デジタルコンテンツの性質上お客様都合の返金不可（不具合時は全額返金）。定期課金は次回更新日前日まで管理画面からいつでも解約可能。",
  environment = "Chrome / Safari / Edge 最新版",
} = {}) {
  return [
    "# 特定商取引法に基づく表記",
    "",
    "| 項目 | 表示内容 |",
    "|---|---|",
    `| 販売業者 | ${seller} |`,
    `| 運営統括責任者 | ${representative} |`,
    `| 所在地 | ${address} |`,
    `| 電話番号 | ${phone} |`,
    `| メールアドレス | ${email} |`,
    `| 販売価格 | ${price} |`,
    `| 商品代金以外の必要料金 | ${extraFees} |`,
    `| 支払方法および支払時期 | ${payment} |`,
    `| 商品の引渡・提供時期 | ${delivery} |`,
    `| 返品・キャンセル・解約 | ${cancellation} |`,
    `| 動作環境 | ${environment} |`,
  ].join("\n");
}
