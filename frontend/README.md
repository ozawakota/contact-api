# Contact API Frontend

次世代カスタマーサポートシステムのReactフロントエンドアプリケーション

## 🚀 機能概要

### Core Features
- **📧 お問い合わせフォーム**: バリデーション付きの使いやすいフォーム
- **🤖 AI分析表示**: Gemini AIによる自動分析結果の可視化
- **🔍 ベクター検索**: 類似お問い合わせの意味的検索
- **⚙️ 管理ダッシュボード**: 包括的な管理機能
- **🔐 Firebase認証**: オプションのユーザー認証
- **📊 システム状態監視**: リアルタイムのシステム状態表示

### Advanced Features
- **レスポンシブデザイン**: モバイル・タブレット・デスクトップ対応
- **リアルタイム通知**: React Hot Toast統合
- **アクセシビリティ**: WCAG準拠のUI設計
- **パフォーマンス最適化**: 遅延読み込みとキャッシュ機能

## 🛠 技術スタック

### Frontend Framework
- **React 18**: 最新のReact機能とフック
- **TypeScript**: 型安全な開発環境
- **React Router DOM**: SPA ナビゲーション

### Styling & UI
- **Tailwind CSS**: ユーティリティファーストCSS
- **Headless UI**: アクセシブルなUIコンポーネント
- **Hero Icons**: 美しいアイコンライブラリ

### State Management & Data
- **React Query**: サーバー状態管理
- **Axios**: HTTP クライアント
- **Date-fns**: 日付処理ライブラリ

### Authentication & Services
- **Firebase**: 認証とユーザー管理
- **React Hot Toast**: 通知システム

## 📁 プロジェクト構造

```
frontend/
├── public/
│   ├── index.html              # メインHTMLテンプレート
│   └── favicon.ico
├── src/
│   ├── components/             # Reactコンポーネント
│   │   ├── ContactForm.tsx     # お問い合わせフォーム
│   │   ├── AIAnalysisDisplay.tsx  # AI分析結果表示
│   │   ├── VectorSearch.tsx    # ベクター検索
│   │   ├── AdminDashboard.tsx  # 管理ダッシュボード
│   │   ├── ContactList.tsx     # お問い合わせ一覧
│   │   ├── SystemStatusDisplay.tsx  # システム状態表示
│   │   ├── SimilarContactsList.tsx  # 類似お問い合わせ表示
│   │   ├── AuthModal.tsx       # 認証モーダル
│   │   └── LoadingSpinner.tsx  # ローディングコンポーネント
│   ├── services/               # API・認証サービス
│   │   ├── api.ts             # API通信ロジック
│   │   └── auth.ts            # Firebase認証
│   ├── types/                  # TypeScript型定義
│   │   └── index.ts           # 全体型定義
│   ├── App.tsx                # メインアプリケーション
│   ├── index.tsx              # エントリーポイント
│   └── index.css              # グローバルスタイル
├── package.json               # 依存関係とスクリプト
├── tailwind.config.js         # Tailwind設定
├── .env.example              # 環境変数テンプレート
└── README.md                 # このファイル
```

## 🚀 セットアップ手順

### 1. 依存関係のインストール
```bash
cd frontend
npm install
```

### 2. 環境変数の設定
```bash
cp .env.example .env.local
```

`.env.local` を編集して以下を設定：
```env
# API Configuration
REACT_APP_API_URL=https://your-deployed-backend-url.com

# Firebase Configuration (Optional)
REACT_APP_FIREBASE_API_KEY=your-api-key
REACT_APP_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
REACT_APP_FIREBASE_PROJECT_ID=your-project-id
REACT_APP_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=123456789
REACT_APP_FIREBASE_APP_ID=1:123456789:web:abcdef123456
```

### 3. 開発サーバー起動
```bash
npm start
```

アプリケーションが `http://localhost:3000` で起動します。

### 4. プロダクションビルド
```bash
npm run build
```

### 5. テスト実行
```bash
npm test
```

## 🔧 設定詳細

### API接続設定
バックエンドAPIのベースURLを環境変数で指定：
```env
REACT_APP_API_URL=https://your-backend-url.com
```

### Firebase認証設定（オプション）
Firebase プロジェクトを作成し、設定情報を環境変数に追加：

1. Firebase Console でプロジェクト作成
2. Authentication を有効化
3. Web アプリを追加
4. 設定情報を `.env.local` に追加

認証が不要な場合は、Firebase設定を省略できます。

## 🎨 コンポーネント詳細

### ContactForm
- **機能**: お問い合わせフォームとバリデーション
- **特徴**: リアルタイムバリデーション、AI分析結果表示
- **依存**: ApiService、AIAnalysisDisplay、SimilarContactsList

### AdminDashboard
- **機能**: 管理者向けダッシュボード
- **特徴**: 統計表示、お問い合わせ一覧、システム状態監視
- **権限**: 認証オプション、すべての機能にアクセス可能

### VectorSearch
- **機能**: ベクター検索インターフェース
- **特徴**: 自然言語検索、類似度調整、検索結果表示
- **API**: `/api/v1/search` エンドポイント使用

### AIAnalysisDisplay
- **機能**: AI分析結果の可視化
- **表示項目**: 
  - カテゴリ分類
  - 緊急度レベル
  - 感情分析
  - 信頼度スコア
  - キートピック
  - 推奨アクション

## 🔐 認証システム

### Firebase Authentication
- **サポート認証方法**:
  - Google OAuth
  - メールアドレス・パスワード
- **機能**:
  - 自動ログイン状態管理
  - JWTトークン自動更新
  - ログアウト機能

### 認証なしモード
Firebase設定を省略すると、認証なしで全機能を利用可能。

## 📱 レスポンシブデザイン

### ブレークポイント
- **Mobile**: `< 640px`
- **Tablet**: `640px - 1024px`
- **Desktop**: `> 1024px`

### 対応機能
- タッチ操作対応
- スクリーンリーダー対応
- キーボードナビゲーション
- 高コントラストモード

## ⚡ パフォーマンス最適化

### React最適化
- `React.memo` による再レンダリング防止
- `useMemo` / `useCallback` によるメモ化
- 遅延読み込み（Lazy Loading）

### ネットワーク最適化
- API レスポンスキャッシュ
- 画像最適化
- バンドルサイズ最小化

## 🔍 開発者ツール

### TypeScript
- 厳密な型チェック
- インテリセンス サポート
- エラー早期発見

### ESLint & Prettier
- コード品質維持
- 自動フォーマット
- チーム開発標準化

## 🚀 デプロイメント

### Vercel（推奨）
```bash
npm run build
# Vercel にデプロイ
```

### Netlify
```bash
npm run build
# build/ フォルダをアップロード
```

### 環境変数設定
デプロイ先で以下の環境変数を設定：
- `REACT_APP_API_URL`
- Firebase設定（認証使用時）

## 🐛 トラブルシューティング

### よくある問題

1. **API接続エラー**
   - `REACT_APP_API_URL` の確認
   - バックエンドサービスの稼働確認
   - CORSポリシーの確認

2. **Firebase認証エラー**
   - Firebase設定の確認
   - プロジェクトIDの確認
   - 認証ドメインの設定

3. **ビルドエラー**
   - Node.js バージョン確認（推奨: 16+）
   - 依存関係の再インストール
   - TypeScript エラーの修正

## 📞 サポート

### 開発チーム連絡先
- 技術的な問題: [GitHub Issues](https://github.com/your-repo/contact-api)
- 機能リクエスト: feature-request@your-domain.com
- セキュリティ問題: security@your-domain.com

---

**Next-Generation Customer Support System v8.0.0**  
*Powered by React, TypeScript, Tailwind CSS, and Firebase*