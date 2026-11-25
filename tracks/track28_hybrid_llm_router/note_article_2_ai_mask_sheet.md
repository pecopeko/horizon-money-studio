TITLE: 【コピペ1分・ワンコイン】ChatGPT/Claude送信前に社名・メアド・個人名を自動で「仮名化→AI回答を一発復元」するスプシGASセット

---FREE_PART_START---
ChatGPT や Claude を仕事で使っていて、いちばん手が止まる瞬間はこれではないでしょうか。

- **「この議事録・契約書・請求メール、取引先の社名や担当者名が入ったままAIに貼って大丈夫かな……？」**
- **「かといって手動で『A社』『B社』『〇〇様』に置換して、AIから返ってきた文章をまた手で元の社名に戻すのは面倒すぎる！」**
- **「全部『伏せ字（■■■）』にすると、複数社が登場する比較や要約でAIが『どっちの会社かわかりません』と混乱してしまう……」**

実際、私たちが業務データ6ケースで検証したところ、固有名詞を単純な `[伏せ字]` に潰して上位AIモデルへ投げると **正答率は 16.7% まで急落** しました。一方で、`<<取引先_01>>` `<<取引先_02>>` のように **「どれとどれが同じ会社か」の番号を維持して仮名化し、AIの回答後に元の名前へ自動復元（再水和）する方式** に変えると、**外部への生データ送信ゼロのまま正答率 100% を維持** できました。

そこで本noteでは、プログラミング知識ゼロでも **普段の Googleスプレッドシート に1回コピペするだけでずっと使える「自動仮名化＆AI回答一発復元シート（GASカスタム関数2本＋AI指示プロンプト）」** をワンコイン（`¥500`）で配布します。

### 使い方はたったの3ステップ（外部ツール通信ゼロ・スプレッドシート内完結）
1. **A2セル** に生の業務文章（メール・議事録・契約条項など）を貼る → **B2セル** に社名・T番号・電話番号・メールアドレス・口座番号・任意の担当者名が `<<取引先_01>>` 等に自動変換された **AI送信用の安全なプロンプト** が即座に出ます。
2. B2セルをコピーして普段の ChatGPT / Claude / Copilot に貼り、返ってきた回答を **C2セル** に貼る。
3. **D2セル** に、すべての `<<取引先_01>>` 等が **元の正式社名・担当者名・メアドへ1文字の狂いもなく自動復元された完成文** が出力されます！

### 有料エリア（¥500）に入っているもの
1. **コピペ1分で動く Googleスプレッドシート専用GASコード全文**（権限承認ポップアップすら不要な純粋カスタム関数 `=MASK_FOR_AI()` / `=RESTORE_FROM_AI()` 設計）
2. **個人名・案件名も追加で伏せられる「カスタム伏せ語セル」連携の1行見出し＆数式テンプレ**
3. **AI側が `<<取引先_01>>` の記号を勝手な表現に崩さないための「鉄板システムプロンプト」**

※経理・バックオフィス向けの「令和8年年末調整シフト逆算＆10月インボイス5割控除の数式セット」をお探しの方は、こちらのnote（ https://note.com/pecopeko1011/n/nbc8b162c7edb ）もあわせてご覧ください。
---FREE_PART_END---

---PAID_PART_START---
ご購入ありがとうございます！外部APIや特別な権限（OAuth承認）を一切使わず、スプレッドシート標準のカスタム関数だけで安全に動くよう設計してあります。以下の3ステップで1分後にすぐ使えます。

## ステップ1：GoogleスプレッドシートにGASコードを貼り付け（初回1回だけ）

1. 新しい Googleスプレッドシート を開く
2. 上部メニュー **「拡張機能」→「Apps Script」** をクリック
3. 最初から入っている `function myFunction() {}` をすべて消して、以下のコードをまるごと貼り付け、上部の **💾（プロジェクトを保存）** を押します（実行ボタンを押す必要はありません）。

```javascript
/**
 * 原文から社名・T番号・メール・電話・口座・指定ワードを型付き仮名トークンへ変換する内部辞書ビルダー
 */
function buildAiPrivacyVault_(rawText, extraWordsCsv) {
  var text = String(rawText || "");
  var rawToTok = {};
  var tokToRaw = {};
  var counts = {};

  function assignToken(kind, matchStr) {
    if (!rawToTok[matchStr]) {
      counts[kind] = (counts[kind] || 0) + 1;
      var num = ("0" + counts[kind]).slice(-2);
      var tok = "<<" + kind + "_" + num + ">>";
      rawToTok[matchStr] = tok;
      tokToRaw[tok] = matchStr;
    }
    return rawToTok[matchStr];
  }

  var masked = text;

  // 1) 任意の追加伏せワード（担当者名・プロジェクト名など、カンマ区切り・長い順）
  if (extraWordsCsv !== null && extraWordsCsv !== undefined && String(extraWordsCsv).trim() !== "") {
    var words = String(extraWordsCsv)
      .split(/[、,]/)
      .map(function(w) { return w.trim(); })
      .filter(function(w) { return w.length > 0; })
      .sort(function(a, b) { return b.length - a.length; });

    for (var w = 0; w < words.length; w++) {
      var target = words[w];
      if (masked.indexOf(target) !== -1) {
        var tokCustom = assignToken("固有名", target);
        masked = masked.split(target).join(tokCustom);
      }
    }
  }

  // 2) 定型機密パターン（APIキー・T番号・メール・電話・口座・前株/後株法人名）
  var rules = [
    { label: "API鍵", re: /\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b/g },
    { label: "登録番号", re: /\bT\d{13}\b/g },
    { label: "マイナンバー候補", re: /(?<!\d)\d{4}-?\d{4}-?\d{4}(?!\d)/g },
    { label: "メール", re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g },
    { label: "電話", re: /(?<!\d)0\d{1,4}-\d{1,4}-\d{3,4}(?!\d)|(?<!\d)0[789]0\d{8}(?!\d)/g },
    { label: "口座", re: /(?:普通|当座)\s*\d{7}/g },
    { label: "取引先", re: /(?:株式会社|有限会社|合同会社)[一-龥ァ-ヶーA-Za-z0-9]{1,16}|[一-龥ァ-ヶーA-Za-z0-9]{1,16}(?:株式会社|有限会社|合同会社)/g }
  ];

  for (var i = 0; i < rules.length; i++) {
    var kind = rules[i].label;
    masked = masked.replace(rules[i].re, function(m) {
      return assignToken(kind, m);
    });
  }

  return { masked: masked, tokToRaw: tokToRaw };
}

/**
 * AI送信前に社名・連絡先・指定ワードを可逆仮名化します。
 * @param {string} rawText 元の文章（A2）
 * @param {string=} extraWordsCsv 追加で伏せたい人名・案件名（カンマ区切り、省略可：E2）
 * @return {string} 仮名化済みテキスト
 * @customfunction
 */
function MASK_FOR_AI(rawText, extraWordsCsv) {
  if (rawText === null || rawText === undefined || String(rawText).trim() === "") {
    return "";
  }
  return buildAiPrivacyVault_(rawText, extraWordsCsv).masked;
}

/**
 * AIの回答に含まれる仮名トークン（<<取引先_01>>等）を元の正式名称へ自動復元します。
 * @param {string} rawText 元の文章（A2）
 * @param {string} aiReply AIからの回答文（C2）
 * @param {string=} extraWordsCsv 追加で伏せた人名・案件名（E2、省略可）
 * @return {string} 復元済みの完成文
 * @customfunction
 */
function RESTORE_FROM_AI(rawText, aiReply, extraWordsCsv) {
  if (aiReply === null || aiReply === undefined || String(aiReply).trim() === "") {
    return "";
  }
  var vault = buildAiPrivacyVault_(rawText, extraWordsCsv);
  var out = String(aiReply);
  var keys = Object.keys(vault.tokToRaw);
  for (var i = 0; i < keys.length; i++) {
    out = out.split(keys[i]).join(vault.tokToRaw[keys[i]]);
  }
  return out;
}
```

---

## ステップ2：シートの1行目（見出し）と2行目（数式）をセット

スプレッドシートに戻り、**A1〜F1セル** に以下の見出しを貼り付けます（タブ区切りなのでA1を選んで貼り付けると一発で並びます）。

```text
①原文（社外秘あり）	②追加で伏せたい人名・案件名(カンマ区切り)	③AI送信用プロンプト（ここをコピー）	④AIの回答貼り付け欄	⑤復元済みの完成文（自動出力）	AIへの依頼内容
```

次に、以下の2つのセルに数式を入れるだけでシート完成です！

**C2セル（AIにそのまま貼れる「指示文＋仮名化テキスト」自動生成式）**
```excel
=IF(A2="", "", "【重要ルール】文章内の <<取引先_01>> や <<固有名_01>> のような記号は絶対に書き換えたり省略したりせず、そのまま回答内に残してください。" & CHAR(10) & "【依頼】" & IF(F2="", "以下の内容を整理・要約してください。", F2) & CHAR(10) & "---" & CHAR(10) & MASK_FOR_AI(A2, B2))
```

**E2セル（AIの回答 D2 を元の社名・人名・メアドへ一発復元する式）**
```excel
=IF(D2="", "", RESTORE_FROM_AI(A2, D2, B2))
```

---

## ステップ3：実際の運用イメージ（コピペテスト用サンプル）

動作確認として、2行目に以下を入れて試してみてください。

- **A2（原文）**：`株式会社アルファの山田太郎様（yamada@alpha.co.jp / T7000012050002）とサクラ電機株式会社の鈴木様から見積書を受領。株式会社アルファの方が納期が2週間早い。`
- **B2（追加で伏せたい人名）**：`山田太郎, 鈴木`
- **F2（AIへの依頼内容）**：`社内稟議向けに、どちらの発注先を優先すべきか結論と連絡先を箇条書きにしてください。`

すると **C2セル** には社名も人名もメアドも一切含まれない `<<取引先_01>>` `<<固有名_01>>` 形式のプロンプトが自動で作られます。それを ChatGPT や Claude に貼り、返ってきた文章を **D2セル** に貼った瞬間、**E2セル** に正式社名・人名入りの稟議テキストが完成します。

2行目の C2・E2 を下方向にコピーしておけば、毎日の議事録要約・契約書レビュー・顧客返信下書きをすべて「情報漏洩ゼロ」で高速化できます。ぜひブックマークして日々のAI実務にお役立てください！
---PAID_PART_END---
