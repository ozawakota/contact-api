# 技術方針・スタック

## 技術哲学
### アーキテクチャ原則
- **クリーンアーキテクチャ**: レイヤー責務分離によるテスト容易性と保守性確保
- **関心の分離**: データ（contacts）・AI解析（contact_ai_analyses）・ベクトル（contact_vectors）の3テーブル分離
- **セキュリティファースト**: LLM特有脅威への多層防御設計
- **Cloud Nativeアプローチ**: サーバーレス基盤による運用効率化

### 技術選定原則
- **実証済み技術**: 本番実績のあるエンタープライズグレード技術を優先
- **コスト効率**: 運用コストとパフォーマンスの最適バランス
- **統合性**: 既存システムとの連携容易性
- **拡張性**: 将来の機能追加・スケールアウトに対応

## コア技術スタック

### Backend
- **言語**: Python 3.11+ 
- **フレームワーク**: FastAPI（非同期処理対応・自動ドキュメント生成）
- **ORM**: SQLModel（Pydantic + SQLAlchemy統合）
- **バリデーション**: Pydantic（スキーマファースト設計）

### AI・LLM
- **LLM**: Gemini API
  - Function Calling標準対応
  - GPT-4比較: コスト30%削減、レイテンシ20%改善
- **手法**: Self-Refinement（自己検証・品質保証）
- **ベクトル検索**: pgvector（PostgreSQL拡張）
  - 専用ベクトルDB比較: 運用コスト80%削減

### データベース
- **メインDB**: PostgreSQL + pgvector
- **テーブル設計**: 3テーブル分離パターン
  - `contacts`: ユーザー生データ（不変・監査対応）
  - `contact_ai_analyses`: AI解析結果（再解析可能）
  - `contact_vectors`: RAGベクトル（類似検索用）

### Frontend
- **フレームワーク**: Next.js 15.x（App Router・Server Components）
- **UI言語**: TypeScript 5.x（厳密な型安全性）
- **スタイリング**: Tailwind CSS 4.x（ユーティリティファースト）
- **フォーム**: React Hook Form + Zod（バリデーション統合）
- **認証**: Firebase Authentication（Google OAuth優先）

### インフラ・デプロイ
- **プラットフォーム**: Google Cloud Platform
- **バックエンド**: Cloud Run（マネージドサーバーレス）
- **フロントエンド**: Firebase Hosting / Vercel（予定）
- **CI/CD**: Cloud Build（cloudbuild.yaml）
- **コンテナ**: Docker（asia-northeast1リージョン）
- **監視**: Cloud Logging

## 開発規約

### コード構成
```
バックエンド（レイヤードアーキテクチャ）:
- Views: リクエスト受付のみ（ロジック禁止）
- UseCases: フロー制御（AI解析→DB保存→メール送信）
- Repository: DB抽象化層
- Services: 独立したサービス（AI・ベクトル・メール）

フロントエンド（App Router構成）:
- app/: ページルーティング・レイアウト
- components/: 再利用可能UI（auth/, ui/, forms/）
- hooks/: 状態管理・データフェッチ（useAuth）
- lib/: 設定・ユーティリティ（firebase.ts）
- types/: TypeScript型定義
```

### 依存関係管理
- **Python**: requirements.txt（シンプル管理）
- **Node.js**: package.json + npm（フロントエンド）
- **依存性注入**: providers.pyによるDIコンテナパターン
- **設定管理**: 環境変数ベース（12-Factor App準拠）
  - バックエンド: `.env`
  - フロントエンド: `.env.local`（NEXT_PUBLIC_プレフィックス）

### セキュリティ実装
- **入力検証**: _validators.pyによる専用サニタイズ層
- **プロンプトインジェクション対策**: XMLタグ隔離・ガードレール設定
- **認証**: Firebase Authentication（Google OAuth + メール認証）+ カスタムクレーム管理者制御

## パフォーマンス指標
- **API応答時間**: 2秒以内
- **AI解析時間**: 30秒以内
- **全体処理時間**: 2分以内（99.9%短縮目標）
- **同時接続**: 100リクエスト/秒対応

## 運用・監視
- **ログ**: Cloud Logging統合
- **メトリクス**: 分類精度・応答時間・エラー率
- **アラート**: 異常検知・自動エスカレーション
- **バックアップ**: データ不変性保証による継続性確保