# テーブル設計

## 設計方針：生データとメタデータの分離

### なぜ分けるのか

| 観点 | 1テーブルに混在させた場合の問題 | 分離した場合のメリット |
|---|---|---|
| 責務 | ユーザーデータとAI解析結果が混在し、変更理由が不明確 | 各テーブルが「1つの責務」を持つ |
| 不変性 | ユーザーの生データが上書きされるリスクがある | `contacts` を不変レコードとして保護できる |
| 再解析 | LLMモデルを切り替えて再解析すると過去の結果が消える | `contact_ai_analyses` を再作成するだけで生データに影響なし |
| 検索性能 | ベクトルデータをメインテーブルに持つと全件スキャンに影響する | `contact_vectors` を分離し、ベクトル検索のみに最適化できる |

---

## テーブル一覧

```
contacts                ← ユーザーが入力した生データ（不変）
  └── contact_ai_analyses  ← AIが解析したメタデータ（再解析で更新可）
  └── contact_vectors      ← ベクトルデータ（RAG・類似検索用）
```

---

## ① contacts（基本情報テーブル）

**役割**: ユーザーが送信した入力をそのまま保存する。受信後は変更しない。

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | Integer | PK, Serial | 管理ID |
| name | String(50) | NOT NULL | 氏名 |
| email | String(255) | NOT NULL, Index | メールアドレス |
| subject | String(100) | NOT NULL | 件名 |
| message | Text | NOT NULL | 本文（サニタイズ後） |
| status | Enum | NOT NULL, DEFAULT 'new' | 対応状態（new / in_progress / resolved） |
| assigned_email | String(255) | Nullable | 転送先の担当者メールアドレス |
| is_spam | Boolean | DEFAULT false | スパム判定フラグ |
| created_at | DateTime | DEFAULT NOW() | 受信日時 |
| updated_at | DateTime | DEFAULT NOW() | 最終更新日時（status変更時に更新） |

> `message` はサニタイズ（HTMLタグ除去・制御文字削除）後の値を保存する。

---

## ② contact_ai_analyses（AI解析結果テーブル）

**役割**: LLMが解析した結果を保存する。モデル変更・再解析時に `updated_at` を更新して上書きする。

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | Integer | PK, Serial | 管理ID |
| contact_id | Integer | FK → contacts.id, UNIQUE | 対応するお問い合わせ（1対1） |
| category | Enum | NOT NULL | 分類（shipping / product / billing / other） |
| priority | Integer | NOT NULL, DEFAULT 1 | 緊急度（1:通常 / 2:高 / 3:至急） |
| sentiment | Enum | NOT NULL | 感情（positive / neutral / negative） |
| summary | String(100) | Nullable | AIによる30文字以内の要約 |
| reasoning | Text | Nullable | AIがそのカテゴリを選んだ根拠 |
| refined_count | Integer | DEFAULT 0 | self-refinement の実行回数 |
| model_name | String(50) | NOT NULL | 使用したLLMモデル名（例: gemini-1.5-pro） |
| analyzed_at | DateTime | DEFAULT NOW() | 解析実行日時 |
| created_at | DateTime | DEFAULT NOW() | レコード作成日時 |
| updated_at | DateTime | DEFAULT NOW() | 最終更新日時（再解析時に更新） |

> `contact_id` に `UNIQUE` 制約を設けることで `contacts` と 1対1 の関係を保証する。

---

## ③ contact_vectors（RAG・類似検索用テーブル）

**役割**: お問い合わせ本文をベクトル化して保存する。過去の類似問い合わせの検索や、RAGによる回答生成に使用する。

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | Integer | PK, Serial | 管理ID |
| contact_id | Integer | FK → contacts.id, UNIQUE | 対応するお問い合わせ（1対1） |
| embedding | Vector(1536) | NOT NULL | 本文の埋め込みベクトル（pgvector） |
| embedding_model | String(50) | NOT NULL | 使用した埋め込みモデル名（例: text-embedding-3-small） |
| chunk_text | Text | Nullable | ベクトル化した元テキスト（チャンク） |
| created_at | DateTime | DEFAULT NOW() | レコード作成日時 |

> `Vector(1536)` はOpenAIの `text-embedding-3-small` の次元数。モデルに合わせて変更する。
> pgvectorの `ivfflat` または `hnsw` インデックスを `embedding` カラムに作成することで高速なANN検索が可能。

---

## ER図

```
┌─────────────────────────┐
│        contacts         │  ← ユーザーの生データ（不変）
│─────────────────────────│
│ id              PK      │
│ name                    │
│ email           Index   │
│ subject                 │
│ message                 │
│ status                  │
│ assigned_email          │
│ is_spam                 │
│ created_at              │
│ updated_at              │
└────────────┬────────────┘
             │ 1
     ┌───────┴────────┐
     │ 1              │ 1
     ▼                ▼
┌──────────────────┐  ┌──────────────────────┐
│contact_ai_analyses│  │   contact_vectors    │
│──────────────────│  │──────────────────────│
│ id         PK    │  │ id           PK      │
│ contact_id FK,UQ │  │ contact_id   FK,UQ   │
│ category         │  │ embedding    Vector  │
│ priority         │  │ embedding_model      │
│ sentiment        │  │ chunk_text           │
│ summary          │  │ created_at           │
│ reasoning        │  └──────────────────────┘
│ refined_count    │    ↑ 類似検索・RAGに使用
│ model_name       │
│ analyzed_at      │
│ created_at       │
│ updated_at       │
└──────────────────┘
  ↑ 再解析時に updated_at 更新
```

---

## データの流れ

```
1. POST /api/v1/contacts
   └─ contacts にレコード作成（生データのみ）

2. BackgroundTask: AI解析
   └─ contact_ai_analyses にレコード作成（カテゴリ・優先度・感情分析）

3. BackgroundTask: ベクトル化
   └─ contact_vectors にレコード作成（埋め込みベクトル保存）

4. 担当者へのメール送信
   └─ contacts.assigned_email, status を更新

5. PATCH /api/v1/admin/contacts/{id}（担当者の手動修正）
   └─ contact_ai_analyses.category を更新
      contact_ai_analyses 側の修正理由は reasoning に追記
```

---

## requirements.md との対応

| 要件 | 実現するカラム |
|---|---|
| LLM解析機能（カテゴリ分類） | contact_ai_analyses.category |
| 緊急度判定 | contact_ai_analyses.priority |
| 感情分析 | contact_ai_analyses.sentiment |
| 自動振り分け（担当部署メール） | contacts.assigned_email |
| 対応ステータス管理 | contacts.status |
| スパム対策 | contacts.is_spam |
| self-refinement の精度評価 | contact_ai_analyses.refined_count |
| LLMモデル切り替えの追跡 | contact_ai_analyses.model_name |
| 類似問い合わせの検索（RAG） | contact_vectors.embedding |
