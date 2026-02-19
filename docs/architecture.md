## アーキテクチャ設計

*** 種類 ***

* クリーンアーキテクチャ
* レイヤードアーキテクチャ
* ヘキサゴナルアーキテクチャ

```bash

├── api
│   └── contacts
│       ├── __init__.py
│       ├── views.py       # POST /api/v1/contacts などを定義
│       ├── use_case.py    # AI解析とDB保存のフロー制御
│       └── schemas.py     # リクエスト用バリデーションモデル
├── models
│   └── contact.py         # 以前作成した Contact テーブル定義
├── repositories
│   └── contact.py         # def save_contact(...) などを実装
├── services
│   ├── ai_agent
│   │   ├── agent.py       # LangChain / Gemini エージェントの核
│   │   └── tools.py       # Function Calling で使う関数の実体
│   └── memory
│       └── vector_store.py # pgvector 関連の操作
```

## 意識すること

1. Viewにロジックを書かない
  > api/contacts/views.py はリクエストを受けて use_case.py を呼ぶだけにする。
2. Serviceを「道具箱」にする
  > LLMの呼び出しやベクトル検索は services/ に作り、それを use_case.py が組み合わせて「お問い合わせフロー」を完成させる。
3. Repositoryを介して保存する
  > use_case 内で直接 db.session を使わず、repositories/contact.py を経由する。