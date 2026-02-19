# 開発環境

## 🛠️ 技術スタック一覧

|カテゴリ|選定技術|理由・役割|
|---|---|---|
|言語 / フレームワーク|Python 3.11+ / FastAPI|高速な非同期処理 (asyncio) により、LLM待ち時間の間も他のリクエストを捌けるため。|
|AI (LLM)|Gemini 1.5 Flash|低レイテンシかつ強力な Function Calling 機能を備え、構造化データの抽出に最適。||データベース|PostgreSQL / SQLModel |
PydanticとSQLAlchemyの長所を併せ持ち、型安全なDB操作が可能。|
キャッシュ / Queue|Redisレートリミット管理や、将来的なジョブキュー（Celery等）の拡張用。|
|認証|PyJWT|管理者向けエンドポイントのステートレスな認証。インフラ / 実行環境|Docker & Docker Compose|開発環境と本番環境の差異を無くし、どこでも即座に起動可能にする。|

## ベクトルデータベース
、**「過去の類似問い合わせの検索」や「FAQ（よくある質問）との照合」**による、さらなる精度向上と自動回答の実現

・pgvector :　既存のDB (PostgreSQL) をそのまま使える。リレーショナルデータとベクトルデータを一括管理できる。

## RAG の実装
LangChain

```
ユーザー入力を受け取り、LlamaIndexを「検索ツール」として呼び出し、その結果をGeminiに渡して classify_inquiry 関数を実行させる。
```

## エージェントの記憶と状態管理

1. 短期記憶：Redis (RedisChatMessageHistory)

  * FastAPIと相性が良く、非常に高速です。

    * 理由: ユーザーが連続してメッセージを送る際、ミリ秒単位で履歴を取り出せるため、LLMの応答待ち時間を最小限に抑えられます。

  * 実装: LangChainの RedisChatMessageHistory を使用。

2. 長期記憶：PostgreSQL (PostgresChatMessageHistory)

  * 理由: 過去のすべてのお問い合わせ履歴を保存し、管理者が後で分析したり、ユーザーが1ヶ月後に戻ってきたときに文脈を復元したりするために使用します。

    * 実装: LangChainの PostgresChatMessageHistory または SQLAlchemy を使用。

セマンティック記憶：pgvector (ベクトル検索)


## Function Call

process_inquiry_routing (お問い合わせの振り分けと判定)

```
関数の引数（パラメータ）:

category: shipping, product, billing, other (Enum)

LLMが判断した振り分け先。

priority: 1 (低), 2 (通常), 3 (至急) (Integer)

「キャンセル希望」「怒り」などを検知した場合に自動で 3 を割り振る。

sentiment: positive, neutral, negative (String)

感情分析結果。

summary: String

担当者が一目で内容を把握するための、30文字程度の要約。

reasoning: String

なぜそのカテゴリと優先度にしたのかという論理的な根拠。
```

escalate_to_manager (管理者へのエスカレーション)

```
関数の引数（パラメータ）:

reason: aggressive_tone, legal_threat, high_value_loss (Enum)

エスカレーションが必要だと判断した理由。

alert_message: String

管理者のチャットツール（Slack等）に即座に飛ばすための警告文。
```
suggest_faq_articles (FAQ記事の自動提案)

```
関数の引数（パラメータ）:

faq_ids: List[String]

ナレッジベースから関連性が高いと思われる記事のIDリスト。
```

GeminiのSDKに渡すためのスキーマ構成です。


```json
{
  "name": "process_inquiry_routing",
  "description": "顧客からのお問い合わせ内容を分析し、ECサイトの業務フローに基づいた最適な担当部署への振り分けと優先順位付けを行います。感情分析結果も抽出し、即時対応が必要なリスクを特定します。",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "enum": ["shipping", "product", "billing", "other"],
        "description": "内容に基づいた担当部署の分類。'shipping':配送遅延・日時変更・注文キャンセル希望、'product':商品の仕様・不具合・在庫確認、'billing':支払い方法の変更・領収書発行・返金、'other':それ以外の一般的な質問や提言。"
      },
      "priority": {
        "type": "integer",
        "enum": [1, 2, 3],
        "description": "対応の緊急度。1:一般的な質問。2:数日以内の回答が必要。3:至急。特に『キャンセル希望』『配送先の間違い』『激しい怒り』『法的措置の示唆』が含まれる場合は必ず3を選択してください。"
      },
      "sentiment": {
        "type": "string",
        "enum": ["positive", "neutral", "negative"],
        "description": "顧客の感情状態。不満や苦情、皮肉が含まれる場合は'negative'。感謝や満足は'positive'。事実のみの記述は'neutral'としてください。"
      },
      "summary": {
        "type": "string",
        "description": "管理画面の一覧で表示するための要約。主語（誰が）と述語（何をしたいか）を明確にし、30文字以内で作成してください。例：『配送遅延による注文キャンセルを希望』"
      },
      "reasoning": {
        "type": "string",
        "description": "この判定に至った論理的な根拠。入力されたメッセージのどの部分が特定のカテゴリや優先度（特に優先度3）に該当すると判断したかを簡潔に記述してください。自己改善（Self-refinement）の根拠として使用されます。"
      },
      "is_spam": {
        "type": "boolean",
        "description": "内容が広告、無意味な文字列の羅列、フィッシングサイトへの誘導など、カスタマーサポートが対応不要なスパムであるかどうかを判定します。"
      }
    },
    "required": ["category", "priority", "sentiment", "summary", "reasoning", "is_spam"]
  }
}
```

## ストリーミングAPIの実装

LLMの応答をトークンごとにリアルタイムで受け取る機能です。
FastAPI の StreamingResponse を使用して、Gemini からの回答や解析のステップを逐次送信します。


## LLMと Embeddingモデルの設定


## サンドボックス化

## Ragasを使用した評価

## システム設計
* RDBかNoSQLか
* サーバーレスかコンテナか
* AWSかAZUREか

* 何を作るか
* 優先順位の調整
* ステークホルダーへの説明
* 技術的負債を経営層にどう伝えるか

## ドメイン知識
ドメインエキスパートになる

* 無効化された
```
特定言語の習熟・コーディング速度・定型パターンの知識・テストやドキュメントの記述、単純なデバッグ
```
* 価値が上がったもの
```
問題定義力、アーキテクチャ設計、レビュー力、コミュニケーション、運用の経験知、ドメイン知識
```
