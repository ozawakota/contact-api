# Cloud Run Functions とCloud Buildのデプロイ構成

## Cloud Run Service (メインAPI)

### Cloud Buildによる自動デプロイ設定

プロジェクトのメインのFastAPIアプリケーションは、`cloudbuild.yaml`によってCloud Runサービスとして自動デプロイされます。

#### デプロイフロー
1. **Dockerイメージビルド**
   - ベースイメージ: `gcr.io/cloud-builders/docker`
   - コンテナレジストリ: `asia-northeast1-docker.pkg.dev/$PROJECT_ID/contact-api/fastapi-app`
   - Dockerfile位置: `backend/db-backup/docker/Dockerfile`
   - ビルドコンテキスト: `./backend`

2. **イメージプッシュ**
   - Artifact Registryへのプッシュ

3. **Cloud Runデプロイ**
   - サービス名: `fastapi-service`
   - リージョン: `asia-northeast1`
   - 設定:
     - メモリ: 1GiB
     - CPU: 1コア
     - タイムアウト: 300秒
     - 同時実行数: 10
     - 最大インスタンス数: 10
     - 認証なしアクセス許可
     - 環境変数: `ENVIRONMENT=production`

### Cloud Run Functions (補助的な処理)

特定のイベントをトリガーにした「切り離せる処理」を担当させます。

具体例:

* レポート生成: 管理者が「月間のお問い合わせ統計PDF」をリクエストした際、その生成処理をFunctionsに投げる。

* Embeddingの一括更新: 大量の過去データをベクトルDB（pgvector）に再登録するバッチ処理。

* 外部連携通知: 振り分けが決まった後、Slackや外部CRMへの通知だけを非同期で行う。


## 検討

Google Cloud Pub/Sub 

Pub/Subは、データを送る側と受け取る側を**「直接つながない（疎結合）」**のが最大の特徴です。

## 🚀 なぜ今回のお問い合わせAPIで使うのか？
直接「FastAPIからFunctionsを呼ぶ」のではなく、間にPub/Subを挟むのには3つの大きな理由があります。

  1. レスポンス速度の向上（ユーザーを待たせない）
AIの解析が終わった後、「メール送信」や「外部システム連携」に時間がかかると、ユーザーの画面は止まったままになります。

 Pub/Subあり: 「解析完了！あとはPub/Subに投げたから、画面には『受付完了』を出そう」と、一瞬でレスポンスを返せます。

  2. 負荷の分散と平準化
キャンペーンなどで一度に1,000件のお問い合わせが殺到したとします。

Pub/Subなし: APIサーバーやメールサーバーがパンクしてダウンする可能性があります。

Pub/Subあり: Pub/Subがメッセージを溜めておいてくれるので、受信側のFunctionsが自分のペースで1件ずつ確実に処理できます。

  3. 耐障害性（リトライの自動化）
もしメールサーバーが一時的にメンテナンスで落ちていても、Pub/Subはメッセージを保持し続け、メールサーバーが復活した瞬間に再送してくれます。