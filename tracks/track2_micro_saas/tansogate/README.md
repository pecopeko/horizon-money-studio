# TANSOGATE（炭素門）

**SSBJサステナビリティ開示基準（S1/S2）・温対法SHK制度（3,000 t-CO2/年 特定排出者）・GHG Scope 1/2（ロケーション基準＋マーケット基準−非化石証書）・Scope 3・環境表示（グリーンウォッシュ防止）ブラウザ完結ローカル監査ツール**

- 電力使用量・燃料実績・調達金額・非化石証書・J-クレジット保有内容を外部サーバーへ **一切送信しません**（ネットワーク通信 `0` 回）。
- 8つのSSBJ・SHK・グリーンウォッシュ検証要件をローカル実行し、**『SSBJ GHG算定・環境表示監査証明書（Markdown）』** を即時生成します。

## テスト実行

```bash
node --test tracks/track2_micro_saas/tansogate/test/tanso-engine.test.mjs
```
