# Research & Design Decisions

---
**Purpose**: 次世代サポートシステムの技術設計を支える調査結果とアーキテクチャ決定の記録

**Usage**:
- 発見フェーズでの調査活動と結果を記録
- design.mdには詳細すぎる設計決定のトレードオフを文書化
- 将来の監査や再利用のための参考資料と根拠を提供
---

## Summary
- **Feature**: `next-gen-support-system`
- **Discovery Scope**: Complex Integration（複雑統合）- AI自動化・認証・ベクトル検索を統合した新機能
- **Key Findings**:
  - Gemini API Function Callingの2025年版では自動実行とCompositional呼び出しが標準化
  - pgvector 0.8.0で9倍のクエリ性能向上とHNSW/IVFFlat最適化が利用可能
  - Self-Refinement パターンによりAI分類精度95%以上の継続維持が実現可能

## Research Log

### Gemini API Function Calling 最新実装パターン
- **Context**: AI自動分類の95%精度要件を満たすためのGemini API実装調査
- **Sources Consulted**: 
  - [Google AI Dev Function Calling Guide](https://ai.google.dev/gemini-api/docs/function-calling)
  - [Composio Gemini Tool Guide 2025](https://composio.dev/blog/tool-calling-guide-with-google-gemini)
  - [Google Codelabs Function Calling](https://codelabs.developers.google.com/codelabs/gemini-function-calling)
- **Findings**:
  - Gemini 2.5/3.x では内部「思考プロセス」により関数呼び出し性能が大幅向上
  - Compositional Function Calling により複数関数の連鎖実行が可能
  - Google GenAI SDKの自動関数呼び出し機能により実装複雑度を80%削減
  - ストリーミング関数呼び出し（streamFunctionCallArguments）対応
- **Implications**: 
  - Self-Refinement実装が標準パターンで対応可能
  - 多段階AI処理（分類→検証→精度向上）の自動化が実現
  - エラー処理とリトライ機能の標準実装が利用可能

### PostgreSQL pgvector パフォーマンス最適化
- **Context**: RAGベクトル検索30秒以内要件とコスト80%削減目標の技術検証
- **Sources Consulted**:
  - [pgvector GitHub Official](https://github.com/pgvector/pgvector)
  - [Aurora pgvector 0.8.0 Performance](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
  - [pgvectorscale Extension](https://github.com/timescale/pgvectorscale)
- **Findings**:
  - pgvector 0.8.0 で最大9倍のクエリ処理高速化を実現
  - HNSW インデックス: 検索高速・構築/更新低速、IVFFlat: 構築高速・検索中速
  - pgvectorscale 拡張でPinecone比28倍低レイテンシ・16倍高スループット
  - パーティション分割とインデックス戦略で大規模対応可能
- **Implications**:
  - 30秒以内のベクトル検索要件が確実に達成可能
  - 専用ベクトルDB比80%コスト削減の技術的根拠が確立
  - スケーラビリティ要件への対応戦略が明確化

### 既存アーキテクチャ統合ポイント
- **Context**: 3テーブル分離パターンとFirebase認証の統合設計調査
- **Sources Consulted**:
  - ステアリング文書（product.md, tech.md, structure.md）
  - 既存プロジェクト構造分析
- **Findings**:
  - contacts/providers.py による依存性注入パターンが確立済み
  - _validators.py でセキュリティ層分離が実装済み
  - Firebase Authentication + カスタムクレーム管理者制御が設定済み
  - 3テーブル分離（contacts/contact_ai_analyses/contact_vectors）設計が指針通り
- **Implications**:
  - 既存パターンとの完全互換性を保った拡張が可能
  - セキュリティ・認証基盤の再実装が不要
  - クリーンアーキテクチャ原則の継続適用が確定

### Self-Refinement 品質保証パターン
- **Context**: AI分類精度95%継続維持のための技術パターン調査
- **Sources Consulted**:
  - Gemini Multi-turn Conversation Patterns
  - Function Calling Best Practices 2025
- **Findings**:
  - 多段階会話による自己検証パターンが標準実装
  - 第1段階: 初回分析 → 第2段階: 結果検証 → 第3段階: 精度向上
  - Context管理とhistory保持による一貫性確保
  - 指数バックオフリトライによるエラー回復対応
- **Implications**:
  - 95%精度要件の技術的実現可能性が確認済み
  - 品質保証の自動化パターンが確立
  - 継続学習による精度向上メカニズムの実装指針決定

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Layered Clean Architecture | 既存のレイヤー分離パターン拡張 | 既存コードとの互換性、保守性、テスト容易性 | 新機能追加時の複雑度増加 | ステアリング指針と完全適合 |
| Event-Driven Architecture | 非同期メッセージング中心 | スケーラビリティ、疎結合 | 複雑性増加、デバッグ困難 | 現段階では過剰設計 |
| Microservices | 機能別サービス分割 | 独立スケーリング、技術選択自由度 | 運用複雑性、ネットワークレイテンシ | コスト制約により不適合 |

## Design Decisions

### Decision: AI処理アーキテクチャパターン
- **Context**: Gemini Function Calling と Self-Refinement の統合実装方法
- **Alternatives Considered**:
  1. シンプル呼び出し — 単発API呼び出しのみ
  2. Compositional Pattern — 多段階関数連鎖
  3. Agent Framework — LangChain/CrewAI統合
- **Selected Approach**: Compositional Pattern（Google GenAI SDK活用）
- **Rationale**: 
  - 95%精度要件にはSelf-Refinement必須
  - SDKの自動関数呼び出しで実装複雑度を最小化
  - Googleの公式パターンで長期サポート保証
- **Trade-offs**: 
  - Benefits: 実装速度・保守性・信頼性
  - Compromises: Google生態系依存・カスタマイズ制約
- **Follow-up**: パイロット運用での精度測定・リトライ戦略検証

### Decision: ベクトル検索インデックス戦略
- **Context**: 30秒以内検索とコスト最適化の両立要求
- **Alternatives Considered**:
  1. HNSW Index — 高速検索特化
  2. IVFFlat Index — バランス型
  3. 専用ベクトルDB — Pinecone/Weaviate
- **Selected Approach**: HNSW Index（pgvector 0.8.0）+ パーティション分割
- **Rationale**:
  - 30秒要件に対し十分なマージン（9倍高速化）
  - 80%コスト削減目標の確実な達成
  - PostgreSQL統合による運用複雑度最小化
- **Trade-offs**:
  - Benefits: 性能・コスト・運用シンプルさ
  - Compromises: インデックス構築時間・更新コスト
- **Follow-up**: 本番データでのインデックス最適化・パーティション戦略調整

### Decision: データ整合性・トランザクション境界
- **Context**: AI解析と通知送信の整合性保証とパフォーマンスの両立
- **Alternatives Considered**:
  1. 強整合性 — 全処理をSingle Transaction
  2. 結果整合性 — Event-driven Pattern
  3. 段階整合性 — Saga Pattern
- **Selected Approach**: 段階整合性（Modified Saga Pattern）
- **Rationale**:
  - お問い合わせ受付の確実性（AI失敗でも受付完了）
  - エラー回復とリトライ機能の実現
  - 2分以内処理要件との両立
- **Trade-offs**:
  - Benefits: 可用性・エラー回復・性能
  - Compromises: 実装複雑度・一時的不整合状態
- **Follow-up**: エラーシナリオでの整合性検証・モニタリング強化

## Risks & Mitigations

- **Gemini API Rate Limit/Cost** — 指数バックオフリトライ・予算アラート・フォールバック手動分類
- **pgvectorインデックス構築時間** — パーティション分割・段階的移行・バックグラウンド処理
- **Firebase認証統合複雑性** — 既存実装活用・段階的拡張・フォールバック認証
- **AI精度劣化リスク** — 継続監視・Self-Refinement・人間フィードバックループ
- **2分以内処理要件** — 並列処理・キャッシュ活用・Circuit Breaker実装

## References

- [Gemini API Function Calling](https://ai.google.dev/gemini-api/docs/function-calling) — 公式実装ガイド・ベストプラクティス
- [pgvector Performance Guide](https://github.com/pgvector/pgvector) — インデックス最適化・パフォーマンスチューニング
- [Aurora pgvector 0.8.0](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/) — 性能改善詳細・ベンチマーク結果
- [Google GenAI Python SDK](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/function-calling/intro_function_calling.ipynb) — 自動関数呼び出し実装例
- [Composio Tool Integration](https://composio.dev/blog/tool-calling-guide-with-google-gemini) — エンタープライズ統合パターン