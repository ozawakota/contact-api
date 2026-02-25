# プロジェクト構造・組織化

## ディレクトリ組織原則
### 機能ベース分割
- **ドメイン駆動**: contacts/を中心とした機能的境界
- **レイヤー分離**: models/、schemas、use_case、providersの責務明確化
- **関心の分離**: app/（アプリケーションロジック）とdocs/（仕様書）の分離

### 設定・デプロイ分離
- **インフラ**: cloudbuild.yaml（ルート）、Dockerfile（docker/配下）
- **環境設定**: backend/とfrontend/で分離管理
- **ドキュメント**: docs/配下に体系化
- **認証設定**: Firebase設定ファイル（lib/firebase.ts）とCloud Functions

## 現在の構造パターン
```
contact-api/
├── backend/                    # アプリケーション層
│   ├── app/                    # FastAPIアプリケーション
│   │   ├── main.py            # エントリーポイント
│   │   ├── contacts/          # コンタクト機能モジュール
│   │   │   ├── _validators.py # 入力検証・セキュリティ
│   │   │   ├── providers.py   # DI・依存性注入
│   │   │   ├── schemas.py     # Pydanticスキーマ
│   │   │   └── use_case.py    # ビジネスロジック・フロー制御
│   │   └── models/            # データモデル層
│   │       └── contact.py     # SQLAlchemyモデル定義
│   └── db-backup/docker/      # コンテナ化・デプロイ設定
├── frontend/                  # Next.jsフロントエンド
│   ├── app/                   # App Routerページ
│   ├── components/            # 再利用UIコンポーネント
│   │   ├── auth/              # 認証関連（LoginForm, AuthGuard）
│   │   ├── ui/                # 基本UIコンポーネント
│   │   └── forms/             # フォーム関連
│   ├── hooks/                 # カスタムReact Hooks（useAuth）
│   ├── lib/                   # 設定・ユーティリティ（firebase.ts）
│   ├── types/                 # TypeScript型定義
│   └── .env.example          # 環境変数テンプレート
├── docs/                      # プロジェクトドキュメント
│   ├── requirements.md        # 機能・非機能要件
│   ├── architecture.md       # システム設計
│   ├── api-contract.md       # API仕様
│   ├── database-design.md    # DB設計・3テーブル分離
│   ├── security.md           # セキュリティ対策・脅威分析
│   ├── firebase-setup.md     # Firebase認証設定ガイド
│   └── skills.md             # 技術スタック詳細
├── frontend/                  # フロントエンド（将来）
├── terraform/                 # IaC（将来）
└── cloudbuild.yaml           # CI/CDパイプライン
```

## 命名規約
### ファイル・ディレクトリ
- **Python**: snake_case（use_case.py、_validators.py）
- **設定ファイル**: kebab-case（cloudbuild.yaml）
- **ドキュメント**: kebab-case（api-contract.md）

### Python コード
- **クラス**: PascalCase（Contact、ContactAnalysis）
- **関数・変数**: snake_case（process_inquiry、ai_analysis）
- **定数**: UPPER_SNAKE_CASE（MAX_MESSAGE_LENGTH）
- **プライベート**: アンダースコア接頭辞（_validators.py、_sanitize）

## モジュール構成パターン
### contacts/ モジュール構造
```python
# 責務分離パターン
schemas.py      # データ構造定義（Pydantic）
use_case.py     # ビジネスロジック・制御フロー
providers.py    # 依存性注入・サービス組み立て
_validators.py  # セキュリティ・入力検証（プライベート）
```

### データベース設計パターン
```python
# 3テーブル分離パターン
models/contact.py           # メインエンティティ
models/contact_analysis.py  # AI解析結果（分離）
models/contact_vector.py    # ベクトルデータ（RAG用）
```

## インポート規約
### 標準インポート順序
```python
# 1. 標準ライブラリ
from typing import Optional
from datetime import datetime

# 2. サードパーティ
from fastapi import FastAPI
from sqlalchemy import Column, String

# 3. ローカル（相対インポート）
from .schemas import ContactRequest
from ._validators import sanitize_input
```

### Frontend インポートパターン
```typescript
// 1. React・Next.js
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// 2. サードパーティ
import { signInWithPopup } from 'firebase/auth';

// 3. ローカル（絶対パス @/ エイリアス使用）
import { useAuth } from '@/hooks/useAuth';
import { auth } from '@/lib/firebase';
```

### 絶対vs相対パス
- **Backend アプリケーション内**: 相対インポート（.schemas、.use_case）
- **Backend モジュール間**: 絶対インポート（app.models.contact）
- **Frontend**: @/エイリアス使用（@/hooks、@/components）
- **外部パッケージ**: 絶対インポート（fastapi、react、firebase）

## 設定・環境管理
### 環境変数パターン
```
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
SENDGRID_API_KEY=...
JWT_SECRET_KEY=...
```

### デプロイ設定
- **本番**: Cloud Run（asia-northeast1）
- **イメージ**: asia-northeast1-docker.pkg.dev/.../fastapi-app
- **設定**: cloudbuild.yaml（Google Cloud Build）

## 拡張ガイドライン
### 新機能追加時
1. **app/[機能名]/** ディレクトリ作成
2. **schemas → use_case → providers** の順で実装
3. **models/[機能名].py** でDBモデル定義
4. **docs/[機能名].md** で仕様書作成

### セキュリティ機能
- **_validators.py**: 入力検証関数（プライベート）
- **providers.py**: セキュリティサービス組み立て
- **各use_case**: セキュリティレイヤー通過必須