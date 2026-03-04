# Database Migrations - 次世代サポートシステム

このディレクトリには、AI駆動の次世代カスタマーサポートシステムのためのデータベースマイグレーションファイルが含まれています。

## Overview

次世代サポートシステムでは、以下の機能を実現するために新しいデータベーステーブルとインデックスを作成します：

- **AI分析結果保存**: カテゴリ分類、緊急度判定、感情分析結果
- **ベクトル検索**: RAG（Retrieval-Augmented Generation）による類似事例検索
- **高性能インデックス**: pgvector + HNSWによる高速ベクトル類似度検索

## Architecture

```
contacts (既存)
├── contact_ai_analyses (1:1) - AI分析結果
└── contact_vectors (1:1)     - ベクトル埋め込み
```

### Tables Created

1. **contact_ai_analyses**
   - AI分析結果（カテゴリ、緊急度、感情、信頼度スコア）
   - 30文字要約とAI判断理由
   - 処理ステータス管理

2. **contact_vectors**
   - 768次元ベクトル埋め込み（Gemini標準）
   - モデルバージョン管理
   - 処理メタデータ（JSONB）

### Indexes Created

#### HNSW Vector Index
```sql
-- 高速コサイン類似度検索用
CREATE INDEX idx_contact_vectors_embedding_hnsw 
ON contact_vectors 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### Performance Indexes
- Category, urgency, sentiment別検索
- 作成日時・処理日時別ソート
- 未処理アイテム高速取得
- JSONB メタデータ検索（GIN）

## Prerequisites

### 1. PostgreSQL + pgvector拡張

```bash
# pgvector拡張のインストール（Ubuntu/Debian）
sudo apt install postgresql-15-pgvector

# または Homebrew（macOS）
brew install pgvector

# または Docker
docker run --name postgres-vector \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d pgvector/pgvector:pg15
```

### 2. 既存テーブル

`contacts`テーブルが既に存在している必要があります。

### 3. 環境変数

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/contact_api"
```

## Usage

### 1. 自動マイグレーション実行

```bash
cd /Users/kouta.ozawa/Git/_personal/contact-api/backend
python migrations/run_migration.py
```

### 2. 手動マイグレーション実行

```bash
# PostgreSQLに直接実行
psql $DATABASE_URL -f migrations/create_ai_analysis_tables.sql
```

### 3. テスト環境での検証

```bash
# テスト用データベースでのマイグレーション
export TEST_DATABASE_URL="postgresql://test_user:test_pass@localhost:5432/test_contact_api"
python -m pytest tests/test_database_migration.py -v
```

## Migration Content

### Phase 1: Extension & Prerequisites
- pgvector拡張有効化
- contactsテーブル存在確認

### Phase 2: Table Creation
- contact_ai_analysesテーブル作成
- contact_vectorsテーブル作成
- 制約・外部キー設定

### Phase 3: Index Creation
- HNSWベクトル検索インデックス
- パフォーマンス最適化インデックス群
- JSONB GINインデックス

### Phase 4: Triggers & Functions
- 自動タイムスタンプ更新
- データ整合性チェック

## Performance Tuning

### Vector Search Optimization

```sql
-- 検索時のパフォーマンス設定
SET enable_seqscan = off;  -- フルスキャン無効化
SET work_mem = '256MB';    -- ソート・ハッシュ用メモリ増加
```

### Index Maintenance

```sql
-- インデックス統計更新（定期実行推奨）
ANALYZE contact_ai_analyses;
ANALYZE contact_vectors;

-- インデックス使用状況確認
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes 
WHERE tablename IN ('contact_ai_analyses', 'contact_vectors');
```

## Monitoring & Validation

### 1. テーブル状態確認

```sql
-- テーブル存在確認
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_name IN ('contact_ai_analyses', 'contact_vectors');

-- レコード数確認
SELECT 
    (SELECT count(*) FROM contact_ai_analyses) as ai_analyses_count,
    (SELECT count(*) FROM contact_vectors) as vectors_count;
```

### 2. インデックス状態確認

```sql
-- インデックス一覧
SELECT tablename, indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('contact_ai_analyses', 'contact_vectors')
ORDER BY tablename, indexname;

-- HNSWインデックス詳細
SELECT 
    schemaname, 
    tablename, 
    indexname,
    regexp_replace(indexdef, '.*WITH \\(([^)]+)\\).*', '\\1') as hnsw_params
FROM pg_indexes 
WHERE indexdef LIKE '%hnsw%';
```

### 3. パフォーマンス監視

```sql
-- ベクトル検索パフォーマンステスト
EXPLAIN (ANALYZE, BUFFERS) 
SELECT contact_id, embedding <=> '[0,1,0,1,...]' as distance
FROM contact_vectors 
ORDER BY embedding <=> '[0,1,0,1,...]' 
LIMIT 10;
```

## Rollback

マイグレーションをロールバックする場合：

```sql
-- テーブル削除（データも削除されます）
DROP TABLE IF EXISTS contact_vectors CASCADE;
DROP TABLE IF EXISTS contact_ai_analyses CASCADE;

-- pgvector拡張削除（他で使用していない場合のみ）
-- DROP EXTENSION IF EXISTS vector;
```

## Troubleshooting

### Common Issues

1. **pgvector拡張が見つからない**
   ```bash
   ERROR: extension "vector" is not available
   ```
   → pgvector拡張をインストールしてください

2. **contactsテーブルが存在しない**
   ```bash
   ERROR: relation "contacts" does not exist
   ```
   → ベースシステムのマイグレーションを先に実行してください

3. **権限エラー**
   ```bash
   ERROR: permission denied to create extension "vector"
   ```
   → SUPERUSER権限でpgvector拡張を有効化してください

4. **メモリ不足（インデックス作成時）**
   ```bash
   ERROR: could not extend file "base/.../...": No space left on device
   ```
   → `maintenance_work_mem`を増加させるか、一時的にディスク容量を確保してください

## Development Notes

### Testing Strategy

1. **Unit Tests**: `tests/test_database_migration.py`
   - テーブル作成検証
   - 制約・インデックス検証
   - カスケード削除テスト

2. **Integration Tests**: 実際のPostgreSQLでの動作確認
   - マイグレーション実行テスト
   - パフォーマンステスト
   - データ整合性テスト

### Code Quality

- SQLコードの可読性とメンテナンス性重視
- エラーハンドリングと詳細なログ出力
- 段階的な前提条件チェック
- 自動検証とレポート機能

このマイグレーションにより、次世代サポートシステムの基盤となるデータベーススキーマが構築され、AI駆動の高速カスタマーサポート自動化が実現されます。