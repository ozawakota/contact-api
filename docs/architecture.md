# アーキテクチャ設計

## アーキテクチャパターン

**レイヤードアーキテクチャ（クリーンアーキテクチャ準拠）**

- View はリクエストの受付のみ。ロジックを持たない
- UseCase がフロー（AI解析→DB保存→メール送信）を制御する
- Repository を介してDBアクセスを抽象化する
- Service（AI・ベクトル）は UseCase から呼ばれる独立した「道具箱」とする

---

## 技術スタック

| カテゴリ | 採用技術 | 役割 |
|---|---|---|
| API | FastAPI | エンドポイント定義・バリデーション |
| LLM | Gemini API（Function Calling） | カテゴリ分類・感情分析・self-refinement |
| ベクトルDB | pgvector（PostgreSQL拡張） | 類似問い合わせ検索・RAG |
| メール送信 | SendGrid / Gmail SMTP | 担当者への自動振り分け・ユーザーへの自動返信 |
| インフラ | Google Cloud Run | サーバーレスAPIホスティング |
| CI/CD | Google Cloud Build | 自動ビルド・デプロイ |

---

## ディレクトリ構成

### 現状（実装済み）

```
backend/
├── app/
│   ├── main.py                  # FastAPIアプリのエントリーポイント
│   ├── contacts/
│   │   ├── __init__.py
│   │   ├── _validators.py       # 入力サニタイズ・インジェクション検知
│   │   ├── providers.py         # 依存性注入（DIコンテナ）
│   │   ├── schemas.py           # Pydanticバリデーションモデル
│   │   └── use_case.py          # フロー制御（AI解析→DB保存）
│   └── models/
│       └── contact.py           # SQLAlchemy テーブル定義
└── db-backup/
    └── docker/
        ├── Dockerfile           # コンテナイメージ定義
        └── requirements.txt     # Pythonパッケージ
```

### 目標構成（実装予定）

```
backend/
├── app/
│   ├── main.py
│   ├── contacts/
│   │   ├── __init__.py
│   │   ├── _validators.py       # サニタイズ・インジェクション検知
│   │   ├── providers.py         # DIコンテナ
│   │   ├── schemas.py           # リクエスト/レスポンス スキーマ
│   │   ├── use_case.py          # フロー制御（AI解析→保存→メール）
│   │   └── views.py             # ルーター定義（Viewはここのみ）
│   ├── models/
│   │   ├── contact.py           # contacts テーブル
│   │   ├── contact_ai_analysis.py  # contact_ai_analyses テーブル
│   │   └── contact_vector.py    # contact_vectors テーブル
│   ├── repositories/
│   │   ├── contact.py           # contacts テーブルのCRUD
│   │   ├── contact_ai_analysis.py  # AI解析結果のCRUD
│   │   └── contact_vector.py    # ベクトルデータのCRUD・類似検索
│   └── services/
│       ├── ai_agent/
│       │   ├── agent.py         # Gemini Function Callingの核
│       │   └── tools.py         # classify_inquiry等のツール定義
│       ├── email/
│       │   └── sender.py        # 担当者振り分け・自動返信メール
│       └── vector/
│           └── embedder.py      # テキスト→ベクトル変換
└── db-backup/
    └── docker/
        ├── Dockerfile
        └── requirements.txt
```

---

## テーブル設計

3テーブルに分離し、**生データ・AI解析結果・ベクトルデータ**の責務を明確にする。
詳細は [database-design.md](./database-design.md) を参照。

```
contacts                 ← ユーザーの生データ（不変）
  └── contact_ai_analyses   ← AIが解析したメタデータ（再解析で更新可）
  └── contact_vectors       ← 埋め込みベクトル（RAG・類似検索用）
```

---

## データフロー

```
クライアント
    │
    │ POST /api/v1/contacts
    ▼
views.py（ルーター）
    │ リクエストを受けて use_case を呼ぶだけ
    ▼
_validators.py
    │ サニタイズ・インジェクション検知 → 問題あれば 422 を返す
    ▼
use_case.py（フロー制御）
    │
    ├─① contacts に保存（repositories/contact.py）
    │    └─ APIレスポンス 201 を即時返却
    │
    └─ BackgroundTask（非同期）
         │
         ├─② AI解析（services/ai_agent/agent.py）
         │    │  Gemini Function Calling でカテゴリ・優先度・感情分析
         │    │  self-refinement で結果を再検証
         │    └─ contact_ai_analyses に保存
         │
         ├─③ ベクトル化（services/vector/embedder.py）
         │    │  本文を埋め込みモデルでベクトル化
         │    └─ contact_vectors に保存
         │
         └─④ メール送信（services/email/sender.py）
              │  AI解析のカテゴリに基づき担当者へ転送
              └─ ユーザーへ受付完了メールを送信
```

---

## CI/CDパイプライン（Cloud Build）

```
git push
    │
    ▼
Cloud Build（cloudbuild.yaml）
    │
    ├─① Docker イメージをビルド
    │    Dockerfile: backend/db-backup/docker/Dockerfile
    │    コンテキスト: ./backend
    │
    ├─② Artifact Registry にプッシュ
    │    asia-northeast1-docker.pkg.dev/{PROJECT_ID}/contact-api/fastapi-app
    │
    └─③ Cloud Run にデプロイ
         サービス名: fastapi-service
         リージョン: asia-northeast1（東京）
```

---

## レイヤー責務

| レイヤー | ファイル | やること | やらないこと |
|---|---|---|---|
| View | views.py | リクエスト受付・use_case 呼び出し | ビジネスロジック |
| UseCase | use_case.py | フロー制御・Service の組み合わせ | DB直接アクセス |
| Repository | repositories/*.py | DB の読み書き | ビジネスロジック |
| Service | services/**/*.py | AI解析・ベクトル化・メール送信 | DB直接アクセス |
| Model | models/*.py | テーブル定義（SQLAlchemy） | ロジック |
