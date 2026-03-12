# 運賃検索システム

マルチ年度対応の運賃検索 Streamlit アプリです。

## セットアップ

### 1. config.yaml の編集

`config.yaml` を開き、各年度のスプレッドシートIDを設定してください。

```yaml
spreadsheets:
  - name: "2025年度版"
    id: "1aBcDeFgHiJkLmNoPqRsTuVwXyZ..."  # ← ここを実際のIDに変更
```

スプレッドシートIDはURLから取得できます:
`https://docs.google.com/spreadsheets/d/【ここがID】/edit`

### 2. Google API 認証設定

サービスアカウントのJSONキーを以下のいずれかの方法で設定してください:

**方法A: 環境変数（Railway推奨）**
```bash
# JSONファイルの内容を1行の文字列として環境変数に設定
export GOOGLE_CREDENTIALS='{"type":"service_account","project_id":"..."}'
```

**方法B: ファイル配置（ローカル開発用）**
```bash
# credentials.json をプロジェクトルートに配置
# .gitignore に含まれているためコミットされません
```

### 3. スプレッドシートの共有設定

サービスアカウントのメールアドレスに対して、スプレッドシートの**閲覧権限**を付与してください。

### 4. ローカル起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

## スプレッドシートのデータ構造

| 位置 | 内容 |
|------|------|
| 5行目〜14行目 | 都市名（列ヘッダー） |
| A列 16行目〜 | 重量（kg）リスト |
| B列以降 16行目〜 | 運賃データ |

## Railway デプロイ

1. GitHubにプッシュ
2. Railway で「Deploy from GitHub」
3. 環境変数 `GOOGLE_CREDENTIALS` を設定
4. 自動デプロイ完了
