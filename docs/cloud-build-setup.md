# Cloud Build設定詳細ガイド

## 📋 概要

`cloudbuild.yaml`は、GitHubからGoogle Cloud Runまでの**完全自動デプロイパイプライン**を定義するファイルです。

## 🏗️ 全体構造

```yaml
steps:     # ビルドの手順（3ステップ）
options:   # ビルド全体の設定
```

## 🔨 Step 1: Dockerイメージビルド

```yaml
- name: 'gcr.io/cloud-builders/docker'
  args: [
    'build',
    '-t', 'asia-northeast1-docker.pkg.dev/$PROJECT_ID/contact-api/fastapi-app',
    '-f', 'backend/db-backup/docker/Dockerfile', 
    './backend'                     
  ]
```

### 詳細説明

| パラメータ | 意味 | 値 |
|-----------|------|-----|
| `name` | 使用するビルダー | Googleが提供するDockerビルド専用コンテナ |
| `build` | 実行コマンド | Dockerイメージを作成 |
| `-t` | タグ名 | `asia-northeast1-docker.pkg.dev/$PROJECT_ID/contact-api/fastapi-app` |
| `-f` | Dockerfileパス | `backend/db-backup/docker/Dockerfile` |
| コンテキスト | ビルド基準ディレクトリ | `./backend` |

### 重要ポイント
- **Dockerfileの場所**: `backend/db-backup/docker/Dockerfile`
- **ビルドコンテキスト**: `./backend`
- この構成により、Dockerfile内で`app/`フォルダなどにアクセス可能

## 📤 Step 2: イメージプッシュ

```yaml
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'asia-northeast1-docker.pkg.dev/$PROJECT_ID/contact-api/fastapi-app']
```

### 詳細説明
- **目的**: 作成したDockerイメージをArtifact Registryに保存
- **レジストリ**: Google Cloud Artifact Registry
- **リージョン**: `asia-northeast1`（東京）
- **自動変数**: `$PROJECT_ID`は実行時に自動的にプロジェクトIDが設定される

## 🚀 Step 3: Cloud Runデプロイ

```yaml
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args:
    - 'run'
    - 'deploy'
    - 'fastapi-service'
    - '--image'
    - 'asia-northeast1-docker.pkg.dev/$PROJECT_ID/contact-api/fastapi-app'
    - '--region'
    - 'asia-northeast1'
    - '--platform'
    - 'managed'
    - '--allow-unauthenticated'
    - '--timeout'
    - '300'
    - '--memory'
    - '1Gi'
    - '--cpu'
    - '1'
    - '--concurrency'
    - '10'
    - '--max-instances'
    - '10'
    - '--set-env-vars'
    - 'ENVIRONMENT=production'
```

### 基本設定

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| サービス名 | `fastapi-service` | Cloud Runサービスの名前 |
| リージョン | `asia-northeast1` | 東京リージョンにデプロイ |
| プラットフォーム | `managed` | フルマネージドサービス |
| 認証 | `--allow-unauthenticated` | パブリックアクセス許可 |

### リソース設定

| 項目 | 値 | 理由 |
|------|-----|------|
| **メモリ** | `1Gi` | APIサーバーとして適切なサイズ |
| **CPU** | `1` | 1コア、中程度の負荷に対応 |
| **タイムアウト** | `300秒` | AI処理を考慮した長めの設定 |

### スケーリング設定

| 項目 | 値 | 説明 |
|------|-----|------|
| **同時実行数** | `10` | 1インスタンスで10リクエスト並行処理 |
| **最大インスタンス** | `10` | 負荷に応じて最大10インスタンスまで自動スケール |
| **処理能力** | `最大100リクエスト` | 10インスタンス × 10並行 = 100同時処理 |

### 環境変数
- **ENVIRONMENT**: `production`で本番モード動作

## ⚙️ Options設定

```yaml
options:
  logging: CLOUD_LOGGING_ONLY
```

### 詳細説明
- **ログ出力先**: Google Cloud Loggingのみ
- **効果**: コンソール出力を抑制し、ログを一元管理
- **利点**: 本番環境でのログ分析とモニタリングが容易

## 🔄 実行フロー

### 自動実行トリガー
1. GitHubリポジトリへのプッシュ
2. Cloud Build手動実行
3. 指定ブランチへのマージ

### デプロイステップと所要時間

| ステップ | 処理内容 | 所要時間 |
|---------|----------|----------|
| 1️⃣ **ビルド** | Dockerイメージ作成 | 約2-3分 |
| 2️⃣ **プッシュ** | Artifact Registryに保存 | 約1分 |
| 3️⃣ **デプロイ** | Cloud Runにデプロイ | 約2分 |
| ✅ **完了** | 新バージョン稼働開始 | **合計5-6分** |

## 🔧 設定のカスタマイズ

### リソース調整例

```yaml
# 高負荷対応
'--memory': '2Gi'
'--cpu': '2'
'--max-instances': '20'

# 開発環境
'--memory': '512Mi'
'--cpu': '1'
'--max-instances': '3'
```

### 環境別設定

```yaml
# 本番環境
'--set-env-vars': 'ENVIRONMENT=production,LOG_LEVEL=INFO'

# ステージング環境
'--set-env-vars': 'ENVIRONMENT=staging,LOG_LEVEL=DEBUG'
```

## 🚨 重要な注意点

### セキュリティ
- `--allow-unauthenticated`でパブリックアクセス許可
- 必要に応じてIAMによるアクセス制御を検討

### コスト最適化
- `--max-instances`で上限設定
- 不要な高スペック設定を避ける

### パフォーマンス
- `--concurrency`と`--max-instances`のバランス調整
- CPUとメモリの適切な組み合わせ

## 📊 監視とトラブルシューティング

### ログ確認
```bash
# Cloud Buildログ
gcloud builds list

# Cloud Runログ
gcloud run services logs read fastapi-service --region=asia-northeast1
```

### メトリクス監視
- レスポンス時間
- インスタンス使用率
- エラー率
- リクエスト数

この設定により、**コードプッシュから本番稼働まで5-6分で完全自動化**された、スケーラブルで信頼性の高いデプロイパイプラインが実現されています。