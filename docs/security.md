
# セキュリティ

* 特に認証・認可の漏れ、APIキーの露出、外部からのアクセス制御を重点的に。
* RLSの未設定

*リポジトリに含めてはいけないもの*
* AWS / GCP / Azure などの認証ファイル をpushしてないか
* .envファイルpushしてないか
* SSH鍵
* データベースのダンプ・実体ファイル
  * 「テストデータだからいいや」と思っていても、本番データが混ざっていたり、個人情報が含まれていたりすることがあります。そもそもバイナリファイルや巨大なテキストはGit管理に向きません。
* OSが勝手に作るファイル

間違えて、上げてしまった場合
https://zenn.dev/kewa8579/articles/4aa92ec168313a

```.gitignore

# セキュリティ関連
.env
*.pem
*.key
id_rsa

# OS関連（global設定していない場合）
.DS_Store
Thumbs.db

# 依存関係・ビルド
node_modules/
dist/
build/
__pycache__/
*.pyc

# ログ・DB
*.log
*.sqlite3

```